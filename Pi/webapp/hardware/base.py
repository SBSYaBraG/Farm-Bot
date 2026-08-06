"""
base.py - The hardware contract.

FarmBotHardware defines every operation the web interface is allowed to
perform on the machine. Each method corresponds directly to a command the
Arduino firmware already understands (see processCommand() in
Farm-Bot/lib/Motors_X/CommandProcessor.cpp), so the mapping stays obvious:

    move_relative(axis, steps)         ->  X1000  /  Y-500  /  Z800
    move_absolute_percent(axis, pct)   ->  PX25   /  PY50   /  PZ75
    home_axis(axis)                    ->  HX     /  HY     /  HZ
    home_all()                         ->  H      /  HALL
    emergency_stop()                   ->  S      /  STOP
    resume()                           ->  S0     /  CLEAR
    get_status()                       ->  R      /  STATUS   (+ ALM)

Any class implementing this interface can be dropped into the server. Today
that is SimulatedHardware; later it will be a serial-backed implementation.
Because the web layer only knows about this abstract class, swapping between
them is a single line in run.py and requires no changes to app.py or the
frontend at all.
"""

from abc import ABC, abstractmethod


class FarmBotHardware(ABC):
    """Abstract base class describing a controllable FarmBot."""

    # A short string identifying which backend this is ("simulated", "serial").
    # Surfaced in the UI as a badge so it is never ambiguous whether you are
    # looking at a simulation or driving the real machine - an important
    # distinction to keep visible when the interface can move real motors.
    mode = "abstract"

    # -------------------- MOTION --------------------

    @abstractmethod
    def move_relative(self, axis_id, steps):
        """
        Move an axis by a number of steps relative to where it currently is.

        Positive steps move away from home, negative move back toward it.
        Mirrors the firmware's X####/Y####/Z#### commands.
        """

    @abstractmethod
    def move_absolute_percent(self, axis_id, percent):
        """
        Move an axis to an absolute position given as a percentage of its
        total travel, where 0% is home and 100% is the far limit.

        Mirrors the firmware's PX##/PY##/PZ## commands.
        """

    # -------------------- HOMING --------------------

    @abstractmethod
    def home_axis(self, axis_id):
        """
        Home a single axis: drive it toward its limit switch, back off, and
        zero its position counter. Mirrors HX/HY/HZ.
        """

    @abstractmethod
    def home_all(self):
        """Home every axis in sequence. Mirrors H/HALL."""

    # -------------------- SAFETY --------------------

    @abstractmethod
    def emergency_stop(self):
        """
        Halt all motion immediately.

        Important behavioural detail that implementations must preserve: any
        move still in progress is ABANDONED, not paused. The real firmware
        breaks out of its blocking step loop when checkForEmergencyStop()
        returns true, so the remaining steps of that command are simply never
        executed. An implementation that resumed the interrupted move on
        release would be dangerously surprising - the operator pressed stop
        precisely because they wanted the machine to stop going where it was
        going.
        """

    @abstractmethod
    def resume(self):
        """
        Clear the emergency stop condition so new commands are accepted again.

        This only unlatches the stop; it does not restart anything. The
        operator must issue a fresh command to move. Mirrors S0/CLEAR.
        """

    # -------------------- STATE --------------------

    @abstractmethod
    def get_status(self):
        """
        Return a snapshot of the entire machine state as a JSON-safe dict.

        This is the single payload the browser renders from, so it contains
        everything the interface displays. Shape:

            {
              "mode": "simulated",
              "emergency_stop": False,
              "axes": {
                "x": {"steps": 12345, "mm": 2469.0, "percent": 42,
                      "homed": True, "moving": False},
                ...
              },
              "alm": {"X": False, "YL": False, "YR": False, "Z": False},
              "alm_critical": False
            }

        Mirrors the information the firmware prints in reportStatus() and
        printALMStatus().
        """

    @abstractmethod
    def drain_log(self):
        """
        Return and clear any queued human-readable event lines.

        These are the equivalent of the firmware's Serial.println() output
        that the existing command-line controller prints as "Arduino: ...".
        The interface shows them in a scrolling console panel so the operator
        gets the same narrative feedback the terminal gives today.

        Returns a list of strings; empty if nothing new happened.
        """

    # -------------------- LIFECYCLE --------------------

    def start(self):
        """
        Begin whatever background work this backend needs (motion simulation
        thread, serial reader thread, ...). Optional - the default does
        nothing, since not every backend needs it.
        """

    def stop(self):
        """
        Shut down cleanly: stop threads, close ports. Optional.
        """
