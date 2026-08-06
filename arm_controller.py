"""
FarmBot Arm Controller — raw Protocol 1.0 implementation
Scans /dev/cu.usbserial-AI0283MB for 7 AX-18A servos, prints positions,
then moves all to zero using individual WRITE packets (not SYNC WRITE).

Why raw instead of pypot:
  pypot uses SYNC WRITE (broadcast, no status response) for all register
  writes. On this half-duplex USB adapter the SYNC WRITE packets are
  silently lost. Individual WRITE (0x03) packets carry a confirmed status
  response, so we know each command was received and processed.

AX-18A key facts (Protocol 1.0):
  Position raw 0-1023 = 0-300° physical; center (150°) = raw 512 = 0° here
  Speed raw 0-1023; 0 = max speed; 97 rpm max ≈ 582 °/s @ 12 V
  Torque Limit = 0 → motor disabled; default EEPROM = 983; resets on overload
  Shutdown default 0x24 = overheating + overload bits → resets torque on fault
"""

import struct
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("[ERROR] pyserial not installed.  Run:  pip install pyserial")

PORT       = "/dev/cu.usbserial-AI0283MB"
BAUD       = 1000000
SERVO_IDS  = list(range(1, 8))
STEP_DEG         = 10    # degrees per increment — smaller = less peak current
MOVE_SPEED       = 30    # deg/s for distal joints (4-7)
MOVE_SPEED_HEAVY = 12    # deg/s for heavy base joints (1-3)
HEAVY_IDS        = {1, 2, 3}

# AX-18A register addresses
ADDR_TORQUE_ENABLE  = 24
ADDR_CW_SLOPE       = 28   # compliance slope — lower = stiffer = more torque
ADDR_CCW_SLOPE      = 29
ADDR_GOAL_POSITION  = 30
ADDR_MOVING_SPEED   = 32
ADDR_TORQUE_LIMIT   = 34
ADDR_PRESENT_POS    = 36
ADDR_MOVING         = 46
ADDR_PUNCH          = 48   # minimum motor output (RAM, safe to write)

# ── Protocol 1.0 helpers ─────────────────────────────────────────────────────

def _cs(data):
    return (~sum(data)) & 0xFF

def _build(servo_id, instruction, params=()):
    body = [servo_id, len(params) + 2, instruction, *params]
    return bytes([0xFF, 0xFF, *body, _cs(body)])

def _read_status(ser):
    """
    Read one Protocol 1.0 status packet sequentially.
    Matches the pattern in scan_dynamixel.py which is confirmed working.
    Returns (servo_id, error, data_bytes) or None on timeout/bad data.
    """
    header = ser.read(2)
    if len(header) < 2 or header != b'\xff\xff':
        return None
    id_byte = ser.read(1)
    if not id_byte:
        return None
    length_byte = ser.read(1)
    if not length_byte:
        return None
    length = length_byte[0]
    rest = ser.read(length)
    if len(rest) < length:
        return None
    error = rest[0]
    data  = rest[1:-1]   # params, excluding trailing checksum byte
    return (id_byte[0], error, bytes(data))

def _ping(ser, servo_id):
    pkt = _build(servo_id, 0x01)
    ser.reset_input_buffer()
    ser.write(pkt)
    return _read_status(ser) is not None

def _read_reg(ser, servo_id, address, length):
    pkt = _build(servo_id, 0x02, [address, length])
    ser.reset_input_buffer()
    ser.write(pkt)
    result = _read_status(ser)
    if result is None:
        return None
    _, _, data = result
    if length == 1:
        return data[0] if data else None
    if length == 2:
        return struct.unpack('<H', data[:2])[0] if len(data) >= 2 else None
    return data

def _write_reg(ser, servo_id, address, value, length=1):
    """Write register and confirm via status response. Returns error byte."""
    if length == 1:
        raw_bytes = [value & 0xFF]
    else:
        raw_bytes = [value & 0xFF, (value >> 8) & 0xFF]
    pkt = _build(servo_id, 0x03, [address, *raw_bytes])
    ser.reset_input_buffer()
    ser.write(pkt)
    result = _read_status(ser)
    if result is None:
        return 0xFF          # no response = communication error
    return result[1]         # error byte (0 = success)

# ── Unit conversions ─────────────────────────────────────────────────────────

def _deg_to_raw(deg):
    """Degrees (-150…+150) → AX raw position (0…1023)."""
    return max(0, min(1023, int((deg + 150.0) / 300.0 * 1023.0 + 0.5)))

def _raw_to_deg(raw):
    return raw / 1023.0 * 300.0 - 150.0

def _speed_to_raw(deg_s):
    """deg/s → raw speed (1…1023); 0 = max speed so we clamp to 1 minimum."""
    return max(1, min(1023, int(deg_s / 684.0 * 1023.0 + 0.5)))

# ── Per-servo helpers ─────────────────────────────────────────────────────────

