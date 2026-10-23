"""
OfficeVision AI - Edge AI Vision Process Manager
=================================================

Provides lifecycle management (start, stop, restart, status, camera source)
for the local Edge AI Vision Service (`step5_integrated_ai_service.py`).
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional


class AIProcessManager:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self.camera_source: str = os.environ.get("CAMERA_SOURCE", "0")
        self.start_time: Optional[float] = None

        # Resolve path to step5_integrated_ai_service.py
        # backend/app/services -> YOLO-pose/ai_engine/step5_integrated_ai_service.py
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.script_path = root_dir / "ai_engine" / "step5_integrated_ai_service.py"

    def is_running(self) -> bool:
        if self._process is None:
            return False
        retcode = self._process.poll()
        return retcode is None

    def start_service(self, source: Optional[str] = None) -> Dict[str, Any]:
        """Starts the Edge AI Vision process in the background."""
        if source is not None and str(source).strip():
            self.camera_source = str(source).strip()

        if self.is_running():
            return {
                "status": "ALREADY_RUNNING",
                "message": "AI Vision Service is already running",
                "pid": self._process.pid,
                "camera_source": self.camera_source,
            }

        if not self.script_path.exists():
            return {
                "status": "ERROR",
                "message": f"AI service script not found at {self.script_path}",
            }

        env = os.environ.copy()
        env["CAMERA_SOURCE"] = self.camera_source

        # Launch non-blocking subprocess
        cwd = str(self.script_path.parent.parent)
        cmd = [sys.executable, str(self.script_path), "--source", self.camera_source]

        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.start_time = time.time()
            print(f"[PROCESS MANAGER] Started Edge AI Service (PID: {self._process.pid}, Source: {self.camera_source})")
            return {
                "status": "STARTED",
                "message": f"AI Vision Service started successfully on camera '{self.camera_source}'",
                "pid": self._process.pid,
                "camera_source": self.camera_source,
            }
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def stop_service(self) -> Dict[str, Any]:
        """Terminates the Edge AI Vision process."""
        if not self.is_running():
            return {"status": "STOPPED", "message": "AI Vision Service is not running"}

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1.0)

            pid = self._process.pid
            self._process = None
            self.start_time = None
            print(f"[PROCESS MANAGER] Stopped Edge AI Service (PID: {pid})")
            return {"status": "STOPPED", "message": f"AI Vision Service stopped (PID: {pid})"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def restart_service(self, source: Optional[str] = None) -> Dict[str, Any]:
        """Restarts the Edge AI Vision process, optionally with a new camera source."""
        self.stop_service()
        time.sleep(0.5)
        return self.start_service(source=source)

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state of the AI process."""
        running = self.is_running()
        uptime = round(time.time() - self.start_time, 1) if (running and self.start_time) else 0.0
        return {
            "running": running,
            "pid": self._process.pid if running else None,
            "camera_source": self.camera_source,
            "uptime_seconds": uptime,
        }


ai_process_manager = AIProcessManager()
