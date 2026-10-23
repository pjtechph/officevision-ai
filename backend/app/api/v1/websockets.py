"""
OfficeVision AI - WebSocket Endpoints (v1)
===========================================

Real-time streaming endpoints for:
  - Edge AI Ingestion (`/api/v1/ws/ai-telemetry`)
  - Web Dashboard Sync (`/api/v1/ws/live-dashboard`)
"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.websocket_hub import ws_hub
from services.presence_service import presence_service

router = APIRouter()


@router.websocket("/ws/ai-telemetry")
async def websocket_ai_telemetry(websocket: WebSocket):
    """
    Ingestion endpoint for the Edge AI Vision Engine.
    Streams binary JPEG video frames, per-frame presence metrics, and transitions.
    Also serves as the control conduit to push commands down to the AI Engine.
    """
    await ws_hub.connect_ai_worker(websocket)
    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break

            # 1. Binary JPEG frame for browser live streaming
            if "bytes" in msg and msg["bytes"]:
                presence_service.set_latest_frame(msg["bytes"])
                continue

            # 2. Structured JSON telemetry & events
            if "text" in msg and msg["text"]:
                try:
                    packet = json.loads(msg["text"])
                    packet_type = packet.get("type", "TELEMETRY")

                    if packet_type == "TELEMETRY":
                        presence_service.update_telemetry(packet)
                    elif packet_type == "WORKSTATION_STATE_CHANGE":
                        presence_service.record_event(packet)
                    elif packet_type == "WORKSTATIONS_CALIBRATED":
                        wid = packet.get("workstation_id")
                        poly = packet.get("polygon_normalized")
                        if wid and poly:
                            presence_service.update_polygon(wid, poly)
                        else:
                            presence_service.reload_workstations()
                        await ws_hub.broadcast_to_dashboards({
                            "type": "WORKSTATIONS_UPDATED",
                            "workstations": list(presence_service.workstations.values()),
                        })

                    # Broadcast live state to all active React dashboard clients
                    await ws_hub.broadcast_to_dashboards(packet)

                except json.JSONDecodeError:
                    print("[WS ERROR] Received non-JSON packet from AI worker")

    except WebSocketDisconnect:
        pass
    finally:
        ws_hub.disconnect_ai_worker(websocket)
        # Notify dashboard that camera stream disconnected
        await ws_hub.broadcast_to_dashboards({
            "type": "CAMERA_STATUS",
            "camera_id": "CAM-01",
            "status": "OFFLINE",
        })


@router.websocket("/ws/live-dashboard")
async def websocket_live_dashboard(websocket: WebSocket):
    """
    Real-time push channel for the React Dashboard.
    Provides sub-second updates of floorplan occupancy, events, and camera uptime.
    """
    await ws_hub.connect_dashboard(websocket)
    try:
        # Immediately push current state snapshot upon connection
        initial_snapshot = {
            "type": "INITIAL_SNAPSHOT",
            "workstations": list(presence_service.workstations.values()),
            "recent_events": presence_service.event_timeline[-10:],
            "health": presence_service.get_health_status(),
        }
        await websocket.send_text(json.dumps(initial_snapshot))

        # Keep connection open to listen for client commands (e.g. heartbeat ping)
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "PONG"}))

    except WebSocketDisconnect:
        ws_hub.disconnect_dashboard(websocket)
