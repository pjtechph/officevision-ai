"""
OfficeVision AI - Camera Stream Utility
======================================
Unified camera stream loader supporting:
  - Local USB / built-in webcams (DirectShow / MSMF)
  - IP Cameras / Network streams (HTTP MJPEG, RTSP, HLS)
  - Automatic URL normalization (e.g., http://<ip>:8080/ -> http://<ip>:8080/video)
  - Low-latency buffer tuning
"""

import os
import sys
import time
import cv2
import numpy as np


def normalize_camera_source(source):
    """
    Normalizes camera source. If an HTTP IP Webcam URL is provided without
    the stream endpoint (e.g. 'http://192.168.100.2:8080/'), automatically
    appends '/video'.
    """
    if source is None:
        source = os.environ.get("CAMERA_SOURCE", 0)

    if isinstance(source, str):
        source = source.strip()
        if source.isdigit():
            return int(source)
        
        # Check if URL
        if source.startswith(("http://", "https://", "rtsp://")):
            clean = source.rstrip("/")
            # If user provided root IP Webcam address without endpoint
            if clean.endswith(":8080") or (":8080" in clean and not clean.endswith(("/video", "/video.mjpg", "/shot.jpg"))):
                return f"{clean}/video"

    return source


def open_camera_stream(source=None):
    """
    Opens video capture from an IP camera stream, video file, or local webcam.
    Automatically handles network stream protocols and Windows MSMF/DSHOW backends.
    """
    if source is None:
        source = os.environ.get("CAMERA_SOURCE", 0)

    source = normalize_camera_source(source)

    # 1. Network Stream (IP Camera, RTSP, HTTP MJPEG)
    if isinstance(source, str) and source.startswith(("http://", "https://", "rtsp://")):
        print(f"[INFO] Connecting to IP Camera stream: {source}...")
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            print(f"[ERROR] Could not connect to IP camera at '{source}'.")
            return cap

        # Minimize buffer size to reduce stream lag
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Warmup and frame validation
        for _ in range(10):
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"[SUCCESS] Connected to IP Camera! Resolution: {w}x{h}")
                return cap
            time.sleep(0.1)

        print("[WARN] IP Camera opened but returned empty frames initially.")
        return cap

    # 2. Local Hardware Webcam (Index 0, 1, etc.)
    source_idx = int(source) if isinstance(source, (int, str)) and str(source).isdigit() else 0
    backends = [
        (cv2.CAP_MSMF, "Media Foundation (CAP_MSMF)"),
        (cv2.CAP_DSHOW, "DirectShow (CAP_DSHOW)"),
        (cv2.CAP_ANY, "Default Backend (CAP_ANY)"),
    ]

    for backend_id, backend_name in backends:
        print(f"[INFO] Trying camera {source_idx} with {backend_name}...")
        cap = cv2.VideoCapture(source_idx, backend_id)
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

    print("[WARN] All hardware checks failed. Attempting fallback open...")
    return cv2.VideoCapture(source_idx)


# Alias for backwards compatibility
open_webcam = open_camera_stream
