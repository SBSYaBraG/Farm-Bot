"""
simulated.py - A FarmBot that exists entirely in software.

This lets us build and exercise the whole web interface with no Arduino, no
motors, and no wiring. It models the machine closely enough that the frontend
cannot tell the difference: axes take real time to travel, homing runs a
sequence, the emergency stop latches, and alarms can be raised.

How the motion model works
--------------------------
Rather than making a move command block until it finishes (which would freeze
the web server for the duration of a long traverse), each axis stores a
`target` position. A background thread wakes up SIM_TICK_HZ times a second and
nudges every axis a little closer to its target, based on how much real time
elapsed since the last tick. Commands are therefore instant to issue and the
motion plays out over time - exactly how it looks to a user watching the real
machine, and it keeps the server responsive enough to accept an emergency stop
mid-travel.
"""

import threading
import time

import config


class _Axis:
    """
    Simulated state of one axis.

    Positions are held in steps (not millimetres) because that is the unit the
    real firmware works in, so the simulation and the eventual serial backend
    agree on what a "position" is.
    """

    # The homing sequence the real firmware runs, as named phases. See
    # runHoming() in Farm-Bot/lib/Motors_X/SystemOperation.cpp - it does not
    # simply return to zero, it performs three distinct moves.
    HOME_SEEK_HOME = "seek_home"   # travel to the home limit switch
    HOME_SEEK_FAR = "seek_far"     # travel to the far limit, measuring travel
    HOME_CENTER = "center"         # settle at the middle of that travel

    def __init__(self, axis_id):
        self.axis_id = axis_id
        self.position = 0.0                        # current position, steps
        self.target = 0.0                          # where we are heading, steps
        self.max_steps = config.max_steps(axis_id)  # far limit, steps
        self.homed = False                         # has this axis been homed?
        # Which phase of the homing sequence is running, or None if not homing.
        self.home_phase = None

    @property
    def homing(self):
        """True while any phase of the homing sequence is in progress."""
        return self.home_phase is not None

    @property
    def moving(self):
        """True while the axis has not yet arrived at its target."""
        # Half a step of slack: floating-point stepping will not land exactly.
        return abs(self.target - self.position) > 0.5

    @property
    def percent(self):
        """Position as a whole-number percentage of total travel."""
        if self.max_steps <= 0:
            return 0
        return int(round(self.position / self.max_steps * 100))