def _arm(ser, sid):
    """Restore torque + torque_limit before each motion step."""
    _write_reg(ser, sid, ADDR_TORQUE_ENABLE, 1,    length=1)
    _write_reg(ser, sid, ADDR_TORQUE_LIMIT,  1023, length=2)
    if sid in HEAVY_IDS:
        # Stiffer compliance (8 vs default 32) = more torque applied near goal
        _write_reg(ser, sid, ADDR_CW_SLOPE,  8, length=1)
        _write_reg(ser, sid, ADDR_CCW_SLOPE, 8, length=1)
        # Higher punch = larger minimum output to overcome gravity + static friction
        _write_reg(ser, sid, ADDR_PUNCH, 150, length=2)

def _get_pos(ser, sid):
    raw = _read_reg(ser, sid, ADDR_PRESENT_POS, 2)
    return _raw_to_deg(raw) if raw is not None else None

def _set_goal(ser, sid, deg):
    raw = _deg_to_raw(deg)
    err = _write_reg(ser, sid, ADDR_GOAL_POSITION, raw, length=2)
    return err == 0

# ── Main scan + move logic ────────────────────────────────────────────────────

def scan(ser):
    """Ping IDs 1-7, return {id: position_deg} for all that respond."""
    found = {}
    for sid in SERVO_IDS:
        if _ping(ser, sid):
            pos = _get_pos(ser, sid)
            if pos is not None:
                found[sid] = pos
    return found

def move_to_zero(ser, sid, start_deg):
    """Move one servo to 0° in STEP_DEG increments with torque re-arm each step."""
    pos = start_deg
    step = 0
    speed = MOVE_SPEED_HEAVY if sid in HEAVY_IDS else MOVE_SPEED
    _write_reg(ser, sid, ADDR_MOVING_SPEED, _speed_to_raw(speed), length=2)

    while abs(pos) > 2.0:
        step += 1
        direction = -1 if pos > 0 else 1
        delta  = min(STEP_DEG, abs(pos))
        target = pos + direction * delta
        wait   = delta / speed + 0.6   # travel time + settle buffer

        print(f"      step {step}: {pos:+.1f}° → {target:+.1f}°  (wait {wait:.1f} s)")

        _arm(ser, sid)
        _set_goal(ser, sid, target)    # writes are confirmed via position read-back

        time.sleep(wait)

        actual = _get_pos(ser, sid)
        if actual is None:
            print(f"      [ERROR] lost contact with servo {sid}")
            break
        print(f"             actual: {actual:+.1f}°")

        if abs(actual - pos) < 1.0:
            print(f"      Servo {sid} is stuck — stopping.")
            break
        pos = actual

    final = _get_pos(ser, sid)
    return final if final is not None else pos


def main():
    print(f"FarmBot Arm Controller  |  port={PORT}  baud={BAUD}")
    print(f"Servos: {SERVO_IDS}  |  step={STEP_DEG}°  speed={MOVE_SPEED} °/s\n")

    try:
        ser = serial.Serial(
            port=PORT, baudrate=BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
    except serial.SerialException as exc:
        sys.exit(f"[ERROR] Cannot open {PORT}: {exc}")

    with ser:
        # --- Scan ---
        print("Scanning ...")
        positions = scan(ser)

        if not positions:
            sys.exit("[ERROR] No servos found. Check wiring and power.")

        print(f"\nFound {len(positions)}/{len(SERVO_IDS)} servo(s):")
        for sid in SERVO_IDS:
            if sid in positions:
                print(f"  Servo ID {sid:2d}  present position = {positions[sid]:+.1f} °")
            else:
                print(f"  Servo ID {sid:2d}  NOT FOUND")

        if len(positions) < len(SERVO_IDS):
            missing = sorted(set(SERVO_IDS) - set(positions))
            sys.exit(f"\n[ERROR] Missing servo ID(s): {missing} — fix chain before moving.")

        # --- Arm all servos first so every joint holds its position ---
        # Never disable torque on a joint that hasn't reached a safe position —
        # it will fall freely under gravity at large angles.
        print("\n[INFO] Arming all servos (torque + torque_limit) ...")
        for sid in SERVO_IDS:
            _arm(ser, sid)
            _write_reg(ser, sid, ADDR_MOVING_SPEED,
                       _speed_to_raw(MOVE_SPEED_HEAVY if sid in HEAVY_IDS else MOVE_SPEED),
                       length=2)

        # Move order: base joints first (1→2→3), then distal (4→5→6→7).
        # Base joints carry the most mass — zeroing them first reduces the
        # gravitational load on the distal joints when their turn comes.
        MOVE_ORDER = [1, 2, 3, 4, 5, 6, 7]
        print("\n[INFO] Moving to zero (base-first order, all joints holding) ...")
        finals = {}
        for sid in MOVE_ORDER:
            start = positions[sid]
            if abs(start) < 2.0:
                print(f"\n  Servo ID {sid:2d}  already at zero, skipping")
                finals[sid] = start
                continue
            print(f"\n  Servo ID {sid:2d}  {start:+.1f}° → 0° ...")
            # Re-arm before each joint in case a previous fault reset torque
            _arm(ser, sid)
            finals[sid] = move_to_zero(ser, sid, start)

        print("\n  Final positions:")
        for sid in SERVO_IDS:
            print(f"    Servo ID {sid:2d} → {finals.get(sid, positions.get(sid, 0)):+.1f} °")

    print("\n[DONE]")


if __name__ == "__main__":
    main()
