"""
OfficeVision AI - Step 4: Multi-Object Tracking & Workstation State Machine
===========================================================================

Purpose:
  1. Multi-Object Person Tracking using Ultralytics ByteTrack (`persist=True`).
  2. Assign consistent, anonymous tracking IDs (Person #1, Person #2) across frames.
  3. Workstation Finite State Machine (FSM):
     - Entry Debounce: Requires 8 continuous frames (~0.8s) to confirm arrival.
     - Exit Debounce: 3.0s grace period when occupant disappears, eliminating false vacants.
     - Posture Consensus: Rolling majority voting for Seated vs Standing.
  4. Real-Time Event Timeline Overlay:
     - Renders a live timeline of verified transitions and gesture events.
     - Demonstrates the telemetry payload ready for FastAPI WebSockets and PostgreSQL.
  5. Privacy Guardrail:
     - Tracking IDs are transient and reset when the camera session resets;
       they are NEVER linked to employee biometric identity.
"""

import os
import sys
import time
import argparse
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

from core.camera import open_camera_stream, open_webcam, normalize_camera_source
from core.spatial_zone import (
    WorkstationZone,
    calculate_body_anchor,
    load_workstations_from_config,
    save_workstations_to_config,
)
from analysis.posture import PostureClassifier
from analysis.gesture import GestureDetector
from analysis.state_machine import WorkstationStateMachine, WorkstationState


class ZoneCalibrationState:
    """Manages interactive mouse clicking for drawing custom desk polygons."""
    def __init__(self):
        self.is_calibrating = False
        self.clicked_points = []

    def reset(self):
        self.clicked_points = []


calibration_state = ZoneCalibrationState()


def on_mouse_click(event, x, y, flags, param):
    """Mouse callback to record polygon points during calibration."""
    if not calibration_state.is_calibrating:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        calibration_state.clicked_points.append((x, y))
        print(f"[CALIBRATION] Point {len(calibration_state.clicked_points)}: ({x}, {y})")




