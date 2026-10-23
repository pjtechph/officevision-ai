"""
OfficeVision AI - Step 1: Real-Time YOLO-Pose Webcam Verification
==================================================================

Purpose:
  1. Initialize connection to your local webcam using Windows Media Foundation (MSMF)
     with robust auto-fallback and sensor warmup.
  2. Load the lightweight Ultralytics YOLO-Pose model.
  3. Run real-time pose estimation on each frame.
  4. Render 17 skeletal keypoints, connecting bones, and bounding boxes.
  5. Display real-time frames-per-second (FPS) and person count.
  6. Print out keypoint coordinates to understand how the model represents
     human joints for posture and gesture detection in subsequent steps.

Controls:
  - Press 'q' while focused on the video window to safely exit.
"""

import sys
import time
import cv2
import numpy as np
from ultralytics import YOLO

# The 17 COCO keypoint names and indices used by Ultralytics Pose models
COCO_KEYPOINTS = [
    "Nose",           # 0
    "Left Eye",       # 1
    "Right Eye",      # 2
    "Left Ear",       # 3
    "Right Ear",      # 4
    "Left Shoulder",  # 5
    "Right Shoulder", # 6
    "Left Elbow",     # 7
    "Right Elbow",    # 8
    "Left Wrist",     # 9
    "Right Wrist",    # 10
    "Left Hip",       # 11
    "Right Hip",      # 12
    "Left Knee",      # 13
    "Right Knee",     # 14
    "Left Ankle",     # 15
    "Right Ankle",    # 16
]


def open_webcam(camera_index=0):
    """
    Attempts to open the webcam using multiple backends.
    On Windows 10/11, CAP_MSMF (Media Foundation) is the preferred native backend.
    Checks frame validity and brightness to ensure we don't get stuck with a black frame.
    """
    backends = [
        (cv2.CAP_MSMF, "Media Foundation (CAP_MSMF)"),
        (cv2.CAP_DSHOW, "DirectShow (CAP_DSHOW)"),
        (cv2.CAP_ANY, "Default Backend (CAP_ANY)"),
    ]

    for backend_id, backend_name in backends:
        print(f"[INFO] Trying to open camera {camera_index} with {backend_name}...")
        cap = cv2.VideoCapture(camera_index, backend_id)
        if not cap.isOpened():
            print(f"[WARN] Could not open camera with {backend_name}.")
            continue

        # Warm up camera sensor by reading a few initial frames (allows auto-exposure to stabilize)
        valid = False
        for _ in range(5):
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                brightness = float(np.mean(test_frame))
                # If brightness is > 1.0, sensor is receiving actual light (not stuck on black)
                if brightness > 1.0:
                    valid = True
                    break
            time.sleep(0.05)

        if valid:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[SUCCESS] Connected via {backend_name}! Native resolution: {w}x{h}")
            return cap
        else:
            print(f"[WARN] {backend_name} opened but returned black frames. Trying next backend...")
            cap.release()

    # If all fail, return a standard open attempt as final fallback
    print("[WARN] All verified checks failed. Attempting standard open as fallback...")
    return cv2.VideoCapture(camera_index)


def print_keypoint_summary(keypoints_data):
    """
    Prints a concise terminal summary of key joints (wrists, shoulders, hips)
    for the first detected person. This demystifies how the model sees the body.
    """
    if len(keypoints_data) == 0:
        return
    
    first_person_kpts = keypoints_data[0]
    left_wrist = first_person_kpts[9]
    right_wrist = first_person_kpts[10]
    left_shoulder = first_person_kpts[5]
    right_shoulder = first_person_kpts[6]
    
    print(
        f"[DEBUG] Person 0: "
        f"L-Wrist Y={left_wrist[1]:.1f} (conf={left_wrist[2]:.2f}) | "
        f"R-Wrist Y={right_wrist[1]:.1f} (conf={right_wrist[2]:.2f}) | "
        f"L-Shoulder Y={left_shoulder[1]:.1f} | R-Shoulder Y={right_shoulder[1]:.1f}",
        end="\r",
        flush=True,
    )


def main():
    print("=" * 65)
    print(" OfficeVision AI - Step 1: Real-Time YOLO-Pose Verification")
    print("=" * 65)

    # 1. Load the YOLO-Pose model
    model_name = "yolo26n-pose.pt"
    print(f"[INFO] Loading pose model: {model_name}...")
    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"[ERROR] Failed to load model '{model_name}': {e}")
        sys.exit(1)

    # 2. Open the camera stream with robust backend negotiation
    camera_index = 0
    cap = open_webcam(camera_index)

    if not cap.isOpened():
        print(f"[CRITICAL ERROR] Cannot open camera index {camera_index}.")
        print("Troubleshooting tips:")
        print("  1. Ensure no other application (Zoom, Teams, Camera app) is using the webcam.")
        print("  2. Verify Windows Camera Privacy Settings allow desktop apps to access the camera.")
        sys.exit(1)

    print("\n[INFO] Controls: Click the video window and press 'q' to quit.\n")

    prev_time = time.time()
    frame_count = 0

    try:
        while True:
            success, frame = cap.read()
            if not success or frame is None:
                print("\n[WARNING] Failed to grab video frame. Re-attempting...")
                time.sleep(0.05)
                continue

            frame_count += 1

            # 3. Perform Pose Inference
            results = model(frame, verbose=False)

            # 4. Draw skeletons and bounding boxes using Ultralytics built-in plot()
            annotated_frame = results[0].plot()

            # 5. Extract raw keypoint data for understanding and future logic
            person_count = 0
            if results[0].keypoints is not None and results[0].keypoints.data is not None:
                kpts_tensor = results[0].keypoints.data.cpu().numpy()
                person_count = len(kpts_tensor)
                
                # Print periodic coordinate debug every 30 frames
                if frame_count % 30 == 0 and person_count > 0:
                    print_keypoint_summary(kpts_tensor)

            # 6. Calculate real-time FPS
            current_time = time.time()
            elapsed = current_time - prev_time
            fps = 1.0 / elapsed if elapsed > 0 else 0.0
            prev_time = current_time

            # 7. Render on-screen HUD (Head-Up Display)
            hud_text_fps = f"OfficeVision AI | FPS: {fps:.1f}"
            hud_text_people = f"People Detected: {person_count}"
            hud_text_help = "Press 'q' to Quit"

            # Background rectangle for crisp text readability
            cv2.rectangle(annotated_frame, (10, 10), (360, 105), (20, 20, 20), -1)
            cv2.rectangle(annotated_frame, (10, 10), (360, 105), (0, 255, 128), 1)

            cv2.putText(
                annotated_frame,
                hud_text_fps,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 128),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                annotated_frame,
                hud_text_people,
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                annotated_frame,
                hud_text_help,
                (20, 95),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )

            # 8. Display the live video feed
            cv2.imshow("OfficeVision AI - Step 1: Live Pose Detection", annotated_frame)

            # 9. Wait 1 millisecond for 'q' key press
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:  # 'q' or Escape key
                print("\n[INFO] Exit signal received.")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")

    finally:
        # 10. Clean release of hardware and GUI resources
        print("[INFO] Releasing webcam...")
        cap.release()
        cv2.destroyAllWindows()
        print("[SUCCESS] Camera released and windows closed cleanly.")


if __name__ == "__main__":
    main()
