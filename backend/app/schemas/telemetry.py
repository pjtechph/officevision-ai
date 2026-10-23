"""
OfficeVision AI - Pydantic Schemas for Telemetry, Events & Workstations
========================================================================
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WorkstationZoneSchema(BaseModel):
    id: str = Field(..., example="DESK-01")
    name: str = Field(..., example="Workstation 1")
    description: Optional[str] = ""
    polygon_normalized: List[List[float]] = Field(..., description="[[x, y], ...] coordinates in 0.0-1.0 range")
    current_state: str = Field(default="VACANT", example="OCCUPIED_SEATED")
    active_track_id: Optional[int] = None
    time_in_state_sec: float = 0.0
    last_updated: Optional[str] = None


class TelemetryPacket(BaseModel):
    """Periodic real-time status packet sent from Edge AI Vision Engine."""
    camera_id: str = "CAM-01"
    fps: float
    tracked_people_count: int
    workstation_states: List[Dict[str, Any]]
    active_grace_period: bool = False
    grace_period_remaining: float = 0.0
    timestamp: float = Field(default_factory=datetime.utcnow().timestamp)
    iso_time: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class WorkstationEventSchema(BaseModel):
    """Structured event emitted on confirmed presence transitions."""
    event_type: str = Field(..., example="WORKSTATION_STATE_CHANGE")
    workstation_id: str = Field(..., example="DESK-01")
    previous_state: str
    new_state: str
    track_id: Optional[int] = None
    duration_in_prev_state_sec: float = 0.0
    confidence: float = 0.85
    timestamp: float
    formatted_time: str


class GestureEventSchema(BaseModel):
    """Voluntary employee gesture event."""
    event_type: str = "GESTURE_CONFIRMED"
    workstation_id: str
    gesture_type: str = "RIGHT_HAND_RAISE"
    selected_reason: str
    track_id: Optional[int] = None
    confirmed_at: str
    timestamp: float = Field(default_factory=datetime.utcnow().timestamp)


class EmployeeCheckInRequest(BaseModel):
    """Verified employee check-in (upholds privacy principle of separating identity from pose tracking)."""
    employee_id_code: str = Field(..., example="EMP-1042")
    workstation_id: str = Field(..., example="DESK-01")
    verification_method: str = Field(default="BADGE_OR_WEB_PORTAL", example="BADGE_OR_WEB_PORTAL")


class PolygonUpdateRequest(BaseModel):
    """Request payload to update desk boundary polygon vertices."""
    polygon_normalized: List[List[float]]
