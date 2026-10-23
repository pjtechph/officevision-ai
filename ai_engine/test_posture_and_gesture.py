"""
Automated unit test for Step 3 Posture Classifier and Gesture Detector.
"""

import numpy as np
from analysis.posture import PostureClassifier
from analysis.gesture import GestureDetector


def test_posture_and_gesture():
    print("[TEST] Initializing PostureClassifier and GestureDetector...")
    posture_clf = PostureClassifier()
    gesture_det = GestureDetector(required_hold_frames=5, cooldown_seconds=2.0)

    # 1. Test Seated Posture
    mock_seated_kpts = np.zeros((17, 3), dtype=np.float32)
    # Shoulders at Y=280 (in a 480 high frame -> ratio ~ 0.58)
    mock_seated_kpts[5] = [260, 280, 0.9]
    mock_seated_kpts[6] = [360, 280, 0.9]
    posture, conf, _ = posture_clf.classify(mock_seated_kpts, bbox=None, frame_h=480, frame_w=640)
    assert posture == "SEATED", f"Expected SEATED, got {posture}"
    print(f"[TEST] Posture test: SEATED successfully classified (conf={conf})")

    # 2. Test Standing Posture (Shoulders rise to top third: Y=80 in a 480 high frame -> ratio ~ 0.16)
    mock_standing_kpts = np.zeros((17, 3), dtype=np.float32)
    mock_standing_kpts[5] = [260, 80, 0.9]
    mock_standing_kpts[6] = [360, 80, 0.9]
    posture, conf, _ = posture_clf.classify(mock_standing_kpts, bbox=None, frame_h=480, frame_w=640)
    assert posture == "STANDING", f"Expected STANDING, got {posture}"
    print(f"[TEST] Posture test: STANDING successfully classified (conf={conf})")

    # 3. Test Two-Handed Stretch Suppression (Both wrists above eyes)
    mock_stretch_kpts = np.zeros((17, 3), dtype=np.float32)
    mock_stretch_kpts[1] = [300, 150, 0.9]  # L-Eye
    mock_stretch_kpts[2] = [340, 150, 0.9]  # R-Eye
    mock_stretch_kpts[5] = [280, 200, 0.9]  # L-Shoulder
    mock_stretch_kpts[6] = [360, 200, 0.9]  # R-Shoulder
    mock_stretch_kpts[9] = [280, 80, 0.9]   # L-Wrist UP (Stretching)
    mock_stretch_kpts[10] = [360, 80, 0.9]  # R-Wrist UP (Stretching)

    stretch_triggered = False
    for frame_i in range(10):
        trig, status = gesture_det.process_frame(mock_stretch_kpts, person_is_in_desk=True)
        if trig:
            stretch_triggered = True

    assert stretch_triggered is False, "Raising BOTH hands should NOT trigger the gesture (Stretching suppressed)"
    assert status["is_stretching"] is True, "Status should identify state as stretching"
    print("[TEST] Two-handed stretching correctly identified and SUPPRESSED (No false positive!).")

    # 4. Test Intentional Single Right-Hand Raise Accumulation
    # Left wrist DOWN (at lap level: Y=350), Right wrist UP (above eye: Y=80)
    mock_gesture_kpts = np.zeros((17, 3), dtype=np.float32)
    mock_gesture_kpts[1] = [300, 150, 0.9]  # L-Eye
    mock_gesture_kpts[2] = [340, 150, 0.9]  # R-Eye
    mock_gesture_kpts[5] = [280, 200, 0.9]  # L-Shoulder
    mock_gesture_kpts[6] = [360, 200, 0.9]  # R-Shoulder
    mock_gesture_kpts[9] = [280, 350, 0.9]  # L-Wrist DOWN
    mock_gesture_kpts[10] = [360, 80, 0.9]  # R-Wrist UP (Deliberate single hand)

    triggered = False
    for frame_i in range(5):
        trig, status = gesture_det.process_frame(mock_gesture_kpts, person_is_in_desk=True)
        if trig:
            triggered = True
            print(f"[TEST] Hand-raise gesture triggered on frame {frame_i + 1}!")

    assert triggered is True, "Gesture should trigger after 5 consecutive frames"
    assert gesture_det.active_confirmation is not None, "Confirmation prompt should be open"
    print("[TEST] Voluntary confirmation modal activated.")

    # 4. Test Voluntary Reason Selection
    event = gesture_det.select_reason("1")  # Restroom Break
    assert event is not None, "Expected event record returned"
    assert event["selected_reason"] == "Restroom Break"
    assert event["status"] == "CONFIRMED_BY_EMPLOYEE"
    print(f"[TEST] Employee reason confirmed: {event['selected_reason']}")

    print("[TEST] All Step 3 automated tests PASSED successfully!")


if __name__ == "__main__":
    test_posture_and_gesture()
