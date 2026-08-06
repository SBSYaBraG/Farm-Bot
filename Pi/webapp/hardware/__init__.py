"""
hardware - Backend implementations that the web interface drives.

The web layer (app.py) never talks to a motor directly. It only ever calls
methods on a FarmBotHardware object. That indirection is what lets us develop
the entire interface today, with no Arduino plugged in, and then switch to
real hardware later by changing which class we instantiate in run.py.

Currently available:
  SimulatedHardware - pure software motion model, no hardware required

Planned, once the physical machine is available:
  SerialHardware    - talks to the Arduino Mega over USB serial, reusing the
                      port-detection approach already proven in
                      Pi/test_connection.py and Pi_FarmBotController_Class.py
"""

from .base import FarmBotHardware
from .simulated import SimulatedHardware

__all__ = ["FarmBotHardware", "SimulatedHardware"]
