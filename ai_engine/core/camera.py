"""
OfficeVision AI - Camera Stream Utility
======================================
Unified camera stream loader supporting:
  - Local USB / built-in webcams (DirectShow / MSMF)
  - IP Cameras / Network streams (HTTP MJPEG, RTSP, HLS)
  - Automatic URL normalization (e.g., http://<ip>:8080/ -> http://<ip>:8080/video)
  - Low-latency threaded frame-dropping capture (eliminates network buffer lag)
"""

import os
import sys
import time
import threading
import cv2
import numpy as np


class ThreadedRealtimeCapture:
    """
    Wraps cv2.VideoCapture to run frame acquisition in a dedicated background thread.
    
    Why this is critical for IP / Phone cameras:
      Network cameras push frames at 30 FPS. When YOLO inference runs at ~12 FPS,
      a standard synchronous `cap.read()` leaves ~18 unread frames in the socket
      buffer each second. Over time, latency accumulates into seconds or minutes!
      
      This threaded capture continuously discards stale queued frames and guarantees
      that the main loop always receives the single most recent frame (< 15ms old).
    """

    def __init__(self, cap: cv2.VideoCapture, name: str = "CameraStream"):
        self.cap = cap
        self.name = name
        self._latest_frame = None
        self._ret = False
        self._running = True
        self._lock = threading.Lock()
        self._new_frame_event = threading.Event()
        self.total_frames_received = 0
        self.last_frame_timestamp = 0.0

        # Prime with the first available frame
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self._latest_frame = frame
                self._ret = True
                self.last_frame_timestamp = time.time()
                self.total_frames_received = 1

        # Start background polling thread
        self._thread = threading.Thread(target=self._reader_loop, daemon=True, name=f"ThreadedCapture-{name}")
        self._thread.start()

    def _reader_loop(self):
        while self._running and self.cap.isOpened():
            # grab() quickly decodes headers without full color conversion if supported
            ret, frame = self.cap.read()
            if ret and frame is not None:
                now = time.time()
                with self._lock:
                    self._latest_frame = frame
                    self._ret = True
                    self.last_frame_timestamp = now
                    self.total_frames_received += 1
                self._new_frame_event.set()
            else:
                time.sleep(0.005)

    def read(self):
        """Returns (ret, frame) with the most recent frame captured."""
        with self._lock:
            if self._latest_frame is None:
                return False, None
            # Return a fast copy so background thread doesn't overwrite while inference runs
            return self._ret, self._latest_frame.copy()

    def isOpened(self):
        return self._running and self.cap.isOpened()

    def get(self, prop_id):
        return self.cap.get(prop_id)

    def set(self, prop_id, value):
        return self.cap.set(prop_id, value)

    def release(self):
        self._running = False
        self._new_frame_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


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


def open_camera_stream(source=None, threaded=True):
    """
    Opens video capture from an IP camera stream, video file, or local webcam.
    Automatically handles network stream protocols, Windows MSMF/DSHOW backends,
    and wraps in ThreadedRealtimeCapture to eliminate queue latency.
    """
    if source is None:
        source = os.environ.get("CAMERA_SOURCE", 0)

    source = normalize_camera_source(source)
    is_network_stream = isinstance(source, str) and source.startswith(("http://", "https://", "rtsp://"))

    raw_cap = None

    # 1. Network Stream (IP Camera, RTSP, HTTP MJPEG)
    if is_network_stream:
        print(f"[INFO] Connecting to IP Camera stream: {source}...")
        raw_cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        if not raw_cap.isOpened():
            raw_cap = cv2.VideoCapture(source)

        if not raw_cap.isOpened():
            print(f"[ERROR] Could not connect to IP camera at '{source}'.")
            return raw_cap

        # Minimize buffer size in OpenCV / ffmpeg
        raw_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Warmup and frame validation
        valid = False
        for _ in range(10):
            ret, test_frame = raw_cap.read()
            if ret and test_frame is not None:
                w = int(raw_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(raw_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"[SUCCESS] Connected to IP Camera! Resolution: {w}x{h}")
                valid = True
                break
            time.sleep(0.1)

        if not valid:
            print("[WARN] IP Camera opened but returned empty frames initially.")
    else:
        # 2. Local Hardware Webcam (Index 0, 1, etc.)
        source_idx = int(source) if isinstance(source, (int, str)) and str(source).isdigit() else 0
        backends = [
            (cv2.CAP_MSMF, "Media Foundation (CAP_MSMF)"),
            (cv2.CAP_DSHOW, "DirectShow (CAP_DSHOW)"),
            (cv2.CAP_ANY, "Default Backend (CAP_ANY)"),
        ]

        for backend_id, backend_name in backends:
            print(f"[INFO] Trying camera {source_idx} with {backend_name}...")
            cap_candidate = cv2.VideoCapture(source_idx, backend_id)
            if not cap_candidate.isOpened():
                continue

            valid = False
            for _ in range(5):
                ret, test_frame = cap_candidate.read()
                if ret and test_frame is not None:
                    if float(np.mean(test_frame)) > 1.0:
                        valid = True
                        break
                time.sleep(0.05)

            if valid:
                w = int(cap_candidate.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap_candidate.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"[SUCCESS] Connected via {backend_name}! Resolution: {w}x{h}")
                raw_cap = cap_candidate
                break
            else:
                cap_candidate.release()

        if raw_cap is None:
            print("[WARN] All hardware checks failed. Attempting fallback open...")
            raw_cap = cv2.VideoCapture(source_idx)

    if raw_cap is None or not raw_cap.isOpened():
        return raw_cap

    # For network streams, threaded frame-dropping is essential to prevent accumulating latency
    if threaded:
        return ThreadedRealtimeCapture(raw_cap, name=str(source))
    return raw_cap


# Alias for backwards compatibility
open_webcam = open_camera_stream

