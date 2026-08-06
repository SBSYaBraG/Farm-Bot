"""
app.py - Flask + SocketIO server for the FarmBot web interface.

Responsibilities:
  1. Serve the single-page interface (index.html + static assets)
  2. Serve the machine geometry at /api/config, so the frontend draws the bed
     to the correct proportions without duplicating any constants in JS
  3. Receive commands from browsers over WebSockets and pass them to the
     hardware backend
  4. Broadcast machine state to every connected browser, several times a second

Why WebSockets rather than the browser repeatedly asking for updates: the
interface has to feel live while the gantry is moving, and several people may
be watching at once (the monitor on the Pi, someone's phone in the garden).
A broadcast pushes one update to all of them at the same instant, which is
what keeps every screen showing the same thing.

The server never holds machine state of its own. Everything it reports comes
from calling get_status() on the hardware backend. That is deliberate: with
several browsers able to send commands, a cached copy here would be one more
thing that could disagree with reality. The hardware is the only truth.
"""

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO

import config


def create_app(hardware):
    """
    Build the Flask app and SocketIO server around a hardware backend.

    `hardware` is any object implementing the FarmBotHardware contract in
    hardware/base.py. Today that is SimulatedHardware; when the physical
    machine is available a serial-backed implementation is passed instead and
    nothing in this file changes.
    """
    app = Flask(__name__)

    # Re-read index.html whenever it changes on disk.
    #
    # Flask only does this automatically in debug mode, and debug mode is not
    # something to run on the machine. Without it, Jinja compiles the template
    # once at startup and keeps serving that copy forever - so an edit to the
    # interface appears to have done nothing, while edits to the CSS and
    # JavaScript beside it (which ARE read from disk per request) take effect
    # immediately. Half the page updating and half not is a genuinely
    # confusing way to lose an afternoon.
    #
    # The cost is one stat() per page load. config.py still needs a restart,
    # because that is imported Python rather than a template.
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # cors_allowed_origins="*" is required for browsers on other devices to
    # open a WebSocket to this server. Without it, only a page served from the
    # exact same origin could connect - which would defeat the whole point of
    # letting phones on the WiFi use the interface.
    #
    # async_mode="threading" uses plain Python threads rather than eventlet or
    # gevent. Those are faster under heavy load, but this server has a handful
    # of clients at most, and avoiding them keeps installation on a Raspberry
    # Pi to a simple `pip install` with no compiled dependencies.
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    # ==================== HTTP ROUTES ====================

    @app.route("/")
    def index():
        """Serve the interface itself."""
        return render_template("index.html")

    @app.route("/api/config")
    def api_config():
        """
        Machine geometry for the frontend: axis labels, travel distances,
        steps-per-mm and motor names.

        The frontend fetches this once on load and uses it to size the bed map
        and build the controls. Resizing the machine in config.py therefore
        reshapes the interface with no JavaScript edits.
        """
        return jsonify(config.client_config())

    # ==================== SOCKET EVENTS: BROWSER -> SERVER ====================
    #
    # One handler per machine command, each mapping to a method on the hardware
    # backend. After any command we push a fresh state snapshot immediately
    # rather than waiting for the next scheduled broadcast, so the interface
    # reacts the instant a button is pressed.

    @socketio.on("connect")
    def on_connect():
        """A browser opened the interface. Send it the current state at once."""
        _broadcast_status()
        socketio.emit("log", {"lines": ["[web] Interface connected."]})

    @socketio.on("move_relative")
    def on_move_relative(data):
        """
        Jog an axis by a relative distance.

        The browser sends millimetres because that is what the operator thinks
        in; we convert to steps here, which is what the machine thinks in.
        """
        axis_id = data.get("axis")
        mm = float(data.get("mm", 0))

        if axis_id not in config.AXES:
            return

        steps = config.mm_to_steps(axis_id, mm)
        hardware.move_relative(axis_id, steps)
        _push_updates()

    @socketio.on("move_absolute")
    def on_move_absolute(data):
        """Send an axis to an absolute percentage of its travel."""
        axis_id = data.get("axis")
        percent = data.get("percent", 0)

        if axis_id not in config.AXES:
            return

        hardware.move_absolute_percent(axis_id, percent)
        _push_updates()

    @socketio.on("home_axis")
    def on_home_axis(data):
        """Home one axis."""
        axis_id = data.get("axis")
        if axis_id not in config.AXES:
            return

        hardware.home_axis(axis_id)
        _push_updates()

    @socketio.on("home_all")
    def on_home_all(_data=None):
        """Home every axis."""
        hardware.home_all()
        _push_updates()

    @socketio.on("emergency_stop")
    def on_emergency_stop(_data=None):
        """Halt everything immediately."""
        hardware.emergency_stop()
        _push_updates()

    @socketio.on("resume")
    def on_resume(_data=None):
        """Clear the emergency stop."""
        hardware.resume()
        _push_updates()

    # -------------------- Developer-only events --------------------
    # These drive the simulated fault injection. They are guarded with hasattr
    # so that a real hardware backend, which will not implement them, simply
    # ignores these events instead of raising.

    @socketio.on("inject_alm")
    def on_inject_alm(data):
        """Raise a simulated alarm on one motor, for testing the alarm UI."""
        if hasattr(hardware, "inject_alm_fault"):
            hardware.inject_alm_fault(data.get("motor"))
            _push_updates()

    @socketio.on("clear_alm")
    def on_clear_alm(_data=None):
        """Clear all simulated alarms."""
        if hasattr(hardware, "clear_alm_faults"):
            hardware.clear_alm_faults()
            _push_updates()

    # ==================== SERVER -> BROWSER ====================

    def _broadcast_status():
        """Push the current machine state to every connected browser."""
        socketio.emit("status_update", hardware.get_status())

    def _broadcast_log():
        """Push any new log lines to every connected browser."""
        lines = hardware.drain_log()
        if lines:
            socketio.emit("log", {"lines": lines})

    def _push_updates():
        """Send both state and log immediately, after a command."""
        _broadcast_status()
        _broadcast_log()

    def _status_broadcaster():
        """
        Background task: push state to all browsers at a steady rate.

        This runs for the life of the server and is what makes motion appear
        live - the browser is not polling, it is simply being told.
        """
        interval = 1.0 / config.STATUS_BROADCAST_HZ
        while True:
            socketio.sleep(interval)
            _broadcast_status()
            _broadcast_log()

    # start_background_task hands the loop to SocketIO so it cooperates with
    # whichever async model is in use, rather than us managing a raw thread.
    socketio.start_background_task(_status_broadcaster)

    return app, socketio
