"""
Automated unit test for Step 4 Workstation State Machine and Anti-Flicker Debounce.
"""

import time
from analysis.state_machine import WorkstationStateMachine, WorkstationState


def test_state_machine():
    print("[TEST] Initializing WorkstationStateMachine for DESK-01...")
    fsm = WorkstationStateMachine(
        workstation_id="DESK-01",
        entry_debounce_frames=4,    # Fast 4-frame threshold for unit test
        exit_debounce_seconds=1.0,  # 1.0s grace period for test speed
        posture_window_size=5,
    )

    assert fsm.current_state == WorkstationState.VACANT
    print("[TEST] Initial state is correctly VACANT.")

    # 1. Test Entry Debounce (Anti-false-arrival)
    # 3 frames inside should NOT trigger transition yet (needs 4)
    for _ in range(3):
        ev = fsm.update(is_inside_zone=True, track_id=1, instant_posture="SEATED")
        assert ev is None, "Should not transition before entry debounce frames reached"
        assert fsm.current_state == WorkstationState.VACANT

    # 4th frame inside should trigger OCCUPIED_SEATED
    ev = fsm.update(is_inside_zone=True, track_id=1, instant_posture="SEATED")
    assert ev is not None, "Expected state change event on 4th frame"
    assert ev["new_state"] == WorkstationState.OCCUPIED_SEATED
    assert ev["track_id"] == 1
    assert fsm.current_state == WorkstationState.OCCUPIED_SEATED
    print(f"[TEST] Entry Debounce passed: Verified transition to {ev['new_state']}.")

    # 2. Test Exit Debounce Grace Period (Anti-flicker)
    # Simulate occupant stepping out of zone for 0.4 seconds (less than 1.0s grace period)
    ev_out = fsm.update(is_inside_zone=False, track_id=None, instant_posture="UNKNOWN")
    assert ev_out is None, "Should not immediately transition to VACANT"
    assert fsm.is_debouncing_exit is True, "Exit debounce should be active"
    assert fsm.current_state == WorkstationState.OCCUPIED_SEATED
    print("[TEST] Grace period active: State remains OCCUPIED during temporary absence.")

    # Occupant returns at 0.5s -> debounce should cancel and presence remain unbroken!
    ev_back = fsm.update(is_inside_zone=True, track_id=1, instant_posture="SEATED")
    assert ev_back is None
    assert fsm.is_debouncing_exit is False, "Exit debounce should cancel upon return"
    assert fsm.current_state == WorkstationState.OCCUPIED_SEATED
    print("[TEST] Return within grace period confirmed: Presence remained unbroken.")

    # 3. Test Full Absence Beyond Grace Period
    # Step away and wait past 1.0s
    fsm.update(is_inside_zone=False, track_id=None, instant_posture="UNKNOWN")
    time.sleep(1.1)
    ev_vacant = fsm.update(is_inside_zone=False, track_id=None, instant_posture="UNKNOWN")
    assert ev_vacant is not None, "Expected VACANT transition event after grace period expired"
    assert ev_vacant["new_state"] == WorkstationState.VACANT
    assert ev_vacant["duration_in_prev_state_sec"] > 0.0
    assert fsm.current_state == WorkstationState.VACANT
    print(f"[TEST] Confirmed exit after grace period: Transitioned to VACANT (Duration: {ev_vacant['duration_in_prev_state_sec']}s).")

    # 4. Verify Event Schema Structure
    expected_keys = {"event_type", "workstation_id", "previous_state", "new_state", "track_id", "duration_in_prev_state_sec", "timestamp", "formatted_time"}
    for k in expected_keys:
        assert k in ev_vacant, f"Missing key '{k}' in event payload"
    print("[TEST] Event schema structure verified for WebSocket / Database telemetry.")

    print("[TEST] All Step 4 automated tests PASSED successfully!")


if __name__ == "__main__":
    test_state_machine()
