"""
Dynamixel AX-18A Scanner
Scans all common baudrates and IDs 1-10 on /dev/ttyUSB0
using Dynamixel Protocol 1.0 (instruction packet format).
"""

import serial
import time

PORT = "/dev/ttyUSB0"
BAUDRATES = [1000000, 57600, 115200, 9600, 4800, 19200, 38400]
ID_RANGE = range(1, 11)

# Protocol 1.0 constants
PING_INSTRUCTION = 0x01


def checksum(packet_bytes):
    """Protocol 1.0 checksum: ~(ID + LENGTH + ...) & 0xFF"""
    return (~sum(packet_bytes) & 0xFF)


def build_ping_packet(servo_id):
    """Build a Protocol 1.0 PING packet for the given ID."""
    # [0xFF, 0xFF, ID, LENGTH, INSTRUCTION, CHECKSUM]
    length = 2  # instruction + checksum
    cs = checksum([servo_id, length, PING_INSTRUCTION])
    return bytes([0xFF, 0xFF, servo_id, length, PING_INSTRUCTION, cs])


def read_status_packet(ser):
    """
    Read and parse a Protocol 1.0 status packet.
    Returns (servo_id, error_byte) on success, None on failure/timeout.
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
    return (id_byte[0], error)


def scan_baud(baudrate):
    """
    Open the port at the given baudrate and ping IDs 1-10.
    Returns a list of found IDs.
    """
    found = []
    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
    except serial.SerialException as e:
        print(f"  [ERROR] Could not open {PORT}: {e}")
        return found

    with ser:
        for servo_id in ID_RANGE:
            packet = build_ping_packet(servo_id)
            ser.reset_input_buffer()
            ser.write(packet)
            # AX-18A echoes the TX bytes at half-duplex — flush them
            ser.read(len(packet))
            result = read_status_packet(ser)
            if result is not None:
                sid, err = result
                found.append(sid)
                print(f"  [FOUND] ID {sid}  error_byte=0x{err:02X}")

    return found


def main():
    print(f"Dynamixel AX-18A scanner  |  port={PORT}  |  Protocol 1.0")
    print(f"Scanning IDs {min(ID_RANGE)}-{max(ID_RANGE)} at baudrates: {BAUDRATES}\n")

    results = {}
    for baud in BAUDRATES:
        print(f"Baudrate {baud:>8} bps ...")
        found = scan_baud(baud)
        if found:
            results[baud] = found
        else:
            print("  (no response)")

    print("\n--- Scan complete ---")
    if results:
        for baud, ids in results.items():
            print(f"  Baudrate {baud}: servo ID(s) {ids}")
    else:
        print("  No Dynamixel servos found.")
        print("  Check wiring, power, and that /dev/ttyUSB0 is the correct port.")


if __name__ == "__main__":
    main()
