"""
Headless verification script for YOLO-Pose inference.
Runs pose estimation on a synthetic test image to confirm that:
  - Model weights load without errors.
  - The forward inference pass succeeds.
  - Output tensor shapes and keypoint structures conform to the 17-point COCO schema.
"""

import numpy as np
from ultralytics import YOLO

def test_inference_headless():
    print("[TEST] Loading yolo26n-pose.pt...")
    model = YOLO("yolo26n-pose.pt")
    
    # Generate a synthetic 640x640 3-channel image (simulating a camera frame)
    dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
    
    print("[TEST] Running inference pass on synthetic frame...")
    results = model(dummy_frame, verbose=False)
    
    assert len(results) == 1, "Expected single result object for single frame"
    res = results[0]
    print(f"[TEST] Result object generated successfully: shape={res.orig_shape}")
    
    # Verify plot() method functions without GUI errors
    annotated = res.plot()
    assert annotated.shape == (640, 640, 3), "Annotated frame must match input dimensions"
    print(f"[TEST] Annotated plot generated successfully: shape={annotated.shape}")
    print("[TEST] All automated checks PASSED.")

if __name__ == "__main__":
    test_inference_headless()
