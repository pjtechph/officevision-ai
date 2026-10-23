"""
OfficeVision AI - Step 5: Connected Edge AI Inference Microservice
==================================================================

Purpose:
  1. Integrates full AI vision pipeline:
     - YOLO26-Pose + ByteTrack Multi-Object Tracking
     - Multi-Workstation Spatial Monitoring (e.g., DESK-01, DESK-02)
     - Posture Classification (Seated vs. Standing)
     - Anti-Flicker State Machine (Entry Debounce & 3.0s Exit Grace Period)
     - Dynamic Hot-Reload: Listens to Dashboard commands via WebSocket to instantly
       update workstation zones without restarting or dropping frames.
  2. Dispatches real-time telemetry and structured events to the FastAPI Backend:
     - WebSocket stream at `ws://127.0.0.1:8000/api/v1/ws/ai-telemetry`
     - Clean decoupled microservice architecture (runs locally or on edge device)
     - Sends live JPEG video frames to the backend for dashboard embedding
"""

import os
import sys
import time
import argparse
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

# Core & Analysis Modules
from core.camera import open_camera_stream, open_webcam, normalize_camera_source
from core.spatial_zone import (
    WorkstationZone,
    calculate_body_anchor,
    load_workstations_from_config,
    save_workstations_to_config,
)
from analysis.posture import PostureClassifier
from analysis.state_machine import WorkstationStateMachine, WorkstationState
from telemetry.ws_client import EdgeTelemetryClient


class ZoneCalibrationState:
    def __init__(self):
        self.is_calibrating = False
        self.clicked_points = []
        self.active_desk_idx = 0

    def reset(self):
        self.clicked_points = []


calibration_state = ZoneCalibrationState()


def on_mouse_click(event, x, y, flags, param):
    if not calibration_state.is_calibrating:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        calibration_state.clicked_points.append((x, y))
        print(f"[CALIBRATION] Point {len(calibration_state.clicked_points)}: ({x}, {y})")


