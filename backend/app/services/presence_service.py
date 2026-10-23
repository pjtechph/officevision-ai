"""
OfficeVision AI - Presence & Event Store Service
=================================================

Central operational store managing real-time desk occupancy,
multi-workstation monitoring, live JPEG video buffer, and historical event timelines.
"""

import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class PresenceService:
    def __init__(self, config_path: str = "config/workstations.json"):
        self.config_path = Path(config_path)
        self.workstations: Dict[str, Dict[str, Any]] = {}
        self.event_timeline: List[Dict[str, Any]] = []
        self.attendance_records: List[Dict[str, Any]] = []
        self.last_ai_heartbeat: float = 0.0
        self.system_start_time: float = time.time()
        
        # Live JPEG video streaming buffer
        self._frame_lock = threading.Lock()
        self._latest_jpeg_frame: Optional[bytes] = None
        self.load_workstations()

    def set_latest_frame(self, frame_bytes: bytes):
        """Sets the newest JPEG frame for browser MJPEG streaming."""
        with self._frame_lock:
            self._latest_jpeg_frame = frame_bytes

    def get_latest_frame(self) -> Optional[bytes]:
        """Retrieves the newest JPEG frame."""
        with self._frame_lock:
            return self._latest_jpeg_frame

    def load_workstations(self):
        """Loads workstation metadata and polygon coordinates from JSON config."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("workstations", []):
                wid = item["id"]
                self.workstations[wid] = {
                    "id": wid,
                    "name": item.get("name", wid),
                    "description": item.get("description", ""),
                    "polygon_normalized": item.get("polygon_normalized", []),
                    "current_state": "VACANT",
                    "active_track_id": None,
                    "time_in_state_sec": 0.0,
                    "last_updated": datetime.utcnow().strftime("%H:%M:%S"),
                }
            print(f"[SERVICE] Loaded {len(self.workstations)} workstation(s) from {self.config_path}")
        else:
            print(f"[WARN] Workstations config file {self.config_path} not found.")

    def reload_workstations(self):
        """Reloads workstations from disk, updating polygons and metadata while preserving runtime state."""
        if not self.config_path.exists():
            return
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        updated_ids = set()
        for item in data.get("workstations", []):
            wid = item["id"]
            updated_ids.add(wid)
            if wid in self.workstations:
                self.workstations[wid]["name"] = item.get("name", wid)
                self.workstations[wid]["description"] = item.get("description", "")
                self.workstations[wid]["polygon_normalized"] = item.get("polygon_normalized", [])
            else:
                self.workstations[wid] = {
                    "id": wid,
                    "name": item.get("name", wid),
                    "description": item.get("description", ""),
                    "polygon_normalized": item.get("polygon_normalized", []),
                    "current_state": "VACANT",
                    "active_track_id": None,
                    "time_in_state_sec": 0.0,
                    "last_updated": datetime.utcnow().strftime("%H:%M:%S"),
                }
        for wid in list(self.workstations.keys()):
            if wid not in updated_ids:
                del self.workstations[wid]
        print(f"[SERVICE] Reloaded {len(self.workstations)} workstation(s) from {self.config_path}")

    def _persist_workstations(self):
        """Saves current workstations dictionary to JSON config on disk."""
        data = {
            "camera_id": "CAM-01",
            "workstations": [
                {
                    "id": w["id"],
                    "name": w["name"],
                    "description": w.get("description", ""),
                    "polygon_normalized": w["polygon_normalized"],
                }
                for w in self.workstations.values()
            ],
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def update_telemetry(self, packet: dict):
        """Processes live telemetry packet from the AI Edge Inference Engine."""
        self.last_ai_heartbeat = time.time()
        for w_state in packet.get("workstation_states", []):
            wid = w_state.get("id")
            if wid in self.workstations:
                self.workstations[wid]["current_state"] = w_state.get("current_state", "VACANT")
                self.workstations[wid]["active_track_id"] = w_state.get("active_track_id")
                self.workstations[wid]["time_in_state_sec"] = w_state.get("time_in_state_sec", 0.0)
                self.workstations[wid]["last_updated"] = datetime.utcnow().strftime("%H:%M:%S")

    def record_event(self, event_data: dict):
        """Appends a verified state change event to the timeline."""
        event_entry = {
            "id": len(self.event_timeline) + 1,
            **event_data,
            "recorded_at": datetime.utcnow().isoformat() + "Z",
        }
        self.event_timeline.append(event_entry)
        if len(self.event_timeline) > 200:
            self.event_timeline.pop(0)

        return event_entry

    def record_check_in(self, employee_id_code: str, workstation_id: str, method: str = "BADGE_OR_WEB_PORTAL"):
        """Records a deliberate, verified attendance check-in for an employee."""
        record = {
            "id": len(self.attendance_records) + 1,
            "employee_id_code": employee_id_code,
            "workstation_id": workstation_id,
            "verification_method": method,
            "check_in_time": datetime.utcnow().isoformat() + "Z",
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        self.attendance_records.append(record)
        return record

    def update_polygon(self, workstation_id: str, polygon_normalized: List[List[float]]):
        """Updates and persists new polygon coordinates for a workstation."""
        if workstation_id not in self.workstations:
            return False

        self.workstations[workstation_id]["polygon_normalized"] = polygon_normalized
        self._persist_workstations()
        print(f"[SERVICE] Updated polygon for {workstation_id} saved to {self.config_path}")
        return True

    def update_workstation(
        self,
        wid: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        polygon_normalized: Optional[List[List[float]]] = None,
    ):
        """Updates workstation name, description, and/or polygon coordinates."""
        if wid not in self.workstations:
            return None

        if name is not None:
            self.workstations[wid]["name"] = name
        if description is not None:
            self.workstations[wid]["description"] = description
        if polygon_normalized is not None:
            self.workstations[wid]["polygon_normalized"] = polygon_normalized

        self._persist_workstations()
        print(f"[SERVICE] Updated workstation {wid}")
        return self.workstations[wid]

    def add_workstation(self, wid: str, name: str, polygon_normalized: List[List[float]], description: str = ""):
        """Adds a new workstation zone and saves to disk."""
        self.workstations[wid] = {
            "id": wid,
            "name": name,
            "description": description,
            "polygon_normalized": polygon_normalized,
            "current_state": "VACANT",
            "active_track_id": None,
            "time_in_state_sec": 0.0,
            "last_updated": datetime.utcnow().strftime("%H:%M:%S"),
        }
        self._persist_workstations()
        print(f"[SERVICE] Created new workstation {wid}")
        return self.workstations[wid]

    def delete_workstation(self, wid: str):
        """Removes a workstation zone and saves to disk."""
        if wid in self.workstations:
            del self.workstations[wid]
            self._persist_workstations()
            print(f"[SERVICE] Deleted workstation {wid}")
            return True
        return False

    def get_health_status(self) -> Dict[str, Any]:
        """Calculates system health, camera uptime, and AI connection status."""
        now = time.time()
        time_since_ai = now - self.last_ai_heartbeat
        is_ai_connected = (self.last_ai_heartbeat > 0) and (time_since_ai < 4.0)

        return {
            "status": "HEALTHY" if is_ai_connected else ("DEGRADED" if self.last_ai_heartbeat > 0 else "INITIALIZING"),
            "ai_vision_connected": is_ai_connected,
            "camera_status": "ONLINE" if is_ai_connected else "OFFLINE_OR_STANDBY",
            "seconds_since_last_heartbeat": round(time_since_ai, 1) if self.last_ai_heartbeat > 0 else None,
            "uptime_seconds": round(now - self.system_start_time, 1),
            "total_desks_registered": len(self.workstations),
            "total_events_recorded": len(self.event_timeline),
            "total_check_ins": len(self.attendance_records),
        }


presence_service = PresenceService()
