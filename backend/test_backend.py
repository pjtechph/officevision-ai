"""
Automated Integration Test for OfficeVision AI FastAPI Backend
==============================================================

Verifies:
  1. REST Endpoints: /health, /workstations, /events, /attendance/check-in
  2. Polygon Update logic
  3. WebSocket Telemetry Stream Ingestion
  4. Real-time Dashboard Synchronization
"""

import sys
from pathlib import Path

# Add backend/app to sys.path
backend_dir = Path(__file__).resolve().parent / "app"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from services.presence_service import presence_service


def test_backend_suite():
    print("[TEST] Initializing FastAPI TestClient...")
    client = TestClient(app)

    # 1. Test Root
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "RUNNING"
    print("[TEST] Root health check: OK (200)")

    # 2. Test Health Endpoint
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert "status" in health_data
    assert "camera_status" in health_data
    print(f"[TEST] /api/v1/health: OK (Status: {health_data['status']})")

    # 3. Test Workstations Listing
    res_ws = client.get("/api/v1/workstations")
    assert res_ws.status_code == 200
    ws_list = res_ws.json()
    assert len(ws_list) >= 1
    assert ws_list[0]["id"] == "DESK-01"
    print(f"[TEST] /api/v1/workstations: OK (Found {len(ws_list)} workstations)")

    # 4. Test Verified Employee Check-in (Privacy Guardrail)
    check_in_payload = {
        "employee_id_code": "EMP-9021",
        "workstation_id": "DESK-01",
        "verification_method": "BADGE_OR_WEB_PORTAL",
    }
    res_checkin = client.post("/api/v1/attendance/check-in", json=check_in_payload)
    assert res_checkin.status_code == 200
    checkin_data = res_checkin.json()
    assert checkin_data["status"] == "SUCCESS"
    assert checkin_data["record"]["employee_id_code"] == "EMP-9021"
    print("[TEST] /api/v1/attendance/check-in: OK (Verified check-in recorded)")

    # 5. Test Polygon Update
    new_polygon = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]]
    res_poly = client.post("/api/v1/workstations/DESK-01/polygon", json={"polygon_normalized": new_polygon})
    assert res_poly.status_code == 200
    print("[TEST] /api/v1/workstations/DESK-01/polygon: OK (Polygon update persisted)")

    # 6. Test WebSocket Telemetry Streaming
    print("[TEST] Testing WebSocket /api/v1/ws/ai-telemetry...")
    with client.websocket_connect("/api/v1/ws/ai-telemetry") as ws_ai:
        # Send telemetry packet
        telemetry_msg = {
            "type": "TELEMETRY",
            "camera_id": "CAM-01",
            "fps": 25.4,
            "tracked_people_count": 1,
            "workstation_states": [
                {
                    "id": "DESK-01",
                    "current_state": "OCCUPIED_SEATED",
                    "active_track_id": 1,
                    "time_in_state_sec": 12.0,
                }
            ],
            "active_grace_period": False,
            "grace_period_remaining": 0.0,
        }
        ws_ai.send_json(telemetry_msg)

        # Send state change event
        event_msg = {
            "type": "WORKSTATION_STATE_CHANGE",
            "event_type": "WORKSTATION_STATE_CHANGE",
            "workstation_id": "DESK-01",
            "previous_state": "VACANT",
            "new_state": "OCCUPIED_SEATED",
            "track_id": 1,
            "duration_in_prev_state_sec": 5.0,
            "confidence": 0.92,
            "timestamp": 1729690000.0,
            "formatted_time": "16:20:00",
        }
        ws_ai.send_json(event_msg)

        # Send gesture confirmed event
        gesture_msg = {
            "type": "GESTURE_CONFIRMED",
            "event_type": "GESTURE_CONFIRMED",
            "workstation_id": "DESK-01",
            "gesture_type": "RIGHT_HAND_RAISE",
            "selected_reason": "Restroom Break",
            "confirmed_at": "16:20:10",
            "timestamp": 1729690010.0,
        }
        ws_ai.send_json(gesture_msg)

    # 7. Verify Events are reflected in REST timeline
    res_events = client.get("/api/v1/events")
    assert res_events.status_code == 200
    events_list = res_events.json()
    assert len(events_list) >= 2
    assert any(e.get("new_state") == "OCCUPIED_SEATED" for e in events_list)
    assert any(e.get("event_type") == "GESTURE_CONFIRMED" and e.get("selected_reason") == "Restroom Break" for e in events_list)
    print(f"[TEST] Telemetry reflected in /api/v1/events: OK ({len(events_list)} events)")

    # 8. Verify Gesture is linked to the workstation card
    res_desk = client.get("/api/v1/workstations/DESK-01")
    assert res_desk.status_code == 200
    desk_data = res_desk.json()
    assert desk_data.get("latest_gesture") is not None
    assert desk_data["latest_gesture"]["reason"] == "Restroom Break"
    print(f"[TEST] Workstation latest_gesture updated: OK ({desk_data['latest_gesture']})")

    # 9. Test Live Video Feed endpoint headers
    with client.stream("GET", "/api/v1/video-feed") as res_video:
        assert res_video.status_code == 200
        assert "multipart/x-mixed-replace" in res_video.headers.get("content-type", "")
        print("[TEST] /api/v1/video-feed MJPEG Stream: OK (200, multipart/x-mixed-replace)")

    print("\n[SUCCESS] ALL Step 5 FastAPI Backend Tests PASSED!")


if __name__ == "__main__":
    test_backend_suite()
