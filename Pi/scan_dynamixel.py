"""
Dynamixel AX-18A Scanner
Scans the three most common AX-18A baudrates and IDs 0-20 on /dev/ttyUSB0
using both Protocol 1.0 and Protocol 2.0.
Prints every attempt in real time with raw error codes.
"""

import serial
import time

PORT      = "/dev/ttyUSB0"
BAUDRATES = [1000000, 57600, 115200]  # most common AX-18A baudrates
ID_RANGE  = range(0, 21)              # 0-20 (factory default is ID 1)
DELAY     = 0.1                       # seconds between each attempt

# ─── Protocol 1.0 ────────────────────────────────────────────────────────────

def _p1_checksum(packet_bytes):
    return (~sum(packet_bytes)) & 0xFF

def p1_build_ping(servo_id):
    length = 2  # INSTRUCTION + CHECKSUM
    cs = _p1_checksum([servo_id, length, 0x01])
    return bytes([0xFF, 0xFF, servo_id, length, 0x01, cs])

def p1_read_status(ser):
    """
    Returns (servo_id, error_byte) on valid response, or
    (None, raw_bytes) on garbled/partial data, or None on timeout.
    """
    header = ser.read(2)
    if len(header) == 0:
        return None                          # pure timeout
    if header != b'\xff\xff':
        return (None, header)               # garbage — return raw bytes
    id_byte = ser.read(1)
    if not id_byte:
        return (None, header)
    len_byte = ser.read(1)
    if not len_byte:
        return (None, header + id_byte)
    length = len_byte[0]
    rest = ser.read(length)
    if len(rest) < length:
        return (None, header + id_byte + len_byte + rest)
    error = rest[0]
    return (id_byte[0], error)

# ─── Protocol 2.0 ────────────────────────────────────────────────────────────

def _p2_crc(data):
    """CRC-16/CCITT-FALSE as specified by Robotis Protocol 2.0."""
    crc_table = [
        0x0000, 0x8005, 0x800F, 0x000A, 0x801B, 0x001E, 0x0014, 0x8011,
        0x8033, 0x0036, 0x003C, 0x8039, 0x0028, 0x802D, 0x8027, 0x0022,
        0x8063, 0x0066, 0x006C, 0x8069, 0x0078, 0x807D, 0x8077, 0x0072,
        0x0050, 0x8055, 0x805F, 0x005A, 0x804B, 0x004E, 0x0044, 0x8041,
        0x80C3, 0x00C6, 0x00CC, 0x80C9, 0x00D8, 0x80DD, 0x80D7, 0x00D2,
        0x00F0, 0x80F5, 0x80FF, 0x00FA, 0x80EB, 0x00EE, 0x00E4, 0x80E1,
        0x00A0, 0x80A5, 0x80AF, 0x00AA, 0x80BB, 0x00BE, 0x00B4, 0x80B1,
        0x8093, 0x0096, 0x009C, 0x8099, 0x0088, 0x808D, 0x8087, 0x0082,
        0x8183, 0x0186, 0x018C, 0x8189, 0x0198, 0x819D, 0x8197, 0x0192,
        0x01B0, 0x81B5, 0x81BF, 0x01BA, 0x81AB, 0x01AE, 0x01A4, 0x81A1,
        0x01E0, 0x81E5, 0x81EF, 0x01EA, 0x81FB, 0x01FE, 0x01F4, 0x81F1,
        0x81D3, 0x01D6, 0x01DC, 0x81D9, 0x01C8, 0x81CD, 0x81C7, 0x01C2,
        0x0140, 0x8145, 0x814F, 0x014A, 0x815B, 0x015E, 0x0154, 0x8151,
        0x8173, 0x0176, 0x017C, 0x8173, 0x0162, 0x8167, 0x816D, 0x0168,
        0x0120, 0x8125, 0x812F, 0x012A, 0x813B, 0x013E, 0x0134, 0x8131,
        0x8113, 0x0116, 0x011C, 0x8119, 0x0108, 0x810D, 0x8107, 0x0102,
        0x8303, 0x0306, 0x030C, 0x8309, 0x0318, 0x831D, 0x8317, 0x0312,
        0x0330, 0x8335, 0x833F, 0x033A, 0x832B, 0x032E, 0x0324, 0x8321,
        0x0360, 0x8365, 0x836F, 0x036A, 0x837B, 0x037E, 0x0374, 0x8371,
        0x8353, 0x0356, 0x035C, 0x8359, 0x0348, 0x834D, 0x8347, 0x0342,
        0x03C0, 0x83C5, 0x83CF, 0x03CA, 0x83DB, 0x03DE, 0x03D4, 0x83D1,
        0x83F3, 0x03F6, 0x03FC, 0x83F9, 0x03E8, 0x83ED, 0x83E7, 0x03E2,
        0x83A3, 0x03A6, 0x03AC, 0x83A9, 0x03B8, 0x83BD, 0x83B7, 0x03B2,
        0x0390, 0x8395, 0x839F, 0x039A, 0x838B, 0x038E, 0x0384, 0x8381,
        0x0280, 0x8285, 0x828F, 0x028A, 0x829B, 0x029E, 0x0294, 0x8291,
        0x82B3, 0x02B6, 0x02BC, 0x82B9, 0x02A8, 0x82AD, 0x82A7, 0x02A2,
        0x02E0, 0x82E5, 0x82EF, 0x02EA, 0x82FB, 0x02FE, 0x02F4, 0x82F1,
        0x82D3, 0x02D6, 0x02DC, 0x82D9, 0x02C8, 0x82CD, 0x82C7, 0x02C2,
        0x0220, 0x8225, 0x822F, 0x022A, 0x823B, 0x023E, 0x0234, 0x8231,
        0x8213, 0x0216, 0x021C, 0x8219, 0x0208, 0x820D, 0x8207, 0x0202,
    ]
    crc = 0
    for byte in data:
        i = ((crc >> 8) ^ byte) & 0xFF
        crc = ((crc << 8) ^ crc_table[i]) & 0xFFFF
    return crc

