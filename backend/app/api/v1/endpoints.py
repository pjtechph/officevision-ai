"""
OfficeVision AI - REST API Endpoints (v1)
==========================================
"""

import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from services.presence_service import presence_service
from services.websocket_hub import ws_hub
from services.ai_process_manager import ai_process_manager
from schemas.telemetry import (
    WorkstationZoneSchema,
    WorkstationCreateRequest,
    WorkstationUpdateRequest,
    WorkstationEventSchema,
    EmployeeCheckInRequest,
    PolygonUpdateRequest,
    ServiceControlRequest,
)

router = APIRouter()


async def gen_frames():
    """Generates continuous MJPEG frames for browser video streaming."""
    while True:
        frame_bytes = presence_service.get_latest_frame()
        if frame_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        await asyncio.sleep(0.04)  # ~25 fps target


@router.get("/video-feed", summary="Live Camera MJPEG Stream")
async def get_video_feed():
    """Provides a continuous multipart MJPEG stream from the Edge AI worker."""
    return StreamingResponse(
        gen_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/health", summary="System Health & Camera Uptime")
def get_health() -> Dict[str, Any]:
    """Returns camera connection status, uptime, and AI engine telemetry health."""
    health = presence_service.get_health_status()
    service_proc = ai_process_manager.get_status()
    health["process_status"] = service_proc
    return health


# ============================================================================
# Edge AI Vision Service Process Control
# ============================================================================

@router.get("/service/status", summary="Edge AI Service Status")
def get_service_status() -> Dict[str, Any]:
    """Returns status of the Edge AI Vision process and WebSocket telemetry worker."""
    proc_info = ai_process_manager.get_status()
    health_info = presence_service.get_health_status()
    return {
        **proc_info,
        "ai_vision_connected": health_info["ai_vision_connected"],
        "camera_status": health_info["camera_status"],
        "seconds_since_last_heartbeat": health_info["seconds_since_last_heartbeat"],
    }


@router.post("/service/control", summary="Start/Stop/Restart Edge AI Service")
async def control_service(payload: ServiceControlRequest):
    """Controls the lifecycle of the Edge AI Vision process."""
    action = payload.action.lower()
    if action == "start":
        res = ai_process_manager.start_service(source=payload.camera_source)
    elif action == "stop":
        res = ai_process_manager.stop_service()
    elif action == "restart":
        res = ai_process_manager.restart_service(source=payload.camera_source)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action '{payload.action}'. Use 'start', 'stop', or 'restart'.")

    # Notify dashboards of status change
    await ws_hub.broadcast_to_dashboards({
        "type": "SERVICE_STATUS_CHANGE",
        "action": action,
        "status": res,
    })
    return res


# ============================================================================
# Workstations Management & Zone Calibration (Full CRUD + Hot-Reload)
# ============================================================================

@router.get("/workstations", summary="List All Workstations")
def get_workstations() -> List[Dict[str, Any]]:
    """Returns all registered workstations, polygon coordinates, and live occupancy states."""
    return list(presence_service.workstations.values())


@router.post("/workstations", summary="Create New Workstation")
async def create_workstation(payload: WorkstationCreateRequest):
    """Registers a new workstation zone and immediately hot-reloads the Edge AI Engine."""
    wid = payload.id.strip()
    name = payload.name.strip()
    poly = payload.polygon_normalized
    desc = payload.description or ""

    if not wid:
        raise HTTPException(status_code=400, detail="Workstation ID is required")
    if wid in presence_service.workstations:
        raise HTTPException(status_code=409, detail=f"Workstation '{wid}' already exists")
    if len(poly) < 3:
        raise HTTPException(status_code=400, detail="At least 3 polygon coordinates required")

    result = presence_service.add_workstation(wid, name, poly, desc)

    # Hot-reload Edge AI Engine and broadcast to active dashboards
    await ws_hub.send_to_ai_workers({"action": "RELOAD_WORKSTATIONS"})
    await ws_hub.broadcast_to_dashboards({
        "type": "WORKSTATIONS_UPDATED",
        "workstations": list(presence_service.workstations.values()),
    })

    return result


@router.put("/workstations/{workstation_id}", summary="Edit Workstation Details")
async def update_workstation(workstation_id: str, payload: WorkstationUpdateRequest):
    """Updates workstation name, description, and/or polygon, then hot-reloads the AI Engine."""
    if workstation_id not in presence_service.workstations:
        raise HTTPException(status_code=404, detail=f"Workstation '{workstation_id}' not found")

    if payload.polygon_normalized is not None and len(payload.polygon_normalized) < 3:
        raise HTTPException(status_code=400, detail="Polygon must contain at least 3 vertices")

    updated = presence_service.update_workstation(
        wid=workstation_id,
        name=payload.name,
        description=payload.description,
        polygon_normalized=payload.polygon_normalized,
    )

    # Hot-reload Edge AI Engine and broadcast to active dashboards
    await ws_hub.send_to_ai_workers({"action": "RELOAD_WORKSTATIONS"})
    await ws_hub.broadcast_to_dashboards({
        "type": "WORKSTATIONS_UPDATED",
        "workstations": list(presence_service.workstations.values()),
    })

    return updated


@router.delete("/workstations/{workstation_id}", summary="Delete Workstation")
async def delete_workstation(workstation_id: str):
    """Deletes a workstation zone by ID and hot-reloads the AI Engine."""
    success = presence_service.delete_workstation(workstation_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Workstation '{workstation_id}' not found")

    # Hot-reload Edge AI Engine and broadcast to active dashboards
    await ws_hub.send_to_ai_workers({"action": "RELOAD_WORKSTATIONS"})
    await ws_hub.broadcast_to_dashboards({
        "type": "WORKSTATIONS_UPDATED",
        "workstations": list(presence_service.workstations.values()),
    })

    return {"status": "SUCCESS", "message": f"Deleted {workstation_id}"}


@router.get("/workstations/{workstation_id}", summary="Get Workstation Details")
def get_workstation(workstation_id: str) -> Dict[str, Any]:
    if workstation_id not in presence_service.workstations:
        raise HTTPException(status_code=404, detail=f"Workstation '{workstation_id}' not found")
    return presence_service.workstations[workstation_id]


@router.post("/workstations/{workstation_id}/polygon", summary="Update Workstation Polygon")
@router.post("/workstations/{workstation_id}/calibrate", summary="Calibrate Workstation Polygon Zone")
async def update_polygon(workstation_id: str, payload: PolygonUpdateRequest):
    """Updates desk zone boundaries and hot-reloads the AI Engine without restart."""
    if len(payload.polygon_normalized) < 3:
        raise HTTPException(status_code=400, detail="Polygon must contain at least 3 vertices")

    # Clean and clamp normalized coordinates
    cleaned_poly = [
        [round(max(0.0, min(1.0, float(pt[0]))), 4), round(max(0.0, min(1.0, float(pt[1]))), 4)]
        for pt in payload.polygon_normalized
    ]

    success = presence_service.update_polygon(workstation_id, cleaned_poly)
    if not success:
        raise HTTPException(status_code=404, detail=f"Workstation '{workstation_id}' not found")

    # Hot-reload Edge AI Engine and broadcast to active dashboards
    await ws_hub.send_to_ai_workers({"action": "RELOAD_WORKSTATIONS"})
    await ws_hub.broadcast_to_dashboards({
        "type": "WORKSTATIONS_UPDATED",
        "workstations": list(presence_service.workstations.values()),
    })

    return {"status": "SUCCESS", "message": f"Polygon calibrated and updated for {workstation_id}", "polygon_normalized": cleaned_poly}


@router.post("/workstations/reload", summary="Reload Workstations from Disk Config")
async def reload_workstations_from_disk():
    """Forces reload of workstations from disk config and syncs AI engine and dashboards."""
    presence_service.reload_workstations()
    await ws_hub.send_to_ai_workers({"action": "RELOAD_WORKSTATIONS"})
    await ws_hub.broadcast_to_dashboards({
        "type": "WORKSTATIONS_UPDATED",
        "workstations": list(presence_service.workstations.values()),
    })
    return {
        "status": "SUCCESS",
        "message": "Workstations reloaded from disk and synchronized",
        "total_workstations": len(presence_service.workstations),
    }


# ============================================================================
# Events & Attendance
# ============================================================================

@router.get("/events", summary="Get Event Timeline")
def get_events(limit: int = Query(50, ge=1, le=200)) -> List[Dict[str, Any]]:
    """Returns chronological presence events and state changes."""
    return presence_service.event_timeline[-limit:]


@router.post("/attendance/check-in", summary="Verified Employee Attendance Check-In")
def check_in(payload: EmployeeCheckInRequest):
    """
    Records an authorized employee check-in (badge / portal).
    Upholds privacy rule: Employee identity is established via explicit check-in,
    NEVER via camera pose tracking alone.
    """
    if payload.workstation_id not in presence_service.workstations:
        raise HTTPException(status_code=404, detail=f"Workstation '{payload.workstation_id}' not found")

    record = presence_service.record_check_in(
        employee_id_code=payload.employee_id_code,
        workstation_id=payload.workstation_id,
        method=payload.verification_method,
    )
    return {"status": "SUCCESS", "record": record}


@router.get("/attendance/records", summary="List Attendance Records")
def get_attendance_records():
    """Lists verified check-in records for operational reporting."""
    return presence_service.attendance_records
