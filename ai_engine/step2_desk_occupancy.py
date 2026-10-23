"""
OfficeVision AI - Step 2: Desk Zones & Workspace Presence Detection
====================================================================

Purpose:
  1. Load configurable workstation polygon zones from `config/workstations.json`.
  2. Perform real-time YOLO-Pose inference.
  3. Compute accurate human body anchor points (Mid-Torso / Projected-Chest).
  4. Perform Point-in-Polygon (PIP) testing against desk zones.
  5. Dynamically classify and visualize desk states:
     - OCCUPIED (Translucent Green)
     - VACANT (Translucent Amber/Orange)
  6. Interactive Zone Calibration:
     - Press 'c' to enter calibration mode and click 4 custom polygon points.
     - Press 's' to save newly calibrated points to `config/workstations.json`.
     - Press 'r' to reset points.
     - Press 'q' to exit.
"""

import sys
import time
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

# Import our custom spatial zone module
from core.spatial_zone import (
    WorkstationZone,
    calculate_body_anchor,
    load_workstations_from_config,
    save_workstations_to_config,
)


class ZoneCalibrationState:
    """Manages interactive mouse clicking for drawing custom desk polygons."""
    def __init__(self):
        self.is_calibrating = False
        self.clicked_points = []  # List of (x, y) pixel coordinates

    def reset(self):
        self.clicked_points = []


calibration_state = ZoneCalibrationState()


def on_mouse_click(event, x, y, flags, param):
    """Mouse callback to record polygon points during calibration."""
    if not calibration_state.is_calibrating:
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        calibration_state.clicked_points.append((x, y))
        print(f"[CALIBRATION] Point {len(calibration_state.clicked_points)} recorded: ({x}, {y})")


def open_webcam(camera_index=0):
    """Initializes camera stream with Windows Media Foundation (MSMF) and sensor warmup."""
    backends = [
        (cv2.CAP_MSMF, "Media Foundation (CAP_MSMF)"),
        (cv2.CAP_DSHOW, "DirectShow (CAP_DSHOW)"),
        (cv2.CAP_ANY, "Default Backend (CAP_ANY)"),
    ]

    for backend_id, backend_name in backends:
        print(f"[INFO] Trying camera {camera_index} with {backend_name}...")
        cap = cv2.VideoCapture(camera_index, backend_id)
        if not cap.isOpened():
            continue

        valid = False
        for _ in range(5):
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                if float(np.mean(test_frame)) > 1.0:
                    valid = True
                    break
            time.sleep(0.05)

        if valid:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[SUCCESS] Connected via {backend_name}! Resolution: {w}x{h}")
            return cap
        else:
            cap.release()

    return cv2.VideoCapture(camera_index)


