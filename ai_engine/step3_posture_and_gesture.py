"""
OfficeVision AI - Step 3: Posture Classification & Intentional Hand-Raise Recognition
======================================================================================

Purpose:
  1. Detect Workstation Occupancy using YOLO26-Pose and Spatial Zones.
  2. Classify Posture in real time:
     - OCCUPIED (SEATED)
     - OCCUPIED (STANDING)
     - VACANT
  3. Recognize Intentional Hand-Raise Gestures:
     - Kinematic check: Wrist raised above head and shoulder.
     - Multi-frame temporal verification: Hold hand raised for ~10 frames.
     - Progress bar HUD showing gesture accumulation.
     - Cooldown timer & duplicate suppression (~8 seconds).
     - Voluntary confirmation workflow:
         Press [1] Restroom Break
         Press [2] Meeting / Discussion
         Press [3] Official Errand
         Press [4] General Coffee / Stretch Break
         Press [x] Dismiss / Cancel
  4. Privacy compliance: Gestures NEVER auto-classify employee reasons.
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
    """Renders an interactive popup modal for voluntary employee break confirmation."""
    dialog_w, dialog_h = 560, 150
    dx1 = (w - dialog_w) // 2
    dy1 = 120
    dx2 = dx1 + dialog_w
    dy2 = dy1 + dialog_h

    # Translucent modal background
    overlay = frame.copy()
    cv2.rectangle(overlay, (dx1, dy1), (dx2, dy2), (25, 20, 20), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    # Modal border
    cv2.rectangle(frame, (dx1, dy1), (dx2, dy2), (0, 220, 255), 2)

    # Header
    cv2.putText(
        frame,
        "INTENTIONAL HAND-RAISE DETECTED",
        (dx1 + 20, dy1 + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 220, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "Voluntary Status: Press key [1-4] or [x] to dismiss",
        (dx1 + 20, dy1 + 55),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )

    # Options grid
    cv2.putText(frame, "[1] Restroom", (dx1 + 20, dy1 + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[2] Meeting", (dx1 + 180, dy1 + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[3] Errand", (dx1 + 330, dy1 + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[4] Stretch Break", (dx1 + 20, dy1 + 125), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "[x] Dismiss/Cancel", (dx1 + 240, dy1 + 125), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 240), 1, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description="OfficeVision AI - Step 3: Posture & Intentional Gesture Recognition")
    parser.add_argument(
        "--source",
        "-s",
        default=os.environ.get("CAMERA_SOURCE", 0),
        help="Camera source: integer index (0, 1) or stream URL (e.g. http://192.168.100.2:8080/video)",
    )
    args = parser.parse_args()

    print("=" * 72)
    print(" OfficeVision AI - Step 3: Posture & Intentional Gesture Recognition")
    print("=" * 72)

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
    print(f"[INFO] Loaded workstation zone(s): {[w.id for w in workstations]}")

    # 3. Initialize Analyzers
    posture_classifier = PostureClassifier()
    gesture_detector = GestureDetector(required_hold_frames=10, cooldown_seconds=8.0)

    # 4. Open Camera Stream
    cap = open_camera_stream(args.source)
    if cap is None or not cap.isOpened():
        print(f"[CRITICAL] Could not open camera source '{args.source}'.")
        sys.exit(1)

    window_name = "OfficeVision AI - Step 3: Posture & Hand-Raise Gesture Recognition"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse_click)

    print("\n[INFO] Controls & Shortcuts:")
    print("  - Raise your right hand above your head to trigger intentional gesture!")
    print("  - Press [1], [2], [3], [4] when dialog appears to select voluntary status")
    print("  - Press [x] to dismiss gesture dialog")
    print("  - Press [c] to Calibrate desk zone | [s] to Save points | [r] to Reset")
    print("  - Press [q] to Quit\n")

    prev_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]

            # Run Pose Inference
            results = model(frame, verbose=False)
            annotated_frame = results[0].plot()

            # Process Detections
            person_in_desk = False
            current_posture = "UNKNOWN"
            gesture_status = None
            detected_anchors = []

            if results[0].keypoints is not None and results[0].keypoints.data is not None:
                kpts_data = results[0].keypoints.data.cpu().numpy()
                boxes_data = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else None

                for idx, person_kpts in enumerate(kpts_data):
                    bbox = boxes_data[idx] if (boxes_data is not None and idx < len(boxes_data)) else None
                    anchor_x, anchor_y, anchor_label = calculate_body_anchor(person_kpts, bbox)
                    detected_anchors.append((anchor_x, anchor_y))

                    # Check desk occupancy for this person
                    is_in_zone = workstations[0].is_point_inside((anchor_x, anchor_y), w, h)
                    if is_in_zone:
                        person_in_desk = True

                        # Classify Posture (Seated vs Standing)
                        posture, conf, diag = posture_classifier.classify(person_kpts, bbox, h, w)
                        current_posture = posture

                        # Process Intentional Gesture
                        triggered, gesture_status = gesture_detector.process_frame(person_kpts, person_is_in_desk=True)

                        # Draw Anchor
                        ax, ay = int(anchor_x), int(anchor_y)
                        cv2.drawMarker(annotated_frame, (ax, ay), (0, 255, 255), cv2.MARKER_CROSS, 16, 2)
                        cv2.putText(
                            annotated_frame,
                            f"{posture} ({anchor_label})",
                            (ax + 10, ay - 5),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.50,
                            (0, 255, 255),
                            1,
                            cv2.LINE_AA,
                        )

            # If no person at desk, decay gesture detector
            if not person_in_desk:
                _, gesture_status = gesture_detector.process_frame(None, person_is_in_desk=False)

            # Update Workstation Display
            zone = workstations[0]
            zone.is_occupied = person_in_desk
            annotated_frame = zone.draw(annotated_frame)

            # Dynamic Desk Badge Label with Posture
            badge_text = f"{zone.id}: VACANT"
            badge_color = (40, 140, 255)  # Orange
            if zone.is_occupied:
                badge_text = f"{zone.id}: OCCUPIED ({current_posture})"
                badge_color = (0, 230, 100) if current_posture == "SEATED" else (255, 210, 0)

            pts = zone.get_pixel_polygon(w, h)
            bx = max(10, min(pts[0][0][0], w - 280))
            by = max(30, min(pts[0][0][1] - 10, h - 10))
            (tw, th), bl = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.60, 2)
            cv2.rectangle(annotated_frame, (bx - 6, by - th - 6), (bx + tw + 6, by + bl), (20, 20, 20), -1)
            cv2.rectangle(annotated_frame, (bx - 6, by - th - 6), (bx + tw + 6, by + bl), badge_color, 1)
            cv2.putText(annotated_frame, badge_text, (bx, by), cv2.FONT_HERSHEY_SIMPLEX, 0.60, badge_color, 2, cv2.LINE_AA)

            # Render Gesture Progress Bar & Feedback
            if gesture_status:
                right_up = gesture_status.get("right_hand_up", False)
                progress = gesture_status.get("right_progress", 0.0)
                in_cooldown = gesture_status.get("in_cooldown", False)
                cooldown_sec = gesture_status.get("cooldown_remaining", 0.0)

                # Bottom gesture status bar
                bar_x1, bar_y1 = 20, h - 60
                bar_w, bar_h = 280, 20
                bar_x2 = bar_x1 + bar_w
                bar_y2 = bar_y1 + bar_h

                cv2.rectangle(annotated_frame, (bar_x1 - 5, bar_y1 - 25), (bar_x2 + 5, bar_y2 + 5), (20, 20, 20), -1)

                if in_cooldown:
                    cv2.putText(
                        annotated_frame,
                        f"Gesture Cooldown: {cooldown_sec}s",
                        (bar_x1, bar_y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.50,
                        (140, 140, 255),
                        1,
                        cv2.LINE_AA,
                    )
                    cv2.rectangle(annotated_frame, (bar_x1, bar_y1), (bar_x2, bar_y2), (60, 60, 60), 1)
                else:
                    is_stretching = gesture_status.get("is_stretching", False)
                    action_label = gesture_status.get("action_label", "Gesture: Raise Right Hand Only")
                    if is_stretching:
                        lbl_color = (0, 165, 255)  # Orange indicator for stretching
                    elif right_up:
                        lbl_color = (0, 255, 255)  # Yellow when single right hand is charging
                    else:
                        lbl_color = (180, 180, 180)

                    cv2.putText(annotated_frame, action_label, (bar_x1, bar_y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, lbl_color, 1, cv2.LINE_AA)

                    # Draw progress fill
                    fill_w = int(bar_w * progress)
                    cv2.rectangle(annotated_frame, (bar_x1, bar_y1), (bar_x2, bar_y2), (60, 60, 60), 1)
                    if fill_w > 0 and not is_stretching:
                        cv2.rectangle(annotated_frame, (bar_x1, bar_y1), (bar_x1 + fill_w, bar_y2), (0, 230, 255), -1)

            # Render Active Confirmation Modal if waiting for voluntary input
            if gesture_detector.active_confirmation:
                render_gesture_dialog(annotated_frame, gesture_detector.active_confirmation, w, h)

            # Render Last Confirmed Event Badge
            if gesture_detector.last_confirmed_event:
                ev = gesture_detector.last_confirmed_event
                conf_txt = f"Status: {ev['selected_reason']} ({ev['confirmed_at']})"
                cv2.rectangle(annotated_frame, (w - 360, 15), (w - 15, 50), (20, 40, 20), -1)
                cv2.rectangle(annotated_frame, (w - 360, 15), (w - 15, 50), (0, 220, 100), 1)
                cv2.putText(annotated_frame, conf_txt, (w - 350, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 255, 120), 1, cv2.LINE_AA)

            # Top-Left HUD
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0.0
            prev_time = curr_time

            cv2.rectangle(annotated_frame, (10, 10), (320, 95), (20, 20, 20), -1)
            cv2.rectangle(annotated_frame, (10, 10), (320, 95), (0, 255, 128), 1)
            cv2.putText(annotated_frame, f"FPS: {fps:.1f} | People: {len(detected_anchors)}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2, cv2.LINE_AA)
            cv2.putText(annotated_frame, f"Desk State: {zone.id} -> {'OCCUPIED' if zone.is_occupied else 'VACANT'}", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated_frame, f"Posture: {current_posture}", (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1, cv2.LINE_AA)

            # Calibration Overlay (if active)
            if calibration_state.is_calibrating:
                cv2.rectangle(annotated_frame, (0, 0), (w, 40), (40, 20, 160), -1)
                cv2.putText(annotated_frame, f"CALIBRATION: Click 4 points ({len(calibration_state.clicked_points)}/4) | 's' Save | 'r' Reset", (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
                for pt in calibration_state.clicked_points:
                    cv2.circle(annotated_frame, pt, 5, (0, 0, 255), -1)

            # Display Frame
            cv2.imshow(window_name, annotated_frame)

            # Keyboard Shortcuts
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("\n[INFO] Exit signal received.")
                break
            elif key in [ord("1"), ord("2"), ord("3"), ord("4")]:
                key_char = chr(key)
                gesture_detector.select_reason(key_char)
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
