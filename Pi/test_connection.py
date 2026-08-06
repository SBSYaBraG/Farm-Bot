"""
FarmBot Connection Test
Tests: serial port detection → STATUS → home all axes → move X 500 steps
"""

import serial
import serial.tools.list_ports
import time
import sys

BAUD = 115200
CONNECT_WAIT = 5.0   # seconds for Arduino to boot from external power (USB carries data only)
CMD_TIMEOUT  = 30.0  # seconds to wait for a homing sequence to finish
READ_DRAIN   = 2.0   # seconds to drain leftover bytes after a command


def find_arduino_port():
    """Return the most likely Arduino port, or None."""
    ports = list(serial.tools.list_ports.comports())
    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device:30s}  {p.description}  [{p.hwid}]")

    # Priority order for macOS + Linux
    candidates = []
    for p in ports:
        dev = p.device
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(kw in dev for kw in ("usbmodem", "usbserial", "ttyACM", "ttyUSB")):
            candidates.insert(0, dev)          # highest priority
        elif "arduino" in desc or "2341" in hwid or "2a03" in hwid:
            candidates.insert(0, dev)
        elif "debug" not in dev.lower() and "bluetooth" not in dev.lower():
            candidates.append(dev)             # fallback (e.g. cu.X15)

    return candidates[0] if candidates else None


def read_all(ser, timeout=READ_DRAIN):
    """Drain all waiting bytes for `timeout` seconds; return decoded lines."""
    lines = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ser.in_waiting:
            line = ser.readline().decode(errors="replace").strip()
            if line:
                lines.append(line)
                deadline = time.time() + 0.5   # extend a bit after each line
        else:
            time.sleep(0.05)
    return lines


def send_command(ser, cmd, wait=CMD_TIMEOUT, done_marker=None):
    """Send cmd, print every response line until done_marker or timeout."""
    print(f"\n>>> Sending: {cmd!r}")
    ser.write((cmd + "\n").encode())
    time.sleep(0.1)

    deadline = time.time() + wait
    while time.time() < deadline:
        if ser.in_waiting:
            line = ser.readline().decode(errors="replace").strip()
            if line:
                print(f"    Arduino: {line}")
                if done_marker and done_marker.lower() in line.lower():
                    return True
        else:
            time.sleep(0.05)

    if done_marker:
        print(f"    [timeout waiting for {done_marker!r}]")
    return False


def main():
    print("=" * 55)
    print("FarmBot Connection Test")
    print("=" * 55)

    # ── 1. Find port ───────────────────────────────────────────
    port = find_arduino_port()
    if not port:
        print("\nERROR: No suitable serial port found.")
        print("Make sure the Arduino is plugged in via USB.")
        sys.exit(1)
    print(f"\nUsing port: {port}")

    # ── 2. Open connection ─────────────────────────────────────
    try:
        ser = serial.Serial(port, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR opening {port}: {e}")
        sys.exit(1)

    print(f"Port opened at {BAUD} baud. Waiting {CONNECT_WAIT}s for Arduino boot...")
    try:
        time.sleep(CONNECT_WAIT)
        # Quick sanity-check that the port is actually usable
        _ = ser.in_waiting
    except OSError as e:
        ser.close()
        print(f"ERROR: Port {port} opened but is not usable: {e}")
        print("Make sure the Arduino Mega is connected via USB (not Bluetooth/debug ports).")
        sys.exit(1)

    # Drain any boot messages (startup banner, auto-home output, etc.)
    boot_lines = read_all(ser, timeout=1.0)
    if boot_lines:
        print("\n--- Arduino boot output ---")
        for l in boot_lines:
            print(f"    {l}")

    # ── 3. STATUS ──────────────────────────────────────────────
    print("\n--- Step 1: STATUS ---")
    send_command(ser, "STATUS", wait=3.0)

    # ── 4. Home all axes ───────────────────────────────────────
    print("\n--- Step 2: Home all axes (HALL) ---")
    print("    [This may take up to 30 s — waiting for 'homing complete' …]")
    found = send_command(ser, "HALL", wait=CMD_TIMEOUT,
                         done_marker="complete")
    if not found:
        # Some firmware prints "Homing finished" or "Home" — read a bit more
        extra = read_all(ser, timeout=3.0)
        for l in extra:
            print(f"    Arduino: {l}")

    # ── 5. Move X 500 steps ────────────────────────────────────
    print("\n--- Step 3: Move X +500 steps ---")
    send_command(ser, "X500", wait=10.0, done_marker="done")

    # Drain any trailing output
    trailing = read_all(ser, timeout=1.5)
    for l in trailing:
        print(f"    Arduino: {l}")

    ser.close()
    print("\n" + "=" * 55)
    print("Test complete. Connection closed.")
    print("=" * 55)


if __name__ == "__main__":
    main()
