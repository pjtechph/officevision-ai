"""
OfficeVision AI - Workstation State Machine & Temporal Smoothing Engine
========================================================================

Implements hysteresis, anti-flicker debouncing, and posture smoothing
to eliminate false presence transitions and create reliable event timelines.
"""

import time
from collections import deque
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple


class WorkstationState:
    VACANT = "VACANT"
    OCCUPIED_SEATED = "OCCUPIED_SEATED"
    OCCUPIED_STANDING = "OCCUPIED_STANDING"
    UNKNOWN = "UNKNOWN"


class WorkstationStateMachine:
    """
    Finite State Machine (FSM) managing presence and posture for a single workstation.
    
    Anti-Flicker Mechanisms:
      1. Entry Debounce: Occupant must be detected for N consecutive frames before
         transitioning from VACANT to OCCUPIED.
      2. Exit Debounce (Grace Period): If the occupant steps away or camera drops
         keypoints, the system waits `exit_debounce_seconds` (default 3.0s) before
         marking the desk as VACANT.
      3. Posture Smoothing: Rolling majority voting across `posture_window_size` frames.
    """

    def __init__(
        self,
        workstation_id: str,
        entry_debounce_frames: int = 8,
        exit_debounce_seconds: float = 3.0,
        posture_window_size: int = 10,
    ):
        self.workstation_id = workstation_id
        self.entry_debounce_frames = entry_debounce_frames
        self.exit_debounce_seconds = exit_debounce_seconds
        self.posture_window_size = posture_window_size

        # Core State
        self.current_state = WorkstationState.VACANT
        self.active_track_id: Optional[int] = None
        self.state_entered_time = time.time()
        self.last_seen_time = time.time()

        # Debounce Counters
        self.entry_frame_counter = 0
        self.is_debouncing_exit = False
        self.exit_debounce_start_time = 0.0

        # Posture smoothing buffer
        self.posture_history: deque = deque(maxlen=posture_window_size)

        # Audit History (in-memory ring buffer)
        self.event_history: List[Dict[str, Any]] = []

    def _get_smoothed_posture(self) -> str:
        """Computes majority posture from rolling history."""
        if not self.posture_history:
            return "SEATED"
        seated_count = sum(1 for p in self.posture_history if p == "SEATED")
        standing_count = sum(1 for p in self.posture_history if p == "STANDING")
        return "STANDING" if standing_count > seated_count else "SEATED"

    def update(
        self,
        is_inside_zone: bool,
        track_id: Optional[int],
        instant_posture: str,
        confidence: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """
        Updates the state machine with per-frame detection inputs.
        
        Returns:
            A structured event dictionary if a confirmed state transition occurs,
            otherwise None.
        """
        now = time.time()
        event: Optional[Dict[str, Any]] = None

        if is_inside_zone:
            self.last_seen_time = now
            self.posture_history.append(instant_posture)
            smoothed_posture = self._get_smoothed_posture()

            # If we were in the middle of an exit debounce, cancel it!
            if self.is_debouncing_exit:
                self.is_debouncing_exit = False
                self.exit_debounce_start_time = 0.0

            # CASE 1: Currently VACANT -> Evaluating Entry
            if self.current_state == WorkstationState.VACANT:
                self.entry_frame_counter += 1
                if self.entry_frame_counter >= self.entry_debounce_frames:
                    # Verified Entry Transition
                    new_state = (
                        WorkstationState.OCCUPIED_SEATED
                        if smoothed_posture == "SEATED"
                        else WorkstationState.OCCUPIED_STANDING
                    )
                    event = self._transition_to(new_state, track_id, confidence, now)
                    self.entry_frame_counter = 0

            # CASE 2: Currently OCCUPIED -> Check Posture Changes (Seated <-> Standing)
            elif self.current_state in (WorkstationState.OCCUPIED_SEATED, WorkstationState.OCCUPIED_STANDING):
                self.active_track_id = track_id or self.active_track_id
                target_state = (
                    WorkstationState.OCCUPIED_SEATED
                    if smoothed_posture == "SEATED"
                    else WorkstationState.OCCUPIED_STANDING
                )
                if target_state != self.current_state:
                    # Verify posture change has consensus (at least 7 out of 10 frames)
                    recent_votes = sum(1 for p in self.posture_history if p == smoothed_posture)
                    if recent_votes >= 7:
                        event = self._transition_to(target_state, self.active_track_id, confidence, now)

        else:
            # Person NOT detected inside zone
            self.entry_frame_counter = max(0, self.entry_frame_counter - 1)

            # CASE 3: Currently OCCUPIED -> Evaluating Exit Debounce
            if self.current_state in (WorkstationState.OCCUPIED_SEATED, WorkstationState.OCCUPIED_STANDING):
                if not self.is_debouncing_exit:
                    self.is_debouncing_exit = True
                    self.exit_debounce_start_time = now

                # Check if grace period has expired
                elapsed_absence = now - self.exit_debounce_start_time
                if elapsed_absence >= self.exit_debounce_seconds:
                    # Verified Exit Transition
                    event = self._transition_to(WorkstationState.VACANT, None, confidence, now)
                    self.is_debouncing_exit = False
                    self.exit_debounce_start_time = 0.0
                    self.posture_history.clear()

        return event

    def _transition_to(
        self,
        new_state: str,
        track_id: Optional[int],
        confidence: float,
        timestamp: float,
    ) -> Dict[str, Any]:
        """Executes state transition, logs event, and updates internal timers."""
        old_state = self.current_state
        duration_in_old_state = timestamp - self.state_entered_time

        self.current_state = new_state
        self.active_track_id = track_id
        self.state_entered_time = timestamp

        event = {
            "event_type": "WORKSTATION_STATE_CHANGE",
            "workstation_id": self.workstation_id,
            "previous_state": old_state,
            "new_state": new_state,
            "track_id": track_id,
            "duration_in_prev_state_sec": round(duration_in_old_state, 1),
            "confidence": round(confidence, 2),
            "timestamp": timestamp,
            "formatted_time": datetime.fromtimestamp(timestamp).strftime("%H:%M:%S"),
        }

        self.event_history.append(event)
        # Keep last 50 events in memory
        if len(self.event_history) > 50:
            self.event_history.pop(0)

        print(
            f"[STATE MACHINE] {self.workstation_id}: {old_state} -> {new_state} "
            f"(Track: {track_id}, Prev Duration: {event['duration_in_prev_state_sec']}s)"
        )
        return event

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic state snapshot for HUD rendering."""
        now = time.time()
        time_in_state = now - self.state_entered_time

        debounce_sec_left = 0.0
        if self.is_debouncing_exit:
            debounce_sec_left = max(0.0, self.exit_debounce_seconds - (now - self.exit_debounce_start_time))

        return {
            "current_state": self.current_state,
            "active_track_id": self.active_track_id,
            "time_in_state_sec": round(time_in_state, 1),
            "is_debouncing_exit": self.is_debouncing_exit,
            "debounce_sec_left": round(debounce_sec_left, 1),
            "entry_progress": min(1.0, self.entry_frame_counter / float(self.entry_debounce_frames)),
            "recent_events": self.event_history[-4:],
        }