class SimulatedHardware:
    """
    In-memory FarmBot. Implements the FarmBotHardware contract in base.py.

    Note this deliberately does not subclass FarmBotHardware via import-time
    inheritance checks that would force stub methods; it implements every
    abstract method for real. See base.py for what each one means.
    """

    mode = "simulated"

    def __init__(self):
        # One simulated axis per entry in config.AXES.
        self._axes = {axis_id: _Axis(axis_id) for axis_id in config.axis_ids()}

        # Emergency stop latch. While True, all motion is frozen and new
        # movement commands are refused until resume() is called.
        self._estop = False

        # Simulated alarm state, one flag per motor. On the real machine these
        # come from the stepper drivers' ALM pins; here they are only set by
        # the developer fault-injection controls, so we can build and test the
        # alarm UI without needing a genuine motor fault.
        self._alm = {name: False for name in config.all_motor_names()}

        # Queue of human-readable event lines awaiting delivery to browsers.
        self._log_lines = []

        # One lock guards every mutable field above. The motion thread and the
        # web server's request threads both touch this state concurrently.
        self._lock = threading.Lock()

        self._thread = None
        self._running = False

    # -------------------- LIFECYCLE --------------------

    def start(self):
        """Start the background motion thread."""
        if self._running:
            return
        self._running = True
        # daemon=True so this thread cannot keep the process alive after the
        # server shuts down.
        self._thread = threading.Thread(target=self._motion_loop, daemon=True)
        self._thread.start()
        self._log("Simulated FarmBot online. No physical hardware connected.")
        self._log("Axes are NOT homed - run Home All before positioning.")

    def stop(self):
        """Stop the background motion thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    # -------------------- MOTION THREAD --------------------

    def _motion_loop(self):
        """
        Advance every axis toward its target, forever, until stopped.

        Movement is computed from elapsed wall-clock time rather than assuming
        each tick is exactly 1/SIM_TICK_HZ seconds. If the machine is briefly
        busy and a tick runs late, the axis still travels the correct distance
        instead of falling behind.
        """
        tick_interval = 1.0 / config.SIM_TICK_HZ
        last_time = time.monotonic()

        while self._running:
            time.sleep(tick_interval)

            now = time.monotonic()
            elapsed = now - last_time
            last_time = now

            with self._lock:
                # While the emergency stop is latched nothing moves at all.
                if self._estop:
                    continue

                for axis in self._axes.values():
                    self._advance_axis(axis, elapsed)

    def _advance_axis(self, axis, elapsed_seconds):
        """
        Move one axis closer to its target. Caller must hold the lock.

        Returns nothing; mutates the axis in place.
        """
        if not axis.moving:
            # Arrived. If a homing sequence is running, this is where one phase
            # of it finishes and the next begins.
            if axis.homing:
                self._advance_homing(axis)
            return

        # How far we can travel this tick, converted from mm/s into steps/s.
        steps_per_mm = config.AXES[axis.axis_id]["steps_per_mm"]
        max_step_delta = config.SIM_SPEED_MM_S * steps_per_mm * elapsed_seconds

        remaining = axis.target - axis.position
        if abs(remaining) <= max_step_delta:
            # Close enough to land exactly on the target this tick.
            axis.position = axis.target
        else:
            # Travel as far as this tick allows, in the right direction.
            axis.position += max_step_delta if remaining > 0 else -max_step_delta

    def _advance_homing(self, axis):
        """
        Step the homing sequence to its next phase. Caller must hold the lock.

        This mirrors runHoming() in the Arduino firmware, which is a three-part
        sequence rather than a simple return to zero:

          1. Drive to the home limit switch and zero the position counter.
          2. Drive the other way to the far limit switch. The distance covered
             is what tells the machine how much travel the axis actually has.
          3. Drive back to the middle of that travel and stop there.

        The axis therefore comes to rest at 50%, NOT at home. That surprises
        most people - it certainly surprised this simulation, which used to
        park at 0% and would have had the interface showing the tool head in
        the wrong place the first time it drove real hardware.
        """
        name = axis.axis_id.upper()

        if axis.home_phase == _Axis.HOME_SEEK_HOME:
            # Reached the home switch. This is the moment position becomes
            # meaningful, so the counter is zeroed here.
            axis.position = 0.0
            axis.home_phase = _Axis.HOME_SEEK_FAR
            axis.target = float(axis.max_steps)
            self._log(f"{name} home limit found. Seeking far limit...")

        elif axis.home_phase == _Axis.HOME_SEEK_FAR:
            # Reached the far switch. On real hardware the travel distance is
            # discovered here; in simulation we already know it from config.py,
            # so we only report it.
            axis.home_phase = _Axis.HOME_CENTER
            axis.target = axis.max_steps / 2.0
            travel_mm = config.steps_to_mm(axis.axis_id, axis.max_steps)
            self._log(
                f"{name} far limit found. Total travel {int(axis.max_steps)} "
                f"steps ({travel_mm:.0f} mm). Moving to center..."
            )

        elif axis.home_phase == _Axis.HOME_CENTER:
            # Settled at mid-travel. Only now is the axis considered homed.
            axis.home_phase = None
            axis.homed = True
            self._log(f"{name} axis homed. Resting at center of travel (50%).")

    # -------------------- MOTION COMMANDS --------------------

    def move_relative(self, axis_id, steps):
        """Move an axis by `steps` relative to its current target."""
        with self._lock:
            if not self._check_ready(axis_id):
                return

            axis = self._axes[axis_id]

            # Clamp against the physical limits. The real machine has limit
            # switches that would stop it; here we refuse to exceed travel so
            # the simulation cannot wander outside the bed and confuse the map.
            requested = axis.target + steps
            clamped = max(0.0, min(float(axis.max_steps), requested))

            if clamped != requested:
                self._log(
                    f"{axis_id.upper()} move clamped to travel limit "
                    f"({int(clamped)} steps)."
                )

            # Commanding a move cancels any homing run still in progress on
            # this axis. See _cancel_homing() for why this matters.
            self._cancel_homing(axis)

            axis.target = clamped
            mm = config.steps_to_mm(axis_id, steps)
            self._log(f"{axis_id.upper()} move {steps:+d} steps ({mm:+.1f} mm)")

    def move_absolute_percent(self, axis_id, percent):
        """Move an axis to a percentage of its total travel (0-100)."""
        with self._lock:
            if not self._check_ready(axis_id):
                return

            axis = self._axes[axis_id]
            self._cancel_homing(axis)

            percent = max(0, min(100, int(percent)))
            axis.target = axis.max_steps * percent / 100.0
            self._log(f"{axis_id.upper()} move to {percent}% of travel")

    # -------------------- HOMING --------------------

    def home_axis(self, axis_id):
        """
        Home a single axis by driving it back to position zero.

        The real firmware seeks the limit switch, backs off BACKOFF_STEPS, then
        zeroes the counter. We model the observable result - the axis travels
        home and ends up zeroed - rather than the switch mechanics, which have
        no visible effect in the interface.
        """
        with self._lock:
            if self._estop:
                self._log("Cannot home: emergency stop is active. Send RESUME first.")
                return

            self._begin_homing(self._axes[axis_id])

    def home_all(self):
        """Home every axis."""
        with self._lock:
            if self._estop:
                self._log("Cannot home: emergency stop is active. Send RESUME first.")
                return

            self._log("Homing all axes...")
            for axis in self._axes.values():
                self._begin_homing(axis)

    def _begin_homing(self, axis):
        """
        Start the homing sequence on one axis. Caller must hold the lock.

        Clearing `homed` first is deliberate: until the sequence completes,
        the axis's position is not trustworthy, and the interface should say
        so rather than continuing to show a stale HOMED badge while the
        machine is mid-search. The firmware does the same thing, at
        SystemOperation.cpp:41.
        """
        axis.homed = False
        axis.home_phase = _Axis.HOME_SEEK_HOME
        axis.target = 0.0
        self._log(f"Homing {axis.axis_id.upper()} axis - seeking home limit...")

    # -------------------- SAFETY --------------------

    def emergency_stop(self):
        """
        Latch the emergency stop and abandon all in-flight motion.

        Setting each axis's target to its current position is what discards the
        remainder of any move. This matches the firmware: an interrupted move
        is gone, not paused, so releasing the stop never causes the machine to
        lurch off toward a destination the operator has forgotten about.
        """
        with self._lock:
            self._estop = True
            for axis in self._axes.values():
                axis.target = axis.position   # discard remaining travel
                axis.home_phase = None        # a cancelled homing run did not succeed
            self._log("*** EMERGENCY STOP ACTIVATED - all motion halted ***")

    def resume(self):
        """Unlatch the emergency stop. Does not restart anything."""
        with self._lock:
            self._estop = False
            self._log("Emergency stop cleared. Operations resumed.")

    def _cancel_homing(self, axis):
        """
        Abandon an in-progress homing run on this axis. Caller must hold the lock.

        A homing run is only complete when the axis actually reaches home, and
        arriving is what makes the position reading trustworthy. If the
        operator commands an ordinary move part-way through, the axis stops
        travelling toward home and the homing run is simply over - it did not
        succeed.

        Without this, the `homing` flag would survive the interruption and the
        axis would be treated as homed the moment it reached its new, unrelated
        target: its position counter would be zeroed while the machine was
        physically somewhere else entirely, and every subsequent move would be
        measured from that false origin. On real hardware that means driving
        confidently into the end of the frame.

        In practice this is now unreachable: _begin_homing() clears `homed`,
        and _check_ready() refuses moves on an unhomed axis, so a move command
        never gets far enough to interrupt a homing run. That matches the
        firmware, where runHoming() blocks the main loop and only an emergency
        stop can break into it.

        It is kept as a guard. Without it, any future relaxation of the
        unhomed-move rule would silently resurrect a nasty bug: the axis would
        be marked homed on reaching an unrelated target, zeroing its position
        counter while physically somewhere else entirely, and every later move
        would be measured from that false origin.
        """
        if axis.homing:
            axis.home_phase = None
            self._log(
                f"{axis.axis_id.upper()} homing cancelled by a new move command."
            )

    def _check_ready(self, axis_id):
        """
        Guard shared by the movement commands. Caller must hold the lock.

        Returns True if the move may proceed, otherwise logs why not and
        returns False.
        """
        if self._estop:
            self._log("Command refused: emergency stop is active. Send RESUME first.")
            return False

        if not self._axes[axis_id].homed:
            # The firmware refuses outright rather than warning - see
            # processRelativeMove() and processAbsoluteMove() in
            # MotorControl.cpp, both of which bail out with "Axis must be homed
            # before movement". Its reasoning is sound: until an axis has found
            # its limit switches it has no idea where it is or how far it can
            # travel, so it cannot know whether a move would drive the machine
            # into its own frame.
            #
            # The simulation must refuse for the same reason. If it merely
            # warned, jogs would work here and then silently do nothing on real
            # hardware, with the refusal buried in the log.
            self._log(
                f"Command refused: {axis_id.upper()} axis is not homed. "
                "Run homing first."
            )
            return False

        return True

    # -------------------- DEVELOPER FAULT INJECTION --------------------
    #
    # These have no equivalent on real hardware; they exist so the alarm
    # handling in the interface can be built and tested before any motor is
    # available to genuinely fault. The UI keeps them in a separate, collapsed
    # "Developer Tools" section so they are never mistaken for normal controls.

    def inject_alm_fault(self, motor_name):
        """Raise a simulated alarm on one motor."""
        with self._lock:
            if motor_name in self._alm:
                self._alm[motor_name] = True
                self._log(f"[SIM] ALM fault injected on motor {motor_name}")

    def clear_alm_faults(self):
        """Clear all simulated alarms."""
        with self._lock:
            for name in self._alm:
                self._alm[name] = False
            self._log("[SIM] All ALM faults cleared")

    # -------------------- STATE REPORTING --------------------

    def get_status(self):
        """Snapshot of the whole machine, shaped for the browser."""
        with self._lock:
            return {
                "mode": self.mode,
                "emergency_stop": self._estop,
                "axes": {
                    axis_id: {
                        "steps": int(axis.position),
                        "mm": round(config.steps_to_mm(axis_id, axis.position), 1),
                        "percent": axis.percent,
                        "homed": axis.homed,
                        "moving": axis.moving,
                    }
                    for axis_id, axis in self._axes.items()
                },
                "alm": dict(self._alm),
                "alm_critical": any(self._alm.values()),
            }

    def drain_log(self):
        """Return queued log lines and clear the queue."""
        with self._lock:
            lines = self._log_lines
            self._log_lines = []
            return lines

    def _log(self, message):
        """
        Queue a log line. Caller must already hold the lock.

        Every log call in this class happens inside a `with self._lock` block,
        which is why this does not take the lock itself - doing so would
        deadlock, as Python's threading.Lock is not reentrant.
        """
        timestamp = time.strftime("%H:%M:%S")
        self._log_lines.append(f"[{timestamp}] {message}")

        # Bound the queue. If every browser disconnects, nothing drains these
        # lines and the list would grow without limit over a long run.
        if len(self._log_lines) > 200:
            self._log_lines = self._log_lines[-200:]