def p2_build_ping(servo_id):
    # Header: FF FF FD 00 | ID | LEN_L LEN_H | INST | CRC_L CRC_H
    # Payload length = 3 (INST byte + 2 CRC bytes)
    inst = 0x01
    pre_crc = [0xFF, 0xFF, 0xFD, 0x00, servo_id, 0x03, 0x00, inst]
    crc = _p2_crc(pre_crc)
    return bytes(pre_crc + [crc & 0xFF, (crc >> 8) & 0xFF])

def p2_read_status(ser):
    """
    Returns (servo_id, error_byte) on valid response, or
    (None, raw_bytes) on garbled data, or None on timeout.
    """
    header = ser.read(4)
    if len(header) == 0:
        return None
    if header[:3] != b'\xff\xff\xfd':
        return (None, header)
    servo_id = header[4] if len(header) > 4 else None
    # Read ID + LEN_L + LEN_H
    meta = ser.read(3)
    if len(meta) < 3:
        return (None, header + meta)
    sid = meta[0]
    payload_len = meta[1] | (meta[2] << 8)
    rest = ser.read(payload_len)
    if len(rest) < payload_len:
        return (None, header + meta + rest)
    # rest[0] = 0x55 (status inst), rest[1] = error byte
    error = rest[1] if len(rest) > 1 else 0xFF
    return (sid, error)

# ─── Scanner ─────────────────────────────────────────────────────────────────

def scan_baud(baudrate):
    """Scan all IDs with both protocols at the given baudrate."""
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
        print(f"  [ERROR] Cannot open {PORT}: {e}")
        return found

    with ser:
        for servo_id in ID_RANGE:
            for proto, build_fn, read_fn, label in [
                (1, p1_build_ping, p1_read_status, "P1"),
                (2, p2_build_ping, p2_read_status, "P2"),
            ]:
                print(f"  Trying baud={baudrate:>8}  ID={servo_id:>3}  {label} ... ", end="", flush=True)

                packet = build_fn(servo_id)
                ser.reset_input_buffer()
                ser.write(packet)
                # Half-duplex echo flush
                ser.read(len(packet))
                result = read_fn(ser)

                if result is None:
                    print("timeout")
                elif result[0] is None:
                    raw = result[1]
                    print(f"garbled  raw={raw.hex()}")
                else:
                    sid, err = result
                    status = "OK" if err == 0 else f"err=0x{err:02X}"
                    print(f"FOUND  ID={sid}  error=0x{err:02X}  [{status}]")
                    found.append((proto, sid, err))

                time.sleep(DELAY)

    return found

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    total_attempts = len(BAUDRATES) * len(ID_RANGE) * 2  # 2 protocols
    print("=" * 60)
    print(f"  Dynamixel AX-18A Scanner")
    print(f"  Port     : {PORT}")
    print(f"  IDs      : {min(ID_RANGE)}-{max(ID_RANGE)}  (expand ID_RANGE for full sweep)")
    print(f"  Baudrates: {BAUDRATES}")
    print(f"  Protocols: 1.0 and 2.0")
    print(f"  Delay    : {DELAY}s per attempt")
    est_sec = total_attempts * DELAY
  print(f"  Total    : {total_attempts} attempts (~{est_sec:.0f}s / {est_sec/60:.1f} min)")
    print("=" * 60 + "\n")

    all_found = {}
    for baud in BAUDRATES:
        print(f"\n{'─'*60}")
        print(f"  Baudrate: {baud} bps")
        print(f"{'─'*60}")
        found = scan_baud(baud)
        if found:
            all_found[baud] = found

    print("\n" + "=" * 60)
    print("  SCAN COMPLETE")
    print("=" * 60)
    if all_found:
        for baud, hits in all_found.items():
            for proto, sid, err in hits:
                print(f"  baud={baud}  Protocol {proto}.0  ID={sid}  error=0x{err:02X}")
    else:
        print("  No Dynamixel servos found.")
        print("  Check: power, wiring, and that /dev/ttyUSB0 is correct.")

if __name__ == "__main__":
    main()
