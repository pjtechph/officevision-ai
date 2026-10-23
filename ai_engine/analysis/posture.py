"""
OfficeVision AI - Posture Classification Module
================================================

Classifies workstation occupant posture as SEATED, STANDING, or UNKNOWN
using geometric joint kinematics, torso vertical position, and bounding box aspect ratio.
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np


class PostureClassifier:
    """
    Evaluates human skeletal keypoints and spatial positioning to determine
    whether a workstation occupant is SEATED or STANDING.
    
    Supports both:
      1. Full-Body Kinematics (when hips and knees are visible).
      2. Desk-Occluded Upper-Body Estimation (when lower body is occluded by the desk/chair).
    """

    def __init__(self, standing_shoulder_y_threshold: float = 0.32, aspect_ratio_threshold: float = 1.35):
        # Normalized threshold: If shoulders rise above this fraction of frame height,
        # occupant is likely standing up from their desk
        self.standing_shoulder_y_threshold = standing_shoulder_y_threshold
        self.aspect_ratio_threshold = aspect_ratio_threshold

    def classify(
        self,
        keypoints: np.ndarray,
        bbox: Optional[np.ndarray],
        frame_h: int,
        frame_w: int,
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        Classifies posture into ('SEATED' | 'STANDING' | 'UNKNOWN').
        
        Returns:
            (posture: str, confidence: float, diagnostics: dict)
        """
        diagnostics: Dict[str, Any] = {}

        if keypoints is None or len(keypoints) < 17:
            return "UNKNOWN", 0.0, {"reason": "Insufficient keypoints"}

        # Extract primary joints
        # 5: L-Shoulder, 6: R-Shoulder, 11: L-Hip, 12: R-Hip, 13: L-Knee, 14: R-Knee
        l_sh = keypoints[5]
        r_sh = keypoints[6]
        l_hp = keypoints[11]
        r_hp = keypoints[12]
        l_kn = keypoints[13]
        r_kn = keypoints[14]

        conf_thresh = 0.35
        shoulders_valid = l_sh[2] > conf_thresh and r_sh[2] > conf_thresh
        hips_valid = l_hp[2] > conf_thresh and r_hp[2] > conf_thresh
        knees_valid = l_kn[2] > conf_thresh or r_kn[2] > conf_thresh

        # --- Method 1: Full-Body Kinematics (Hips and Knees Visible) ---
        if hips_valid and knees_valid and shoulders_valid:
            mid_sh_y = (l_sh[1] + r_sh[1]) / 2.0
            mid_hp_y = (l_hp[1] + r_hp[1]) / 2.0
            knee_y = l_kn[1] if l_kn[2] > conf_thresh else r_kn[1]

            torso_height = abs(mid_hp_y - mid_sh_y)
            thigh_drop = abs(knee_y - mid_hp_y)

            # When seated, knees bend horizontally; thigh vertical drop is small compared to torso
            # When standing, thighs drop significantly
            ratio = thigh_drop / (torso_height + 1e-5)
            diagnostics["thigh_to_torso_ratio"] = round(ratio, 2)
            diagnostics["method"] = "full_body_kinematics"

            if ratio > 0.65:
                return "STANDING", 0.90, diagnostics
            else:
                return "SEATED", 0.88, diagnostics

        # --- Method 2: Upper-Body Desk-Occluded Estimation ---
        if shoulders_valid:
            mid_sh_y = (l_sh[1] + r_sh[1]) / 2.0
            normalized_shoulder_y = mid_sh_y / frame_h
            diagnostics["normalized_shoulder_y"] = round(normalized_shoulder_y, 3)

            # Calculate Bounding Box Aspect Ratio if available
            aspect_ratio = 1.0
            if bbox is not None and len(bbox) >= 4:
                bw = max(1.0, float(bbox[2] - bbox[0]))
                bh = max(1.0, float(bbox[3] - bbox[1]))
                aspect_ratio = bh / bw
                diagnostics["bbox_aspect_ratio"] = round(aspect_ratio, 2)

            diagnostics["method"] = "upper_body_occluded"

            # If shoulders are high up in the frame and bounding box is tall, person is standing
            is_high_in_frame = normalized_shoulder_y < self.standing_shoulder_y_threshold
            is_tall_aspect = aspect_ratio > self.aspect_ratio_threshold

            if is_high_in_frame and is_tall_aspect:
                return "STANDING", 0.82, diagnostics
            elif is_high_in_frame:
                # High in frame but broad (e.g. leaning forward or standing)
                return "STANDING", 0.75, diagnostics
            else:
                # Normal shoulder height within desk zone
                return "SEATED", 0.85, diagnostics

        # --- Fallback: Insufficient upper body visibility ---
        return "UNKNOWN", 0.40, {"reason": "Shoulders not clearly detected"}
