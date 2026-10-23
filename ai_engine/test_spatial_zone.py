"""
Automated unit test for Step 2 spatial zone logic and point-in-polygon testing.
"""

import numpy as np
from core.spatial_zone import (
    WorkstationZone,
    calculate_body_anchor,
    load_workstations_from_config,
)


def test_spatial_zone():
    print("[TEST] Loading workstations from config/workstations.json...")
    workstations = load_workstations_from_config("config/workstations.json")
    assert len(workstations) >= 1, "Expected at least 1 workstation defined"
    zone = workstations[0]
    print(f"[TEST] Loaded zone '{zone.id}' with {len(zone.polygon_normalized)} vertices.")

    # Test pixel conversion
    w, h = 640, 480
    pts = zone.get_pixel_polygon(w, h)
    assert pts.shape[0] == len(zone.polygon_normalized), "Vertex count mismatch"

    # Test center point (should be inside)
    center_point = (w / 2.0, h / 2.0)
    inside = zone.is_point_inside(center_point, w, h)
    assert inside is True, f"Center point {center_point} should be inside workstation polygon"
    print(f"[TEST] Center point {center_point} correctly evaluated as INSIDE (True)")

    # Test extreme corner point (0, 0) (should be outside)
    corner_point = (10, 10)
    outside = zone.is_point_inside(corner_point, w, h)
    assert outside is False, f"Corner point {corner_point} should be outside workstation polygon"
    print(f"[TEST] Corner point {corner_point} correctly evaluated as OUTSIDE (False)")

    # Test body anchor calculation with mock keypoints (17, 3)
    mock_kpts = np.zeros((17, 3), dtype=np.float32)
    # L-Shoulder (idx 5) at (280, 200, 0.9), R-Shoulder (idx 6) at (360, 200, 0.9)
    mock_kpts[5] = [280, 200, 0.9]
    mock_kpts[6] = [360, 200, 0.9]
    ax, ay, label = calculate_body_anchor(mock_kpts)
    assert ax == 320.0, f"Expected mid-x at 320, got {ax}"
    assert ay > 200.0, f"Chest anchor should project downward from shoulder y=200, got {ay}"
    print(f"[TEST] Body anchor calculated: ({ax}, {ay}) [{label}]")

    print("[TEST] All Step 2 automated tests PASSED successfully!")


if __name__ == "__main__":
    test_spatial_zone()
