# Motors_Enc: 17HS19-2004-ME1K Bench Test

This library is a standalone test harness for the new 17HS19-2004-ME1K NEMA 17 stepper motor and its external magnetic encoder. It does not control the FarmBot gantry, use homing switches, or perform closed-loop correction.

## Why this test exists

The existing ICL motors contain their encoder and controller together, so the FarmBot controller cannot read or experiment with their feedback. The 17HS19-2004-ME1K exposes its magnetic encoder as separate A, B, and Z differential signal pairs. For this first bench test, the Arduino Mega reads the `+` side of each pair directly. This lets us verify the motor and learn from real encoder measurements before selecting the final PCB receiver and MCU.

## Goals

1. Confirm the TB6600 drives both motor coils correctly at 1.5 A.
2. Confirm command pulses move the shaft in both directions.
3. Confirm the encoder A and B signals change and produce a sensible quadrature count.
4. Confirm the Z index channel is visible once per revolution.
5. Compare commanded pulses against encoder counts at full step, then repeat at a known microstep setting.
6. Check low- and medium-speed ramping without a mechanical load.

This test does **not** claim final gantry accuracy, load torque, closed-loop correction, or noise immunity. The final PCB should use differential receivers for A/B/Z; reading only the `+` signals is a short, low-noise bench-test method.

## Required wiring

### Motor coils to TB6600

| 17HS19-2004-ME1K wire | TB6600 terminal |
| --- | --- |
| Red | A+ |
| Black | A- |
| Yellow | B+ |
| Blue | B- |

### Mega command pins to TB6600

| Mega | TB6600 terminal | Notes |
| --- | --- | --- |
| D39 | PUL+ | Step output |
| D43 | DIR+ | Direction output |
| GND | PUL-, DIR- | Common-cathode input return |
| D41 | ENA+ | Kept high impedance by the test firmware; not used yet |
| — | ENA- | Leave unconnected |

Set the TB6600 current to **1.5 A** and the microstep row to **400 pulses per revolution**. The program's default pulse-to-angle calculation now assumes that setting. Update `TB6600_PULSES_PER_REV` in `EncConfig.h` before testing another microstep setting.

### Encoder to Mega (temporary single-ended test)

| Encoder wire | Signal | Mega |
| --- | --- | --- |
| Red | VCC | 5V |
| Black | EGND | GND |
| Brown | EA+ | D2 |
| Blue | EB+ | D3 |
| Yellow | EZ+ | D20 |
| Orange | EA- | Insulate; do not connect |
| Green | EB- | Insulate; do not connect |
| White | EZ- | Insulate; do not connect |

Use short wiring and add a 1 kOhm series resistor between each encoder `+` output and the Mega input. D2, D3, and D20 all use external interrupts, so A/B quadrature edges and Z index rising edges are counted without polling. Do not use I2C while D20 is assigned to Z.

If the encoder uses a separate 5 V supply instead of the Mega's 5 V pin, connect that supply's 0 V terminal to Mega GND as well as encoder EGND. The Arduino needs this shared reference to read EA+/EB+/EZ+.

## Test sequence

1. Keep the shaft clear and test with no mechanical load.
2. Set the TB6600 to 1.5 A and 400 pulses/revolution.
3. Upload the `megaatmega2560-encoder-test` environment and open Serial Monitor at 115200 baud.
4. Send `STATUS`, then turn the shaft by hand and send `STATUS` again. A/B and the encoder count must change.
5. Send `ZERO`, then `F 400`. At the configured setting, the shaft should make roughly one revolution and the encoder magnitude should be near 4000 counts.
6. Send `ZERO`, then `R 400`. The encoder delta should reverse sign.
7. Send `ZERO`, then `RF 800 400` and `RR 800 400` for basic acceleration/deceleration checks.
8. Copy every `ENC_LOG` line from Serial Monitor into `readings_enc.csv` for review.

## Serial commands

| Command | Action |
| --- | --- |
| `HELP` | Print the command list |
| `STATUS` | Print encoder inputs, count, and index count |
| `ZERO` | Set encoder and index counts to zero |
| `F <pulses>` | Forward constant-speed move at 100 pulses/s |
| `R <pulses>` | Reverse constant-speed move at 100 pulses/s |
| `RF <pulses> <pps>` | Forward move with acceleration/deceleration |
| `RR <pulses> <pps>` | Reverse move with acceleration/deceleration |

Each completed move prints one CSV-compatible `ENC_LOG` row. The expected encoder count is based on 4000 encoder counts/revolution and the configured TB6600 pulses/revolution. A positive or negative encoder delta is valid; its sign depends on coil and encoder orientation.
