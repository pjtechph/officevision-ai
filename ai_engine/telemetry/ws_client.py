"""
OfficeVision AI - Edge WebSocket Telemetry Client
==================================================

Asynchronously streams live presence telemetry and verified event records
from the Edge AI Vision Engine to the FastAPI backend over WebSockets.

Features:
  - Non-blocking background worker thread (zero impact on video inference FPS).
  - Thread-safe outbound message queue.
  - Automatic reconnection with exponential backoff if backend restarts.
  - Graceful degradation: Continues camera processing even when backend is offline.
"""

import asyncio
import json
import queue
import threading
import time
from typing import Dict, Any, Optional
import websockets


class EdgeTelemetryClient:
    def __init__(self, server_ws_url: str = "ws://127.0.0.1:8000/api/v1/ws/ai-telemetry"):
        self.server_ws_url = server_ws_url
        self.message_queue: queue.Queue = queue.Queue(maxsize=100)
        self.is_connected = False
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._latest_frame_lock = threading.Lock()
        self._latest_frame_bytes: Optional[bytes] = None

    def start(self):
        """Starts the background asynchronous telemetry transmission loop."""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._worker_thread.start()
        print(f"[TELEMETRY CLIENT] Initialized background worker -> {self.server_ws_url}")

    def stop(self):
        """Stops the worker thread cleanly."""
        self._running = False

    def send_packet(self, data: Dict[str, Any]):
        """
        Enqueues a telemetry or event dictionary to be sent to the backend.
        Non-blocking: drops oldest packet if queue is full.
        """
        try:
            self.message_queue.put_nowait(data)
        except queue.Full:
            # Drop older packet to prevent stale backlog
            try:
                self.message_queue.get_nowait()
                self.message_queue.put_nowait(data)
            except Exception:
                pass

    def send_frame(self, frame_bytes: bytes):
        """
        Stores the newest JPEG frame for live browser streaming.
        Always overwrites previous frame to guarantee zero latency.
        """
        with self._latest_frame_lock:
            self._latest_frame_bytes = frame_bytes

    def _run_async_loop(self):
        """Thread target that sets up an asyncio event loop for WebSockets."""
        asyncio.run(self._connection_manager())

    async def _connection_manager(self):
        """Maintains persistent WebSocket connection with automatic backoff reconnection."""
        backoff_sec = 1.0
        while self._running:
            try:
                print(f"[TELEMETRY CLIENT] Connecting to {self.server_ws_url}...")
                async with websockets.connect(self.server_ws_url, ping_interval=20, ping_timeout=10, max_size=10_000_000) as ws:
                    self.is_connected = True
                    backoff_sec = 1.0  # Reset backoff on success
                    print("[TELEMETRY CLIENT] Connected to FastAPI WebSocket Gateway! Streaming active.")

                    while self._running:
                        sent_something = False

                        # 1. Send live video frame if available
                        frame_to_send = None
                        with self._latest_frame_lock:
                            if self._latest_frame_bytes is not None:
                                frame_to_send = self._latest_frame_bytes
                                self._latest_frame_bytes = None

                        if frame_to_send is not None:
                            await ws.send(frame_to_send)
                            sent_something = True

                        # 2. Drain pending telemetry and event packets
                        while not self.message_queue.empty():
                            try:
                                data = self.message_queue.get_nowait()
                                payload_json = json.dumps(data)
                                await ws.send(payload_json)
                                sent_something = True
                            except queue.Empty:
                                break

                        if not sent_something:
                            await asyncio.sleep(0.015)
                        else:
                            await asyncio.sleep(0.005)

            except Exception as e:
                self.is_connected = False
                # Backend is offline or restarting
                await asyncio.sleep(backoff_sec)
                backoff_sec = min(8.0, backoff_sec * 1.5)