def main():
    print("=" * 68)
    print(" OfficeVision AI - Step 2: Desk Zones & Workspace Presence Detection")
    print("=" * 68)

    # 1. Load YOLO-Pose Model
    model_name = "yolo26n-pose.pt"
    print(f"[INFO] Loading pose model: {model_name}...")
    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"[ERROR] Failed to load model '{model_name}': {e}")
        sys.exit(1)

    # 2. Load Workstation Zones from Config
    config_file = "config/workstations.json"
    print(f"[INFO] Loading workstation definitions from {config_file}...")
    try:
        workstations = load_workstations_from_config(config_file)
        print(f"[INFO] Loaded {len(workstations)} workstation zone(s): {[w.id for w in workstations]}")
    except Exception as e:
        print(f"[ERROR] Failed to load workstations: {e}")
        sys.exit(1)

    # 3. Open Camera Stream
    cap = open_webcam(0)
    if not cap.isOpened():
        print("[CRITICAL] Could not open webcam.")
        sys.exit(1)

    window_name = "OfficeVision AI - Step 2: Desk Occupancy & Polygon Zones"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse_click)

    print("\n[INFO] Interactive Controls:")
    print("  - Focus on window and press 'q' to Quit")
    print("  - Press 'c' to Toggle Interactive Calibration Mode (Click 4 points to redraw desk)")
    print("  - Press 's' to Save calibrated polygon to config/workstations.json")
    print("  - Press 'r' to Reset points during calibration\n")

    prev_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]

            # 4. Run Pose Inference
            results = model(frame, verbose=False)

            # Draw skeletons & bounding boxes
            annotated_frame = results[0].plot()

            # 5. Extract Keypoints and Compute Body Anchors
            detected_anchors = []
            if results[0].keypoints is not None and results[0].keypoints.data is not None:
                kpts_data = results[0].keypoints.data.cpu().numpy()
                boxes_data = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else None

                for idx, person_kpts in enumerate(kpts_data):
                    bbox = boxes_data[idx] if (boxes_data is not None and idx < len(boxes_data)) else None
                    anchor_x, anchor_y, anchor_label = calculate_body_anchor(person_kpts, bbox)
                    detected_anchors.append((anchor_x, anchor_y, anchor_label))

                    # Render visual anchor target on the person's torso
                    ax, ay = int(anchor_x), int(anchor_y)
                    cv2.drawMarker(annotated_frame, (ax, ay), (0, 255, 255), cv2.MARKER_CROSS, 16, 2)
                    cv2.circle(annotated_frame, (ax, ay), 6, (0, 255, 255), 1)
                    cv2.putText(
                        annotated_frame,
                        f"Anchor: {anchor_label}",
                        (ax + 10, ay - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (0, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )

            # 6. Evaluate Workstation Occupancy via Point-in-Polygon
            occupied_count = 0
            for zone in workstations:
                # Check if any detected person anchor is inside this desk polygon
                occupants_in_zone = 0
                for ax, ay, _ in detected_anchors:
                    if zone.is_point_inside((ax, ay), w, h):
                        occupants_in_zone += 1

                zone.is_occupied = (occupants_in_zone > 0)
                zone.occupant_count = occupants_in_zone
                if zone.is_occupied:
                    occupied_count += 1

                # Draw the desk zone overlay
                annotated_frame = zone.draw(annotated_frame)

            # 7. Render Calibration Overlay (if active)
            if calibration_state.is_calibrating:
                cv2.rectangle(annotated_frame, (0, 0), (w, 50), (40, 20, 160), -1)
                calib_msg = (
                    f"CALIBRATION MODE: Click 4 desk corners ({len(calibration_state.clicked_points)}/4) "
                    "| 's' to Save | 'r' to Reset | 'c' to Cancel"
                )
                cv2.putText(annotated_frame, calib_msg, (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

                # Draw clicked points and connecting lines
                pts = calibration_state.clicked_points
                for i, pt in enumerate(pts):
                    cv2.circle(annotated_frame, pt, 6, (0, 0, 255), -1)
                    cv2.putText(annotated_frame, f"P{i+1}", (pt[0] + 8, pt[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                if len(pts) > 1:
                    for i in range(len(pts) - 1):
                        cv2.line(annotated_frame, pts[i], pts[i+1], (0, 255, 255), 2)
                if len(pts) >= 3:
                    cv2.line(annotated_frame, pts[-1], pts[0], (0, 200, 200), 1)

            # 8. Render HUD
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0.0
            prev_time = curr_time

            cv2.rectangle(annotated_frame, (10, 60 if calibration_state.is_calibrating else 10), (370, 175 if calibration_state.is_calibrating else 125), (20, 20, 20), -1)
            hud_y = 85 if calibration_state.is_calibrating else 35

            cv2.putText(annotated_frame, f"FPS: {fps:.1f} | People: {len(detected_anchors)}", (20, hud_y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2, cv2.LINE_AA)
            cv2.putText(annotated_frame, f"Desks Occupied: {occupied_count}/{len(workstations)}", (20, hud_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated_frame, "Controls: 'q'=Quit | 'c'=Calibrate Zone", (20, hud_y + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1, cv2.LINE_AA)

            # 9. Display Frame
            cv2.imshow(window_name, annotated_frame)

            # 10. Key Handling
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("\n[INFO] Exit signal received.")
                break
            elif key == ord("c"):
                calibration_state.is_calibrating = not calibration_state.is_calibrating
                calibration_state.reset()
                status_str = "ACTIVATED" if calibration_state.is_calibrating else "DEACTIVATED"
                print(f"[CALIBRATION] Calibration Mode {status_str}.")
            elif key == ord("r"):
                calibration_state.reset()
                print("[CALIBRATION] Points reset. Click 4 new points on the window.")
            elif key == ord("s"):
                if len(calibration_state.clicked_points) >= 3:
                    # Convert pixel points to normalized coordinates (0.0 to 1.0)
                    norm_pts = [[round(px / w, 4), round(py / h, 4)] for px, py in calibration_state.clicked_points]
                    workstations[0].polygon_normalized = norm_pts
                    save_workstations_to_config(workstations, config_file)
                    print(f"[CALIBRATION] Saved {len(norm_pts)} normalized vertices to {config_file}!")
                    calibration_state.is_calibrating = False
                    calibration_state.reset()
                else:
                    print("[CALIBRATION] Need at least 3 or 4 points to form a polygon before saving.")

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[SUCCESS] Camera released and windows closed cleanly.")


if __name__ == "__main__":
    main()
