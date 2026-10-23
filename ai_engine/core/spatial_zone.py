"""
OfficeVision AI - Spatial Zone & Point-in-Polygon Engine
=========================================================

Handles workstation polygon representations, coordinate normalization,
and point-in-polygon spatial intersection for presence detection.
"""

import json
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import cv2
import numpy as np


class WorkstationZone:
    """
    Represents an office workstation desk area defined by a polygon.
    Stores coordinates in normalized space (0.0 to 1.0) so they automatically
    scale to any camera resolution (640x480, 1280x720, 1080p, 4K).
    """

    def __init__(self, desk_id: str, name: str, polygon_normalized: List[List[float]], description: str = ""):
        self.id = desk_id
        self.name = name
        self.polygon_normalized = polygon_normalized
        self.description = description
        self.is_occupied = False
        self.occupant_count = 0

    def get_pixel_polygon(self, frame_w: int, frame_h: int) -> np.ndarray:
        """
        Converts normalized (0.0 - 1.0) vertices into absolute pixel coordinates (X, Y)
        for the given frame dimensions.
        """
        pts = []
        for nx, ny in self.polygon_normalized:
            px = int(nx * frame_w)
            py = int(ny * frame_h)
            pts.append([px, py])
        return np.array(pts, dtype=np.int32).reshape((-1, 1, 2))

    def is_point_inside(self, point_xy: Tuple[float, float], frame_w: int, frame_h: int) -> bool:
        """
        Performs Point-in-Polygon (PIP) testing using OpenCV's pointPolygonTest.
        Returns True if the point is strictly inside or on the boundary.
        """
        contour = self.get_pixel_polygon(frame_w, frame_h)
        # cv2.pointPolygonTest returns: +1 (inside), 0 (on edge), -1 (outside)
        result = cv2.pointPolygonTest(contour, (float(point_xy[0]), float(point_xy[1])), measureDist=False)
        return result >= 0

    def draw(self, frame: np.ndarray, alpha: float = 0.20, show_label: bool = True) -> np.ndarray:
        """
        Renders the workstation zone on the frame:
          - GREEN when Occupied
          - AMBER / ORANGE when Vacant
        Uses translucent alpha blending for a modern, non-obtrusive look.
        """
        h, w = frame.shape[:2]
        pts = self.get_pixel_polygon(w, h)

        # Color palette: BGR format
        if self.is_occupied:
            border_color = (0, 230, 100)      # Neon Green
            fill_color = (0, 200, 80)
            status_text = f"{self.id}: OCCUPIED"
        else:
            border_color = (40, 140, 255)     # Amber/Orange
            fill_color = (30, 100, 220)
            status_text = f"{self.id}: VACANT"

        # 1. Draw translucent overlay fill
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], fill_color)
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

        # 2. Draw crisp anti-aliased polygon boundary lines
        cv2.polylines(frame, [pts], isClosed=True, color=border_color, thickness=2, lineType=cv2.LINE_AA)

        # 3. Draw corner pin markers
        for pt in pts:
            px, py = pt[0]
            cv2.circle(frame, (px, py), 4, border_color, -1, lineType=cv2.LINE_AA)
            cv2.circle(frame, (px, py), 6, (255, 255, 255), 1, lineType=cv2.LINE_AA)

        # 4. Optional status badge near the top-left vertex of the polygon
        if show_label:
            top_left_pt = pts[0][0]
            badge_x = max(10, min(top_left_pt[0], w - 220))
            badge_y = max(30, min(top_left_pt[1] - 10, h - 10))

            # Badge background
            (text_w, text_h), baseline = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (badge_x - 6, badge_y - text_h - 6), (badge_x + text_w + 6, badge_y + baseline), (20, 20, 20), -1)
            cv2.rectangle(frame, (badge_x - 6, badge_y - text_h - 6), (badge_x + text_w + 6, badge_y + baseline), border_color, 1)

            cv2.putText(
                frame,
                status_text,
                (badge_x, badge_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                border_color,
                2,
                cv2.LINE_AA,
            )

        return frame


def calculate_body_anchor(keypoints: np.ndarray, bbox: Optional[List[float]] = None) -> Tuple[float, float, str]:
    """
    Computes the most reliable physical anchor point for a person to check desk presence.
    
    Anchor Hierarchy:
      1. Mid-Torso (Center between Shoulders and Hips) -> Ideal full-body anchor
      2. Projected Chest (Down from Mid-Shoulder)      -> Ideal when hips are occluded by desk
      3. Bounding Box Torso Center                     -> Fallback if keypoints have low confidence
    """
    # Keypoint indices in COCO 17-point schema:
    # 5: L-Shoulder, 6: R-Shoulder, 11: L-Hip, 12: R-Hip
    l_sh = keypoints[5]
    r_sh = keypoints[6]
    l_hp = keypoints[11]
    r_hp = keypoints[12]

    conf_thresh = 0.30
    shoulders_detected = l_sh[2] > conf_thresh and r_sh[2] > conf_thresh
    hips_detected = l_hp[2] > conf_thresh and r_hp[2] > conf_thresh

    if shoulders_detected and hips_detected:
        mid_sh_x = (l_sh[0] + r_sh[0]) / 2.0
        mid_sh_y = (l_sh[1] + r_sh[1]) / 2.0
        mid_hp_x = (l_hp[0] + r_hp[0]) / 2.0
        mid_hp_y = (l_hp[1] + r_hp[1]) / 2.0
        torso_x = (mid_sh_x + mid_hp_x) / 2.0
        torso_y = (mid_sh_y + mid_hp_y) / 2.0
        return (torso_x, torso_y, "Mid-Torso")

    elif shoulders_detected:
        # Hips are hidden behind desk: project downward from shoulders into upper torso
        mid_sh_x = (l_sh[0] + r_sh[0]) / 2.0
        mid_sh_y = (l_sh[1] + r_sh[1]) / 2.0
        shoulder_span = abs(r_sh[0] - l_sh[0])
        # Torso center is approximately 40% of shoulder span below the shoulder line
        torso_y = mid_sh_y + max(25.0, shoulder_span * 0.40)
        return (mid_sh_x, torso_y, "Projected-Chest")

    elif bbox is not None:
        # Fallback to center-bottom region of bounding box
        bx1, by1, bx2, by2 = bbox[:4]
        cx = (bx1 + bx2) / 2.0
        cy = by1 + (by2 - by1) * 0.60
        return (cx, cy, "BBox-Center")

    else:
        # Fallback to first available keypoint (e.g. nose)
        return (float(keypoints[0][0]), float(keypoints[0][1]), "Head-Nose")


def load_workstations_from_config(config_path: str = "config/workstations.json") -> List[WorkstationZone]:
    """
    Loads workstation zone polygon definitions from a JSON file.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    workstations = []
    for item in data.get("workstations", []):
        zone = WorkstationZone(
            desk_id=item["id"],
            name=item.get("name", item["id"]),
            polygon_normalized=item["polygon_normalized"],
            description=item.get("description", ""),
        )
        workstations.append(zone)

    return workstations


def save_workstations_to_config(workstations: List[WorkstationZone], config_path: str = "config/workstations.json"):
    """
    Saves updated workstation zones back to the JSON configuration file.
    """
    data = {
        "camera_id": "CAM-01",
        "workstations": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "polygon_normalized": w.polygon_normalized,
            }
            for w in workstations
        ],
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
