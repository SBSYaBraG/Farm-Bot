"""
run.py - Entry point for the FarmBot web interface.

Usage:
    python run.py

Then open http://localhost:5000 on the Pi itself, or
http://<pi-ip-address>:5000 from any phone or laptop on the same WiFi.
(The Pi's address is printed at startup.)

THIS is the file where you choose which machine you are driving. Right now it
creates a SimulatedHardware, so nothing physical is involved and the interface
can be developed and demonstrated anywhere. When the real machine is wired up,
that single line becomes a serial-backed backend and nothing else in the
project needs to change.
"""

import os
import socket
import sys

# Make this directory importable so `import config` and `import hardware` work
# regardless of where the command was run from - a common annoyance when the
# same script is launched from a laptop, from the Pi, and later from systemd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config                                   # noqa: E402
from app import create_app                      # noqa: E402
from hardware import SimulatedHardware          # noqa: E402


def local_ip_address():
    """
    Best-effort guess at this machine's address on the local network, so we can
    print a URL that other devices can actually reach.

    Opening a UDP socket toward an external address does not send any traffic;
    it just makes the OS choose which network interface it would use, which
    tells us the relevant local address. This is more reliable than a hostname
    lookup, which often resolves to 127.0.0.1 on Linux.
    """
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        address = probe.getsockname()[0]
        probe.close()
        return address
    except OSError:
        return "127.0.0.1"


def main():
    # ---- Choose the hardware backend -------------------------------------
    # Swap this line for a serial-backed backend when the Arduino is connected.
    hardware = SimulatedHardware()
    hardware.start()

    app, socketio = create_app(hardware)

    ip = local_ip_address()
    print("=" * 60)
    print("  FarmBot Web Interface")
    print("=" * 60)
    print(f"  Mode:        {hardware.mode.upper()}")
    print(f"  On this Pi:  http://localhost:{config.SERVER_PORT}")
    print(f"  On the WiFi: http://{ip}:{config.SERVER_PORT}")
    print("=" * 60)
    print("  Press Ctrl+C to stop.")
    print()

    try:
        socketio.run(
            app,
            host=config.SERVER_HOST,
            port=config.SERVER_PORT,
            # The reloader would start a second copy of the process, giving us
            # two motion threads fighting over one simulated machine.
            use_reloader=False,
            # Silences a startup warning about the development server. This is
            # intentionally a small local server for one machine on a LAN, not
            # a public deployment.
            allow_unsafe_werkzeug=True,
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        hardware.stop()


if __name__ == "__main__":
    main()
