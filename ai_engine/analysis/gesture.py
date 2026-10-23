"""
OfficeVision AI - Intentional Gesture Recognition Module
=========================================================

Detects intentional hand-raise gestures using:
  1. Instantaneous joint kinematic rules (wrist above eye and shoulder).
  2. Multi-frame temporal persistence (requires continuous hold for N frames).
  3. Cooldown timers & duplicate suppression.
  4. Voluntary employee confirmation workflow (reasons are never auto-assigned).
"""

import time
from typing import Dict, Any, Tuple, Optional, List
import numpy as np


class GestureDetector:
    """
    Stateful detector for intentional hand-raise gestures.
    Maintains frame counters, cooldown timers, and confirmation dialog states.
    """

    BREAK_OPTIONS = {
        "1": "Restroom Break",
        "2": "Meeting / Discussion",
        "3": "Official Errand",
        "4": "General Coffee / Stretch Break",
    }

    def __init__(
        self,
        required_hold_frames: int = 10,
        cooldown_seconds: float = 8.0,
        confidence_threshold: float = 0.40,
    ):
        self.required_hold_frames = required_hold_frames
        self.cooldown_seconds = cooldown_seconds
        self.confidence_threshold = confidence_threshold

        # Tracking state
        self.right_hand_frame_count = 0
        self.left_hand_frame_count = 0
        self.last_triggered_time = 0.0

        # Voluntary Confirmation State
        self.active_confirmation: Optional[Dict[str, Any]] = None
        self.last_confirmed_event: Optional[Dict[str, Any]] = None

    def process_frame(
        self,
        keypoints: np.ndarray,
        person_is_in_desk: bool = True,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Processes a single frame of keypoints for a desk occupant.
        
        Returns:
            (gesture_triggered: bool, status_dict: dict)
        """
        now = time.time()
        time_since_last = now - self.last_triggered_time
        in_cooldown = time_since_last < self.cooldown_seconds
        cooldown_remaining = max(0.0, self.cooldown_seconds - time_since_last)

        status: Dict[str, Any] = {
            "right_hand_up": False,
            "left_hand_up": False,
            "right_progress": 0.0,
            "in_cooldown": in_cooldown,
            "cooldown_remaining": round(cooldown_remaining, 1),
            "triggered_now": False,
            "active_confirmation": self.active_confirmation,
            "last_confirmed": self.last_confirmed_event,
        }

        # Do not track gestures if no person detected or not at desk
        if keypoints is None or len(keypoints) < 17 or not person_is_in_desk:
            self.right_hand_frame_count = max(0, self.right_hand_frame_count - 1)
            self.left_hand_frame_count = max(0, self.left_hand_frame_count - 1)
            return False, status

        # Extract joints for Right Arm: 10: R-Wrist, 6: R-Shoulder, 2: R-Eye
        # Extract joints for Left Arm: 9: L-Wrist, 5: L-Shoulder, 1: L-Eye
        r_wrist = keypoints[10]
        r_shoulder = keypoints[6]
        r_eye = keypoints[2]
        nose = keypoints[0]

        l_wrist = keypoints[9]
        l_shoulder = keypoints[5]
        l_eye = keypoints[1]

        # Reference head level: use eye or nose
        head_ref_y = r_eye[1] if r_eye[2] > 0.3 else (nose[1] if nose[2] > 0.3 else r_shoulder[1] - 40)

        # 1. Right Hand Raised Kinematic Condition
        right_wrist_valid = r_wrist[2] > self.confidence_threshold
        right_shoulder_valid = r_shoulder[2] > self.confidence_threshold
        is_right_raised = False
        if right_wrist_valid and right_shoulder_valid:
            wrist_is_above_head = r_wrist[1] < head_ref_y
            wrist_is_well_above_shoulder = r_wrist[1] < (r_shoulder[1] - 30)
            if wrist_is_above_head and wrist_is_well_above_shoulder:
                is_right_raised = True

        # 2. Left Hand Raised Kinematic Condition
        left_wrist_valid = l_wrist[2] > self.confidence_threshold
        left_shoulder_valid = l_shoulder[2] > self.confidence_threshold
        is_left_raised = False
        if left_wrist_valid and left_shoulder_valid:
            l_wrist_above_head = l_wrist[1] < head_ref_y
            l_wrist_above_shoulder = l_wrist[1] < (l_shoulder[1] - 30)
            if l_wrist_above_head and l_wrist_above_shoulder:
                is_left_raised = True

        # 3. Two-Handed Stretching Discrimination
        # If BOTH hands are raised, occupant is stretching or yawning, NOT making an intentional gesture
        is_stretching = is_right_raised and is_left_raised
        is_intentional_right_raise = is_right_raised and not is_left_raised

        status["right_hand_up"] = is_right_raised
        status["left_hand_up"] = is_left_raised
        status["is_stretching"] = is_stretching
        status["is_intentional_right_raise"] = is_intentional_right_raise

        # Update multi-frame hold counter for intentional single-hand raise
        if is_stretching:
            # When stretching, rapidly reset gesture progress to prevent false trigger
            self.right_hand_frame_count = max(0, self.right_hand_frame_count - 3)
            status["action_label"] = "Stretching (Both Hands Up - Ignored)"
        elif is_intentional_right_raise and not in_cooldown:
            self.right_hand_frame_count += 1
            status["action_label"] = "HOLD RIGHT HAND UP..."
        else:
            # Decay gradually
            self.right_hand_frame_count = max(0, self.right_hand_frame_count - 2)
            status["action_label"] = "Gesture: Raise Right Hand Only"

        # Compute progress toward trigger threshold (0.0 to 1.0)
        progress = min(1.0, self.right_hand_frame_count / float(self.required_hold_frames))
        status["right_progress"] = progress

        # Check for trigger condition
        if self.right_hand_frame_count >= self.required_hold_frames and not in_cooldown:
            self.last_triggered_time = now
            self.right_hand_frame_count = 0  # Reset counter
            status["triggered_now"] = True
            status["in_cooldown"] = True
            status["cooldown_remaining"] = self.cooldown_seconds

            # Open voluntary employee confirmation prompt
            self.active_confirmation = {
                "gesture": "RIGHT_HAND_RAISE",
                "triggered_at": time.strftime("%H:%M:%S"),
                "status": "AWAITING_VOLUNTARY_SELECTION",
                "options": self.BREAK_OPTIONS,
            }
            status["active_confirmation"] = self.active_confirmation
            return True, status

        return False, status

    def select_reason(self, option_key: str) -> Optional[Dict[str, Any]]:
        """
        Records the employee's voluntary reason selection (1, 2, 3, or 4).
        """
        if not self.active_confirmation or option_key not in self.BREAK_OPTIONS:
            return None

        reason_text = self.BREAK_OPTIONS[option_key]
        event_record = {
            "gesture": self.active_confirmation["gesture"],
            "selected_reason": reason_text,
            "confirmed_at": time.strftime("%H:%M:%S"),
            "status": "CONFIRMED_BY_EMPLOYEE",
        }
        self.last_confirmed_event = event_record
        self.active_confirmation = None
        print(f"[AUDIT LOG] Voluntary Status Recorded: {reason_text} at {event_record['confirmed_at']}")
        return event_record

    def cancel_confirmation(self):
        """Cancels an active confirmation dialog (e.g. employee raised hand by accident)."""
        if self.active_confirmation:
            print("[AUDIT LOG] Gesture confirmation dismissed / canceled by employee.")
            self.active_confirmation = None
