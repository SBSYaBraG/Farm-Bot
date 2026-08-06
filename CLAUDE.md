# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# FarmBot Project

## Overview
A precision farming robot controller with three subsystems:
- **Arduino firmware** (C++/PlatformIO) — drives 5 stepper motors across X/Y/Z axes
- **Raspberry Pi controller** (Python) — serial CLI to send commands to the Arduino
- **AI vision module** (Python/TensorFlow) — CNN-based lettuce health classifier (Healthy vs. Non-Healthy)

---

## Hardware

- **Board:** Arduino Mega 2560
- **Motors:** 5 stepper motors — XL, XR (synchronized), Y, ZL, ZR (synchronized)
- **Limit switches:** 3 (X: pin 26, Y: pin 24, Z: pin 22)
- **ALM pins:** XL=37, XR=39, Y=31, ZL=33, ZR=35
- **Serial baud rate:** 115200

### Key Pin Assignments (from `Config.h`)
| Axis | PUL | DIR | ENA |
|------|-----|-----|-----|
| X    | 51  | 53  | 49  |
| Y    | 50  | 52  | 48  |
| Z    | 42  | 44  | 40  |

---

## Arduino Firmware

### Build & Upload
Use PlatformIO:
```bash
cd Farm-Bot
pio run                    # compile only (no hardware needed)
pio run --target upload    # compile and flash to Arduino Mega
pio device monitor --baud 115200  # open serial monitor
```

### Serial Commands
| Command         | Action |
|-----------------|--------|
| `X####`         | Move X axis relative steps (e.g. `X1000`, `X-500`) |
| `Y####`         | Move Y axis relative steps |
| `Z####`         | Move Z axis relative steps |
| `PX25/50/75`    | Move X to absolute percentage position |
| `PY25/50/75`    | Move Y to absolute percentage position |
| `PZ25/50/75`    | Move Z to absolute percentage position |
| `H` / `HALL`    | Home all axes |
| `HX/HY/HZ`     | Home individual axis |
| `R` / `STATUS`  | Report current position and system status |
| `S` / `STOP`    | Emergency stop (immediate) |
| `S0` / `CLEAR`  | Resume after emergency stop |
| `ALM`           | Print per-motor ALM status |
| `HELP`          | Print command list |

### Safety
- `AUTO_HOME_ON_STARTUP true` — the system homes all axes 3 seconds after boot
- ALM monitoring runs every loop iteration (`monitorAllALM()`) — detects overcurrent, overvoltage, position errors
- Emergency stop halts all motion; `S0`/`CLEAR` is required to resume
- `BACKOFF_STEPS 1600` — after hitting a limit switch, motors back off before zeroing position
- ALM alarm types distinguished by blink pattern: overcurrent (1), overvoltage (2), position error (7)

---

## Raspberry Pi Controller

### Dependencies
```bash
pip install pyserial
```

### Run
```bash
python3 Pi/Pi_FarmBotController_Class.py   # interactive CLI
python3 Pi/test_connection.py              # automated test: STATUS → HALL → X500
```

- Auto-detects Arduino on `/dev/ttyACM*`, `/dev/ttyUSB*`, or `usbmodem*` (macOS)
- Ctrl+C triggers emergency stop; prompts to continue or exit
- Prompt shows `[READY]` or `[EMERGENCY]` status

---

## AI Vision Module

### Purpose
Binary CNN classifier trained on a Kaggle lettuce disease dataset to detect whether a lettuce plant is **Healthy** or **Non-Healthy**.

### Training (Google Colab)
- Dataset: `ashishjstar/lettuce-diseases` from Kaggle
- Split: 80% train / 10% validation / 10% test
- Input: 150×150 RGB images
- Architecture: 3× Conv2D+MaxPool → Flatten → Dense(512) → Dropout(0.5) → Sigmoid
- Output model: `healthy_vs_non_healthy_classifier.h5`

### Run inference
```python
classify_uploaded_image(model, "path/to/image.jpg")
```

---

## Architecture Notes

- All motor speed/safety constants are centralized in `Config.h` — change speeds, timeouts, and pin assignments there only.
- X and Z axes use two synchronized motors; commands to those axes move both motors together.
- `processCommand()` in `CommandProcessor.cpp` is the single entry point for all serial command parsing — all new commands go here.
- The AI module is independent from the motion control system and is not yet integrated into the main robot loop.
