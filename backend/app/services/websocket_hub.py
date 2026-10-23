"""
OfficeVision AI - WebSocket Connection Hub
===========================================

Manages real-time WebSocket connections between:
  1. Edge AI Inference Engine (Telemetry Publisher & Command Receiver)
  2. Web Dashboard Frontends (Telemetry Subscribers)
"""

from typing import List, Set
from fastapi import WebSocket
import json


class WebSocketHub:
    """Central WebSocket broadcaster facilitating real-time UI synchronization."""

    def __init__(self):
        # Connected web browsers (dashboard subscribers)
        self.dashboard_clients: Set[WebSocket] = set()
        # Connected AI vision workers
        self.ai_workers: Set[WebSocket] = set()

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_clients.add(websocket)
        print(f"[WS HUB] Dashboard client connected. Total clients: {len(self.dashboard_clients)}")

    def disconnect_dashboard(self, websocket: WebSocket):
        self.dashboard_clients.discard(websocket)
        print(f"[WS HUB] Dashboard client disconnected. Total clients: {len(self.dashboard_clients)}")

    async def connect_ai_worker(self, websocket: WebSocket):
        await websocket.accept()
        self.ai_workers.add(websocket)
        print(f"[WS HUB] AI Edge Worker connected. Total workers: {len(self.ai_workers)}")

    def disconnect_ai_worker(self, websocket: WebSocket):
        self.ai_workers.discard(websocket)
        print(f"[WS HUB] AI Edge Worker disconnected. Total workers: {len(self.ai_workers)}")

    async def broadcast_to_dashboards(self, message: dict):
        """Dispatches telemetry data or events to all active dashboard frontends."""
        if not self.dashboard_clients:
            return

        payload = json.dumps(message)
        dead_sockets = set()

        for client in self.dashboard_clients:
            try:
                await client.send_text(payload)
            except Exception:
                dead_sockets.add(client)

        for dead in dead_sockets:
            self.dashboard_clients.discard(dead)

    async def send_to_ai_workers(self, message: dict):
        """Dispatches control commands (e.g. RELOAD_WORKSTATIONS) to connected Edge AI workers."""
        if not self.ai_workers:
            return

        payload = json.dumps(message)
        dead_sockets = set()

        for worker in self.ai_workers:
            try:
                await worker.send_text(payload)
            except Exception:
                dead_sockets.add(worker)

        for dead in dead_sockets:
            self.ai_workers.discard(dead)


ws_hub = WebSocketHub()
