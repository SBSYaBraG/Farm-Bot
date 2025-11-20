# FarmBot X-Axis Control Interface

### Project Overview
This project enables a Raspberry Pi to control the X-axis of a FarmBot via an Arduino.  
The Arduino handles motors, encoders, and safety switches, while the Pi runs a Python interface to issue commands and monitor status.  
This is ideal for prototyping precision farming automation and safety-critical motion systems.


### How to Use This Program

1. **Startup & Detection**
   - Automatically searches for connected Arduino.
   - Displays available ports if not found.

2. **Command Reference**

| Type             | Command  | Description |
|------------------|----------|-------------|
| Movement         | `X####`  | Move relative steps (`X3200`, `X-500`) |
|                  | `P25`    | Go to 25% absolute position |
|                  | `P50`    | Go to 50% absolute position |
|                  | `P75`    | Go to 75% absolute position |
| System           | `H`      | Run homing sequence |
|                  | `R`      | Report current position & status |
|                  | `S`      | Emergency stop |
|                  | `S0`     | Resume after stop |
| Control          | `help`   | Show help menu |
|                  | `exit`/`quit` | Exit the program |

3. **What Happens When You Run the Code**
   - Prints system status (Arduino connection, commands).
   - Warns if Arduino is not found.
   - Allows emergency stop via keyboard or command.

### Project-Specific Arduino Files

- `main.cpp` – Arduino entry point
- `Config.h` – Shared system constants
- `SystemOperations.h/.cpp` – Emergency stop and state logic
- `CommandProcessor.h/.cpp` – Handles serial commands 
- `MotorControl.h/.cpp` – Stepper motor control logic
- `LimitSwitch.h/.cpp` – Handles mechanical limit switches
- `PositionManager.h/.cpp` – Tracks and updates current motor position

### Python Packages Used

- `serial` – Communicates with Arduino (`pyserial`)
- `time` – For synchronization delays
- `threading` – Reserved for future concurrency
- `sys`, `signal` – Terminal control, Ctrl+C handling
- `serial.tools.list_ports` – Automatically finds Arduino ports

### Recommended VS Code Extensions

| Extension               | Description |
|--------------------------|-------------|
| PlatformIO IDE           | Embedded development & upload to Arduino |
| Python, Pylance          | Python language support |
| Python Debugger          | Debugging for Python |
| Remote - SSH             | Remotely connect to Raspberry Pi |
| autoDocstring            | Auto-generate Python docstrings |

> For any startup issues, confirm your Arduino is connected and USB permissions are correctly set.