def render_gesture_dialog(frame: np.ndarray, active_confirmation: dict, w: int, h: int):
    """Renders popup dialog for voluntary employee break confirmation."""
    dialog_w, dialog_h = 560, 150
    dx1 = (w - dialog_w) // 2
    dy1 = 120
    dx2 = dx1 + dialog_w
    dy2 = dy1 + dialog_h

    overlay = frame.copy()
    cv2.rectangle(overlay, (dx1, dy1), (dx2, dy2), (25, 20, 20), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    cv2.rectangle(frame, (dx1, dy1), (dx2, dy2), (0, 220, 255), 2)
    cv2.putText(frame, "INTENTIONAL HAND-RAISE DETECTED", (dx1 + 20, dy1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, "Voluntary Status: Press key [1-4] or [x] to dismiss", (dx1 + 20, dy1 + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1, cv2.LINE_AA)

    cv2.putText(frame, "[1] Restroom", (dx1 + 20, dy1 + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[2] Meeting", (dx1 + 180, dy1 + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[3] Errand", (dx1 + 330, dy1 + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[4] Stretch Break", (dx1 + 20, dy1 + 125), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[x] Dismiss/Cancel", (dx1 + 240, dy1 + 125), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 240), 1, cv2.LINE_AA)


def render_event_timeline(frame: np.ndarray, events: list, w: int, h: int):
    """Renders a compact real-time event timeline sidebar below the top header."""
    panel_w, panel_h = 250, 110
    px1 = w - panel_w - 10
    py1 = 44  # Placed right below the 36px top bar with no overlap
    px2 = px1 + panel_w
    py2 = py1 + panel_h

    # Translucent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (px1, py1), (px2, py2), (18, 18, 18), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    cv2.rectangle(frame, (px1, py1), (px2, py2), (70, 70, 70), 1)
    cv2.putText(frame, "EVENT TIMELINE", (px1 + 10, py1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 200), 1, cv2.LINE_AA)
    cv2.line(frame, (px1 + 8, py1 + 24), (px2 - 8, py1 + 24), (60, 60, 60), 1)

    if not events:
        cv2.putText(frame, "No state changes yet", (px1 + 10, py1 + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (130, 130, 130), 1, cv2.LINE_AA)
    else:
        # Display the most recent 4 events
        for i, ev in enumerate(events[-4:]):
            ey = py1 + 42 + (i * 18)
            etime = ev.get("formatted_time", "")
            etype = ev.get("event_type", "")
            if etype == "WORKSTATION_STATE_CHANGE":
                nstate = ev.get("new_state", "").replace("OCCUPIED_", "")
                tid = f"P#{ev['track_id']}" if ev.get("track_id") else "-"
                ev_str = f"[{etime}] -> {nstate} ({tid})"
                color = (0, 255, 120) if "OCCUPIED" in ev.get("new_state", "") else (40, 140, 255)
            elif etype == "GESTURE_CONFIRMED":
                ev_str = f"[{etime}] GESTURE: {ev.get('reason', '')[:12]}"
                color = (0, 220, 255)
            else:
                ev_str = f"[{etime}] {etype[:16]}"
                color = (200, 200, 200)

            cv2.putText(frame, ev_str, (px1 + 10, ey), cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description="OfficeVision AI - Step 4: Multi-Object Tracking & State Machine")
    parser.add_argument(
        "--source",
        "-s",
        default=os.environ.get("CAMERA_SOURCE", 0),
        help="Camera source: integer index (0, 1) or stream URL (e.g. http://192.168.100.2:8080/video)",
    )
    args = parser.parse_args()

    print("=" * 75)
    print(" OfficeVision AI - Step 4: Multi-Object Tracking & State Machine")
    print("=" * 75)

    # 1. Load YOLO26-Pose Model
    model_name = "yolo26n-pose.pt"
    print(f"[INFO] Loading pose model: {model_name}...")
    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"[ERROR] Failed to load model '{model_name}': {e}")
        sys.exit(1)

    # 2. Load Workstation Zones
    config_file = "config/workstations.json"
    workstations = load_workstations_from_config(config_file)
    zone = workstations[0]
    print(f"[INFO] Initialized Workstation: {zone.id}")

    # 3. Initialize Modular Analyzers & FSM
    posture_classifier = PostureClassifier()
    gesture_detector = GestureDetector(required_hold_frames=10, cooldown_seconds=8.0)
    state_machine = WorkstationStateMachine(
        workstation_id=zone.id,
        entry_debounce_frames=8,    # ~0.8s entry confirmation
        exit_debounce_seconds=3.0,  # 3.0s absence grace period
        posture_window_size=10,     # 10-frame posture smoothing
    )

    # 4. Open Camera Stream
    cap = open_camera_stream(args.source)
    if cap is None or not cap.isOpened():
        print(f"[CRITICAL] Could not open camera source '{args.source}'.")
        sys.exit(1)

    window_name = "OfficeVision AI - Step 4: Tracking & Temporal State Machine"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse_click)

    print("\n[INFO] Interactive Features in Step 4:")
    print("  - Person Tracking: Each detected human is assigned a track ID (e.g. Person #1)")
    print("  - Anti-Flicker Debounce: Step away for 1-2s -> system stays Occupied!")
    print("  - Stay away > 3.0s -> system cleanly logs transition to VACANT")
    print("  - Live Timeline: Real-time transition events displayed on the right sidebar")
    print("  - Press 'q' to Quit | 'c' to Calibrate\n")

    prev_time = time.time()
    timeline_events = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]

            # 5. Run Inference with ByteTrack Multi-Object Tracking
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
            # labels=False suppresses default 'person 0.88' text to keep display clean and readable
            annotated_frame = results[0].plot(labels=False)

            # 6. Process Tracked Persons & Spatial Presence
            occupant_in_zone = False
            zone_track_id = None
            instant_posture = "UNKNOWN"
            gesture_status = None
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

                    anchor_x, anchor_y, anchor_label = calculate_body_anchor(person_kpts, bbox)

                    # Check if this person is inside the workstation zone
                    is_in_zone = zone.is_point_inside((anchor_x, anchor_y), w, h)

                    # Subtle Person ID tag at bottom-left corner of person's bounding box
                    if bbox is not None:
                        bx1, by2 = int(bbox[0]), int(bbox[3])
                        cv2.rectangle(annotated_frame, (bx1, by2 - 20), (bx1 + 55, by2), (25, 25, 25), -1)
                        cv2.rectangle(annotated_frame, (bx1, by2 - 20), (bx1 + 55, by2), (0, 255, 255), 1)
                        cv2.putText(annotated_frame, f"P#{tid}", (bx1 + 5, by2 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1, cv2.LINE_AA)

                    if is_in_zone:
                        occupant_in_zone = True
                        zone_track_id = tid

                        # Posture estimation
                        posture, conf, _ = posture_classifier.classify(person_kpts, bbox, h, w)
                        instant_posture = posture

                        # Gesture detection for this occupant
                        triggered, gesture_status = gesture_detector.process_frame(person_kpts, person_is_in_desk=True)

                        # Draw small anchor crosshair on chest
                        ax, ay = int(anchor_x), int(anchor_y)
                        cv2.drawMarker(annotated_frame, (ax, ay), (0, 255, 255), cv2.MARKER_CROSS, 12, 1)

            # If occupant left the desk, decay gesture detector
            if not occupant_in_zone:
                _, gesture_status = gesture_detector.process_frame(None, person_is_in_desk=False)

            # 7. Update Workstation State Machine (Hysteresis & Anti-Flicker)
            transition_event = state_machine.update(
                is_inside_zone=occupant_in_zone,
                track_id=zone_track_id,
                instant_posture=instant_posture,
            )
            if transition_event:
                timeline_events.append(transition_event)

            fsm_status = state_machine.get_status()
            current_fsm_state = fsm_status["current_state"]

            # 8. Render Desk Zone (show_label=False avoids duplicate floating badges)
            zone.is_occupied = (current_fsm_state in (WorkstationState.OCCUPIED_SEATED, WorkstationState.OCCUPIED_STANDING))
            annotated_frame = zone.draw(annotated_frame, show_label=False)

            # Calculate FPS
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0.0
            prev_time = curr_time

            # 9. Sleek Docked Top Bar Header (Non-overlapping edge-to-edge ribbon)
            cv2.rectangle(annotated_frame, (0, 0), (w, 36), (15, 15, 15), -1)
            cv2.line(annotated_frame, (0, 36), (w, 36), (60, 60, 60), 1)

            # Left side of top bar: System status
            cv2.putText(
                annotated_frame,
                f"OfficeVision | FPS: {fps:.1f} | People: {detected_count}",
                (10, 23),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.46,
                (0, 255, 150),
                1,
                cv2.LINE_AA,
            )

            # Center of top bar: Workstation Status Badge
            if fsm_status["is_debouncing_exit"]:
                pill_text = f"ABSENCE GRACE PERIOD: {fsm_status['debounce_sec_left']}s"
                pill_bg = (20, 80, 180)  # Amber
                pill_fg = (255, 255, 255)
            elif current_fsm_state == WorkstationState.OCCUPIED_SEATED:
                pill_text = f"{zone.id}: OCCUPIED (SEATED) [P#{fsm_status['active_track_id']}]"
                pill_bg = (0, 150, 60)   # Green
                pill_fg = (255, 255, 255)
            elif current_fsm_state == WorkstationState.OCCUPIED_STANDING:
                pill_text = f"{zone.id}: OCCUPIED (STANDING) [P#{fsm_status['active_track_id']}]"
                pill_bg = (180, 140, 0)  # Gold
                pill_fg = (255, 255, 255)
            elif current_fsm_state == WorkstationState.VACANT and occupant_in_zone:
                pill_text = f"VERIFYING ARRIVAL... ({int(fsm_status['entry_progress'] * 100)}%)"
                pill_bg = (160, 90, 0)
                pill_fg = (255, 255, 255)
            else:
                pill_text = f"{zone.id}: VACANT"
                pill_bg = (35, 35, 35)
                pill_fg = (40, 160, 255)

            (tw, th), bl = cv2.getTextSize(pill_text, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
            pill_x = (w - tw) // 2
            cv2.rectangle(annotated_frame, (pill_x - 8, 5), (pill_x + tw + 8, 30), pill_bg, -1)
            cv2.rectangle(annotated_frame, (pill_x - 8, 5), (pill_x + tw + 8, 30), (100, 100, 100), 1)
            cv2.putText(annotated_frame, pill_text, (pill_x, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.44, pill_fg, 1, cv2.LINE_AA)

            # Right side of top bar: Session timer
            cv2.putText(
                annotated_frame,
                f"Time: {fsm_status['time_in_state_sec']}s",
                (w - 95, 23),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.44,
                (190, 190, 190),
                1,
                cv2.LINE_AA,
            )

            # 10. Render Real-Time Event Timeline (Right side, y: 44..154)
            render_event_timeline(annotated_frame, timeline_events, w, h)

            # 11. Render Gesture Feedback Bar (Bottom-left, y: h-48..h-20)
            if gesture_status:
                right_up = gesture_status.get("right_hand_up", False)
                progress = gesture_status.get("right_progress", 0.0)
                in_cooldown = gesture_status.get("in_cooldown", False)
                cooldown_sec = gesture_status.get("cooldown_remaining", 0.0)
                is_stretching = gesture_status.get("is_stretching", False)
                action_label = gesture_status.get("action_label", "Gesture: Raise Right Hand Only")

                bar_x1, bar_y1 = 12, h - 45
                bar_w, bar_h = 240, 14
                bar_x2 = bar_x1 + bar_w
                bar_y2 = bar_y1 + bar_h

                cv2.rectangle(annotated_frame, (bar_x1 - 4, bar_y1 - 18), (bar_x2 + 4, bar_y2 + 4), (18, 18, 18), -1)

                if in_cooldown:
                    cv2.putText(annotated_frame, f"Cooldown: {cooldown_sec}s", (bar_x1, bar_y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 140, 255), 1, cv2.LINE_AA)
                    cv2.rectangle(annotated_frame, (bar_x1, bar_y1), (bar_x2, bar_y2), (50, 50, 50), 1)
                else:
                    lbl_color = (0, 165, 255) if is_stretching else ((0, 255, 255) if right_up else (160, 160, 160))
                    cv2.putText(annotated_frame, action_label, (bar_x1, bar_y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, lbl_color, 1, cv2.LINE_AA)

                    fill_w = int(bar_w * progress)
                    cv2.rectangle(annotated_frame, (bar_x1, bar_y1), (bar_x2, bar_y2), (50, 50, 50), 1)
                    if fill_w > 0 and not is_stretching:
                        cv2.rectangle(annotated_frame, (bar_x1, bar_y1), (bar_x1 + fill_w, bar_y2), (0, 230, 255), -1)

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

            # 13. Render Gesture Voluntary Confirmation Modal (if active)
            if gesture_detector.active_confirmation:
                render_gesture_dialog(annotated_frame, gesture_detector.active_confirmation, w, h)

            # Calibration Overlay (if active)
            if calibration_state.is_calibrating:
                cv2.rectangle(annotated_frame, (0, 38), (w, 68), (40, 20, 160), -1)
                cv2.putText(annotated_frame, f"CALIBRATION: Click 4 points ({len(calibration_state.clicked_points)}/4) | 's' Save | 'r' Reset", (15, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
                for pt in calibration_state.clicked_points:
                    cv2.circle(annotated_frame, pt, 5, (0, 0, 255), -1)

            # 14. Display Frame
            cv2.imshow(window_name, annotated_frame)

            # Keyboard Shortcuts
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("\n[INFO] Exit signal received.")
                break
            elif key in [ord("1"), ord("2"), ord("3"), ord("4")]:
                key_char = chr(key)
                ev = gesture_detector.select_reason(key_char)
                if ev:
                    # Append confirmed gesture to live timeline
                    timeline_events.append({
                        "event_type": "GESTURE_CONFIRMED",
                        "reason": ev["selected_reason"],
                        "formatted_time": ev["confirmed_at"],
                    })
            elif key == ord("x"):
                gesture_detector.cancel_confirmation()
            elif key == ord("c"):
                calibration_state.is_calibrating = not calibration_state.is_calibrating
                calibration_state.reset()
            elif key == ord("r"):
                calibration_state.reset()
            elif key == ord("s"):
                if len(calibration_state.clicked_points) >= 3:
                    norm_pts = [[round(px / w, 4), round(py / h, 4)] for px, py in calibration_state.clicked_points]
                    workstations[0].polygon_normalized = norm_pts
                    save_workstations_to_config(workstations, config_file)
                    print(f"[CALIBRATION] Saved polygon to {config_file}!")
                    calibration_state.is_calibrating = False
                    calibration_state.reset()

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[SUCCESS] Camera released and windows closed cleanly.")


if __name__ == "__main__":
    main()