def render_event_timeline(frame: np.ndarray, events: list, w: int, h: int):
    panel_w, panel_h = 260, 120
    px1 = w - panel_w - 10
    py1 = 44
    px2 = px1 + panel_w
    py2 = py1 + panel_h

    overlay = frame.copy()
    cv2.rectangle(overlay, (px1, py1), (px2, py2), (18, 18, 18), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    cv2.rectangle(frame, (px1, py1), (px2, py2), (70, 70, 70), 1)
    cv2.putText(frame, "EVENT TIMELINE", (px1 + 10, py1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 200), 1, cv2.LINE_AA)
    cv2.line(frame, (px1 + 8, py1 + 24), (px2 - 8, py1 + 24), (60, 60, 60), 1)

    if not events:
        cv2.putText(frame, "No state changes yet", (px1 + 10, py1 + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130, 130, 130), 1, cv2.LINE_AA)
    else:
        for i, ev in enumerate(events[-4:]):
            ey = py1 + 42 + (i * 18)
            etime = ev.get("formatted_time") or ev.get("confirmed_at", "")
            etype = ev.get("event_type", "")
            wid = ev.get("workstation_id", "")
            if etype == "WORKSTATION_STATE_CHANGE":
                nstate = ev.get("new_state", "").replace("OCCUPIED_", "")
                tid = f"P#{ev['track_id']}" if ev.get("track_id") else "-"
                ev_str = f"[{etime}] {wid}->{nstate} ({tid})"
                color = (0, 255, 120) if "OCCUPIED" in ev.get("new_state", "") else (40, 140, 255)
            else:
                ev_str = f"[{etime}] {etype[:16]}"
                color = (200, 200, 200)

            cv2.putText(frame, ev_str, (px1 + 8, ey), cv2.FONT_HERSHEY_SIMPLEX, 0.34, color, 1, cv2.LINE_AA)


def sync_workstations_from_config(config_file: str, current_machines: dict):
    """
    Reloads workstations from config file and preserves state machines for unchanged desks.
    """
    updated_workstations = load_workstations_from_config(config_file)
    if not updated_workstations:
        updated_workstations = [
            WorkstationZone("DESK-01", "Workstation 1", [[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]])
        ]
        save_workstations_to_config(updated_workstations, config_file)

    updated_ids = {w.id for w in updated_workstations}

    # Remove state machines for deleted workstations
    for wid in list(current_machines.keys()):
        if wid not in updated_ids:
            del current_machines[wid]

    # Add state machines for new workstations
    for w in updated_workstations:
        if w.id not in current_machines:
            current_machines[w.id] = WorkstationStateMachine(
                workstation_id=w.id,
                entry_debounce_frames=8,
                exit_debounce_seconds=3.0,
                posture_window_size=10,
            )

    print(f"[HOT-RELOAD] Synchronized {len(updated_workstations)} Workstation Zone(s): {[w.id for w in updated_workstations]}")
    return updated_workstations, current_machines


def main():
    parser = argparse.ArgumentParser(description="OfficeVision AI - Step 5: Multi-Workstation Edge AI Inference Service")
    parser.add_argument(
        "--source",
        "-s",
        default=os.environ.get("CAMERA_SOURCE", 0),
        help="Camera source: integer index (0, 1) or stream URL (e.g. http://192.168.100.2:8080/video)",
    )
    args = parser.parse_args()

    print("=" * 75)
    print(" OfficeVision AI - Step 5: Multi-Workstation Edge AI Inference Service")
    print("=" * 75)

    # 1. Load YOLO26-Pose Model
    model_name = "yolo26n-pose.pt"
    print(f"[INFO] Loading pose model: {model_name}...")
    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"[ERROR] Failed to load model '{model_name}': {e}")
        sys.exit(1)

    # 2. Load Workstation Zones (Supports multiple workstations)
    config_file = "config/workstations.json"
    state_machines = {}
    workstations, state_machines = sync_workstations_from_config(config_file, state_machines)

    # 3. Initialize Posture Classifier
    posture_classifier = PostureClassifier()

    # 4. Initialize Edge Telemetry Client (Streams to FastAPI WebSocket Gateway)
    telemetry_client = EdgeTelemetryClient(server_ws_url="ws://127.0.0.1:8000/api/v1/ws/ai-telemetry")
    telemetry_client.start()

    # 5. Open Camera Stream
    cap = open_camera_stream(args.source)
    if cap is None or not cap.isOpened():
        print(f"[CRITICAL] Could not open camera source '{args.source}'.")
        telemetry_client.stop()
        sys.exit(1)

    window_name = "OfficeVision AI - Edge AI Vision Service (Streaming to FastAPI)"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse_click)

    print("\n[INFO] Edge AI Multi-Workstation Service Active:")
    print("  - Video inference runs independently.")
    print("  - Real-time MJPEG frames + Telemetry streamed to FastAPI.")
    print("  - Full Dashboard Control: Hot-reloads workstation zones on the fly.")
    print("  - Press 'q' to Quit | 'c' to Calibrate locally\n")

    prev_time = time.time()
    last_telemetry_broadcast = 0.0
    timeline_events = []

    try:
        while True:
            # Check for inbound control commands from the Dashboard via WebSocket
            cmd = telemetry_client.get_command()
            if cmd:
                action = cmd.get("action")
                if action == "RELOAD_WORKSTATIONS":
                    workstations, state_machines = sync_workstations_from_config(config_file, state_machines)
                    if calibration_state.active_desk_idx >= len(workstations):
                        calibration_state.active_desk_idx = 0

            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]

            # 6. Run Pose Inference with ByteTrack Multi-Object Tracking
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
            annotated_frame = results[0].plot(labels=False)

            # 7. Map Detected Persons to Workstations
            desk_occupants = {}
            detected_count = 0

            if results[0].keypoints is not None and results[0].keypoints.data is not None:
                kpts_data = results[0].keypoints.data.cpu().numpy()
                boxes_obj = results[0].boxes
                boxes_data = boxes_obj.xyxy.cpu().numpy() if boxes_obj is not None else None
                track_ids = boxes_obj.id.int().cpu().tolist() if (boxes_obj is not None and boxes_obj.id is not None) else None

                detected_count = len(kpts_data)

                for idx, person_kpts in enumerate(kpts_data):
                    bbox = boxes_data[idx] if (boxes_data is not None and idx < len(boxes_data)) else None
                    tid = track_ids[idx] if (track_ids is not None and idx < len(track_ids)) else (idx + 1)

                    anchor_x, anchor_y, _ = calculate_body_anchor(person_kpts, bbox)

                    # Draw subtle Person ID tag near bottom of bounding box
                    if bbox is not None:
                        bx1, by2 = int(bbox[0]), int(bbox[3])
                        cv2.rectangle(annotated_frame, (bx1, by2 - 20), (bx1 + 55, by2), (25, 25, 25), -1)
                        cv2.rectangle(annotated_frame, (bx1, by2 - 20), (bx1 + 55, by2), (0, 255, 255), 1)
                        cv2.putText(annotated_frame, f"P#{tid}", (bx1 + 5, by2 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1, cv2.LINE_AA)

                    # Check which workstation this person falls into
                    for desk in workstations:
                        if desk.is_point_inside((anchor_x, anchor_y), w, h):
                            if desk.id not in desk_occupants:
                                desk_occupants[desk.id] = {
                                    "kpts": person_kpts,
                                    "bbox": bbox,
                                    "tid": tid,
                                    "anchor": (anchor_x, anchor_y),
                                }

            # 8. Update State Machine for Each Workstation
            for desk in workstations:
                sm = state_machines.get(desk.id)
                if not sm:
                    continue

                if desk.id in desk_occupants:
                    occ = desk_occupants[desk.id]
                    person_kpts = occ["kpts"]
                    bbox = occ["bbox"]
                    tid = occ["tid"]
                    ax, ay = occ["anchor"]

                    posture, conf, _ = posture_classifier.classify(person_kpts, bbox, h, w)

                    transition_event = sm.update(
                        is_inside_zone=True,
                        track_id=tid,
                        instant_posture=posture,
                    )

                    # Draw anchor crosshair on person
                    cv2.drawMarker(annotated_frame, (int(ax), int(ay)), (0, 255, 255), cv2.MARKER_CROSS, 12, 1)

                else:
                    transition_event = sm.update(
                        is_inside_zone=False,
                        track_id=None,
                        instant_posture="UNKNOWN",
                    )

                if transition_event:
                    timeline_events.append(transition_event)
                    telemetry_client.send_packet({
                        "type": "WORKSTATION_STATE_CHANGE",
                        **transition_event,
                    })

                # Render Desk Zone on Frame
                fsm_status = sm.get_status()
                desk.is_occupied = (fsm_status["current_state"] in (WorkstationState.OCCUPIED_SEATED, WorkstationState.OCCUPIED_STANDING))
                annotated_frame = desk.draw(annotated_frame, show_label=False)

                # Draw desk label on top-left of polygon
                if desk.polygon_normalized and len(desk.polygon_normalized) >= 1:
                    p0 = desk.polygon_normalized[0]
                    lx, ly = int(p0[0] * w), int(p0[1] * h) - 6
                    state_lbl = fsm_status["current_state"].replace("OCCUPIED_", "")
                    color = (0, 255, 120) if desk.is_occupied else (80, 80, 80)
                    cv2.putText(annotated_frame, f"{desk.name} [{state_lbl}]", (lx, max(15, ly)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

            # 9. Periodic Telemetry Streaming (every ~0.5 seconds)
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0.0
            prev_time = curr_time

            if curr_time - last_telemetry_broadcast >= 0.5:
                w_states = []
                for desk in workstations:
                    if desk.id in state_machines:
                        st = state_machines[desk.id].get_status()
                        w_states.append({
                            "id": desk.id,
                            "name": desk.name,
                            "current_state": st["current_state"],
                            "active_track_id": st["active_track_id"],
                            "time_in_state_sec": st["time_in_state_sec"],
                        })

                has_grace = any(state_machines[d.id].get_status()["is_debouncing_exit"] for d in workstations if d.id in state_machines)
                max_grace_left = max([state_machines[d.id].get_status()["debounce_sec_left"] for d in workstations if d.id in state_machines] + [0.0])

                telemetry_client.send_packet({
                    "type": "TELEMETRY",
                    "camera_id": "CAM-01",
                    "fps": round(fps, 1),
                    "tracked_people_count": detected_count,
                    "workstation_states": w_states,
                    "active_grace_period": has_grace,
                    "grace_period_remaining": max_grace_left,
                    "timestamp": curr_time,
                })
                last_telemetry_broadcast = curr_time

            # 10. Docked Top Bar Header
            cv2.rectangle(annotated_frame, (0, 0), (w, 36), (15, 15, 15), -1)
            cv2.line(annotated_frame, (0, 36), (w, 36), (60, 60, 60), 1)

            # Left side: FPS, people & backend connection pill
            ws_conn_color = (0, 255, 120) if telemetry_client.is_connected else (100, 100, 100)
            ws_conn_text = "API: ONLINE" if telemetry_client.is_connected else "API: WAITING"
            cv2.circle(annotated_frame, (12, 18), 4, ws_conn_color, -1, lineType=cv2.LINE_AA)
            cv2.putText(
                annotated_frame,
                f"{ws_conn_text} | FPS: {fps:.1f} | People: {detected_count} | Desks: {len(workstations)}",
                (22, 23),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                ws_conn_color,
                1,
                cv2.LINE_AA,
            )

            # Center Pill: Multi-Desk Quick Status Summary
            occ_count = sum(1 for d in workstations if d.id in state_machines and state_machines[d.id].get_status()["current_state"] != WorkstationState.VACANT)
            summary_text = f"OCCUPANCY: {occ_count}/{len(workstations)} DESKS"
            (tw, th), bl = cv2.getTextSize(summary_text, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
            pill_x = (w - tw) // 2
            pill_bg = (0, 140, 60) if occ_count > 0 else (35, 35, 35)
            cv2.rectangle(annotated_frame, (pill_x - 8, 5), (pill_x + tw + 8, 30), pill_bg, -1)
            cv2.rectangle(annotated_frame, (pill_x - 8, 5), (pill_x + tw + 8, 30), (100, 100, 100), 1)
            cv2.putText(annotated_frame, summary_text, (pill_x, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

            # 11. Render Timeline (Right side)
            render_event_timeline(annotated_frame, timeline_events, w, h)

            # 12. Bottom-Right Shortcut Hints
            cv2.putText(
                annotated_frame,
                "Press 'q' to Quit | 'c' to Calibrate",
                (w - 225, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (150, 150, 150),
                1,
                cv2.LINE_AA,
            )

            # 13. Calibration Overlay (if active)
            if calibration_state.is_calibrating and len(workstations) > 0:
                active_wid = workstations[calibration_state.active_desk_idx % len(workstations)].id
                cv2.rectangle(annotated_frame, (0, 38), (w, 68), (40, 20, 160), -1)
                cv2.putText(
                    annotated_frame,
                    f"CALIBRATING [{active_wid}]: Click points ({len(calibration_state.clicked_points)}/4) | 'tab' Next Desk | 's' Save | 'r' Reset",
                    (15, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.44,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                for pt in calibration_state.clicked_points:
                    cv2.circle(annotated_frame, pt, 5, (0, 0, 255), -1)

            # 14. Send Live Frame to Backend for Web Streaming
            ret_enc, jpeg_buf = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret_enc:
                telemetry_client.send_frame(jpeg_buf.tobytes())

            # 15. Display Local Frame
            cv2.imshow(window_name, annotated_frame)

            # Keyboard Shortcuts
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("\n[INFO] Exit signal received.")
                break
            elif key == ord("c"):
                calibration_state.is_calibrating = not calibration_state.is_calibrating
                calibration_state.reset()
            elif key == 9:  # Tab key switches calibrating desk
                if len(workstations) > 0:
                    calibration_state.active_desk_idx = (calibration_state.active_desk_idx + 1) % len(workstations)
                    calibration_state.reset()
                    print(f"[CALIBRATION] Switched to {workstations[calibration_state.active_desk_idx].id}")
            elif key == ord("r"):
                calibration_state.reset()
            elif key == ord("s"):
                if len(calibration_state.clicked_points) >= 3 and len(workstations) > 0:
                    norm_pts = [[round(px / w, 4), round(py / h, 4)] for px, py in calibration_state.clicked_points]
                    cur_desk = workstations[calibration_state.active_desk_idx % len(workstations)]
                    cur_desk.polygon_normalized = norm_pts
                    save_workstations_to_config(workstations, config_file)
                    print(f"[CALIBRATION] Saved polygon for {cur_desk.id} to {config_file}!")
                    # Notify FastAPI backend and connected dashboards
                    telemetry_client.send_packet({
                        "type": "WORKSTATIONS_CALIBRATED",
                        "workstation_id": cur_desk.id,
                        "polygon_normalized": norm_pts,
                    })
                    calibration_state.is_calibrating = False
                    calibration_state.reset()

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")

    finally:
        telemetry_client.stop()
        cap.release()
        cv2.destroyAllWindows()
        print("[SUCCESS] Edge AI resources released cleanly.")


if __name__ == "__main__":
    main()
