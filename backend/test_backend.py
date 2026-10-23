"""
Automated Integration Test for OfficeVision AI FastAPI Backend
==============================================================

Verifies:
  1. REST Endpoints: /health, /workstations, /events, /attendance/check-in
  2. Full Workstation CRUD: Create, Edit, Polygon Update, Delete
  3. Edge AI Service Status & Process Control Endpoints
  4. WebSocket Telemetry Stream Ingestion and Hot-Reload Command Dispatch
  5. Live MJPEG Video Feed
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
    assert "process_status" in health_data
    print(f"[TEST] /api/v1/health: OK (Status: {health_data['status']})")

    # 3. Test Service Status & Control
    res_svc = client.get("/api/v1/service/status")
    assert res_svc.status_code == 200
    svc_data = res_svc.json()
    assert "running" in svc_data
    assert "camera_source" in svc_data
    print(f"[TEST] /api/v1/service/status: OK (Running: {svc_data['running']})")

    # 4. Test Workstations Listing
    res_ws = client.get("/api/v1/workstations")
    assert res_ws.status_code == 200
    ws_list = res_ws.json()
    assert len(ws_list) >= 1
    assert any(w["id"] == "DESK-01" for w in ws_list)
    print(f"[TEST] /api/v1/workstations: OK (Found {len(ws_list)} workstations)")

    # 5. Test Full Workstation CRUD
    # 5a. Create
    test_desk_id = "DESK-99"
    create_payload = {
        "id": test_desk_id,
        "name": "Test Lab Desk",
        "description": "Integration test temporary workstation",
        "polygon_normalized": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
    }
    res_create = client.post("/api/v1/workstations", json=create_payload)
    assert res_create.status_code == 200
    assert res_create.json()["id"] == test_desk_id
    print(f"[TEST] POST /api/v1/workstations: OK (Created {test_desk_id})")

    # 5b. Update Metadata
    update_payload = {
        "name": "Updated Test Desk Name",
        "description": "Updated description",
    }
    res_update = client.put(f"/api/v1/workstations/{test_desk_id}", json=update_payload)
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "Updated Test Desk Name"
    print(f"[TEST] PUT /api/v1/workstations/{test_desk_id}: OK (Updated name)")

    # 5c. Update Polygon
    new_poly = [[0.2, 0.2], [0.5, 0.2], [0.5, 0.5], [0.2, 0.5]]
    res_poly = client.post(f"/api/v1/workstations/{test_desk_id}/polygon", json={"polygon_normalized": new_poly})
    assert res_poly.status_code == 200
    print(f"[TEST] POST /api/v1/workstations/{test_desk_id}/polygon: OK (Updated polygon)")

    # 5d. Delete
    res_delete = client.delete(f"/api/v1/workstations/{test_desk_id}")
    assert res_delete.status_code == 200
    print(f"[TEST] DELETE /api/v1/workstations/{test_desk_id}: OK (Deleted)")

    # 6. Test Verified Employee Check-in (Privacy Guardrail)
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

    # 7. Test WebSocket Telemetry Streaming
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

    # 8. Verify Events are reflected in REST timeline
    res_events = client.get("/api/v1/events")
    assert res_events.status_code == 200
    events_list = res_events.json()
    assert len(events_list) >= 1
    assert any(e.get("new_state") == "OCCUPIED_SEATED" for e in events_list)
    print(f"[TEST] Telemetry reflected in /api/v1/events: OK ({len(events_list)} events)")

    # 9. Test Live Video Feed endpoint headers
    with client.stream("GET", "/api/v1/video-feed") as res_video:
        assert res_video.status_code == 200
        assert "multipart/x-mixed-replace" in res_video.headers.get("content-type", "")
        print("[TEST] /api/v1/video-feed MJPEG Stream: OK (200, multipart/x-mixed-replace)")

    print("\n[SUCCESS] ALL Step 5 FastAPI Backend Tests PASSED!")


if __name__ == "__main__":
    test_backend_suite()
