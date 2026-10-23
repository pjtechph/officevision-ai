"""
OfficeVision AI - REST API Endpoints (v1)
==========================================
"""

import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from services.presence_service import presence_service
from schemas.telemetry import (
    WorkstationZoneSchema,
    WorkstationEventSchema,
    EmployeeCheckInRequest,
    PolygonUpdateRequest,
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
    return presence_service.get_health_status()


@router.get("/workstations", summary="List All Workstations")
def get_workstations() -> List[Dict[str, Any]]:
    """Returns all registered workstations, polygon coordinates, and live occupancy states."""
    return list(presence_service.workstations.values())


@router.post("/workstations", summary="Create New Workstation")
def create_workstation(payload: Dict[str, Any]):
    """Registers a new workstation zone."""
    wid = payload.get("id")
    name = payload.get("name", wid)
    poly = payload.get("polygon_normalized", [])
    desc = payload.get("description", "")
    if not wid or len(poly) < 3:
        raise HTTPException(status_code=400, detail="Workstation ID and at least 3 polygon points required")
    return presence_service.add_workstation(wid, name, poly, desc)


@router.delete("/workstations/{workstation_id}", summary="Delete Workstation")
def delete_workstation(workstation_id: str):
    """Deletes a workstation zone by ID."""
    success = presence_service.delete_workstation(workstation_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Workstation '{workstation_id}' not found")
    return {"status": "SUCCESS", "message": f"Deleted {workstation_id}"}


@router.get("/workstations/{workstation_id}", summary="Get Workstation Details")
def get_workstation(workstation_id: str) -> Dict[str, Any]:
    if workstation_id not in presence_service.workstations:
        raise HTTPException(status_code=404, detail=f"Workstation '{workstation_id}' not found")
    return presence_service.workstations[workstation_id]


@router.post("/workstations/{workstation_id}/polygon", summary="Update Workstation Polygon")
def update_polygon(workstation_id: str, payload: PolygonUpdateRequest):
    """Allows web floorplan editor to adjust desk zone boundaries."""
    if len(payload.polygon_normalized) < 3:
        raise HTTPException(status_code=400, detail="Polygon must contain at least 3 vertices")

    success = presence_service.update_polygon(workstation_id, payload.polygon_normalized)
    if not success:
        raise HTTPException(status_code=404, detail=f"Workstation '{workstation_id}' not found")
    return {"status": "SUCCESS", "message": f"Polygon updated for {workstation_id}"}


@router.get("/events", summary="Get Event Timeline")
def get_events(limit: int = Query(50, ge=1, le=200)) -> List[Dict[str, Any]]:
    """Returns chronological presence events, state changes, and voluntary gesture confirmations."""
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
