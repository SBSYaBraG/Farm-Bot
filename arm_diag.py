"""
Diagnostic script — run this to find out why servos aren't moving.
Tests one servo at a time with explicit read-back at every step.
"""
import time
import pypot.dynamixel

PORT   = "/dev/cu.usbserial-AI0283MB"
BAUD   = 1000000
TEST_ID = 1   # change this if servo 1 is not reachable

with pypot.dynamixel.DxlIO(PORT, baudrate=BAUD) as io:

    print("=== Step 1: ping / model ===")
    found = io.scan([TEST_ID])
    print(f"  scan([{TEST_ID}]) → {found}")
    if not found:
        print("  Servo not found — stop here.")
        raise SystemExit

    model = io.get_model([TEST_ID])
    print(f"  model → {model}")

    print("\n=== Step 2: angle limits ===")
    limits = io.get_angle_limit([TEST_ID])
    print(f"  angle_limit → {limits}  (0,0 means wheel mode — no position control!)")

    print("\n=== Step 3: torque state before enable ===")
    te_before = io.is_torque_enabled([TEST_ID])
    print(f"  torque_enabled → {te_before}")

    print("\n=== Step 4: enable torque + read back ===")
    io.enable_torque([TEST_ID])
    time.sleep(0.15)
    te_after = io.is_torque_enabled([TEST_ID])
    print(f"  torque_enabled after enable → {te_after}")

    print("\n=== Step 5: torque limit ===")
    tl = io.get_torque_limit([TEST_ID])
    print(f"  torque_limit → {tl}  (0 = no torque even if enabled)")

    print("\n=== Step 6: current position ===")
    pos_before = io.get_present_position([TEST_ID])
    print(f"  present_position → {pos_before} °")

    print("\n=== Step 7: set goal position to 0° and read back ===")
    io.set_moving_speed({TEST_ID: 50})
    time.sleep(0.05)
    io.set_goal_position({TEST_ID: 0.0})
    print("  goal_position command sent")
    time.sleep(2.0)

    pos_after = io.get_present_position([TEST_ID])
    print(f"  present_position 2 s later → {pos_after} °")

    moved = abs(pos_after[0] - pos_before[0]) > 1.0
    print(f"\n  {'SERVO MOVED ✓' if moved else 'SERVO DID NOT MOVE ✗'}")
    if not moved:
        print("\n  Likely causes:")
        print("  - angle_limit = (0,0)  → wheel mode, no position control")
        print("  - torque_limit = 0     → torque physically disabled")
        print("  - torque_enabled still False → write packets not reaching servo")
        print("  - already at 0° (check pos_before)")
