"""
OfficeVision AI - IP Camera Verification & Test Script
======================================================
Tests connection to an IP camera (e.g., Android IP Webcam at http://192.168.100.2:8080/),
captures live frames, and runs YOLO-Pose inference.
"""

import sys
import time
import argparse
import cv2
import numpy as np
from ultralytics import YOLO


def normalize_camera_source(source):
    """
    Normalizes camera source. If an HTTP IP Webcam URL is provided without
    the stream endpoint (e.g. 'http://192.168.100.2:8080/'), automatically
    appends '/video'.
    """
    if isinstance(source, str):
        source = source.strip()
        # Check if integer string
        if source.isdigit():
            return int(source)
        
        # If it's a URL
        if source.startswith(("http://", "https://", "rtsp://")):
            clean = source.rstrip("/")
            if clean.endswith(":8080") or (":8080" in clean and not clean.endswith(("/video", "/video.mjpg", "/shot.jpg"))):
                # IP Webcam standard endpoint
                return f"{clean}/video"
    return source


def open_camera_stream(source="http://192.168.100.2:8080/video"):
    source = normalize_camera_source(source)
    print(f"[INFO] Connecting to camera source: {source}")

    if isinstance(source, str) and source.startswith(("http://", "https://", "rtsp://")):
        # IP Camera stream via FFMPEG backend
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
            
        if not cap.isOpened():
            print(f"[ERROR] Failed to open IP camera stream: {source}")
            return None
            
        # Minimize network buffer to reduce latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Verify first valid frame
        for _ in range(10):
            ret, frame = cap.read()
            if ret and frame is not None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"[SUCCESS] Connected to IP Camera! Resolution: {w}x{h}")
                return cap
            time.sleep(0.1)
            
        print("[ERROR] Stream opened, but no valid frame could be read.")
        cap.release()
        return None
    else:
        # Local USB / built-in webcam
        source_idx = int(source) if isinstance(source, (int, str)) and str(source).isdigit() else 0
        backends = [
            (cv2.CAP_MSMF, "Media Foundation (CAP_MSMF)"),
            (cv2.CAP_DSHOW, "DirectShow (CAP_DSHOW)"),
            (cv2.CAP_ANY, "Default Backend (CAP_ANY)"),
        ]
        for backend_id, backend_name in backends:
            cap = cv2.VideoCapture(source_idx, backend_id)
            if cap.isOpened():
                for _ in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None and float(np.mean(frame)) > 1.0:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        print(f"[SUCCESS] Connected to local camera via {backend_name}! Resolution: {w}x{h}")
                        return cap
                cap.release()
        return cv2.VideoCapture(source_idx)


def test_ip_camera(source="http://192.168.100.2:8080/video", num_frames=5):
    print("=" * 65)
    print(" OfficeVision AI - IP Camera Live Verification")
    print("=" * 65)

    cap = open_camera_stream(source)
    if cap is None or not cap.isOpened():
        print(f"[CRITICAL ERROR] Could not connect to {source}")
        return False

    print("[INFO] Loading YOLO-Pose model (yolo26n-pose.pt)...")
    model = YOLO("yolo26n-pose.pt")

    print(f"\n[INFO] Grabbing {num_frames} frames from IP camera and running inference...")
    for i in range(1, num_frames + 1):
        t0 = time.time()
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"[WARN] Frame {i}: Failed to read.")
            continue
        
        results = model(frame, verbose=False)
        dt = (time.time() - t0) * 1000
        
        persons = len(results[0].boxes) if results[0].boxes is not None else 0
        print(f"  Frame {i:02d}: Captured {frame.shape[1]}x{frame.shape[0]} | "
              f"Inference: {dt:.1f}ms ({1000/dt:.1f} FPS) | Persons detected: {persons}")

    cap.release()
    print("\n[SUCCESS] IP Camera stream and YOLO-Pose inference verified successfully!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test IP Camera with YOLO-Pose")
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default="http://192.168.100.2:8080/video",
        help="Camera source (URL or device index). Default: http://192.168.100.2:8080/video",
    )
    parser.add_argument("--frames", "-f", type=int, default=5, help="Number of test frames to capture")
    args = parser.parse_args()

    test_ip_camera(source=args.source, num_frames=args.frames)
