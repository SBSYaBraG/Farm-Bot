"""
config.py - FarmBot Web Interface Configuration

THIS IS THE ONE FILE YOU EDIT WHEN THE MACHINE CHANGES SIZE.

Everything dimensional in the whole web interface derives from the AXES dict
below: the bed map's aspect ratio, the millimetre <-> step conversions, the
axis labels shown in the UI, and which ALM (alarm) indicator lights appear.
Change a number here, restart the server, and the entire interface follows.

The travel figures below now come from the 3D model of our machine, which
carries them as authored data (see MODEL TRAVEL DATA at the bottom of this
file). They replaced the FarmBot Genesis placeholders, which described a
machine more than twice our size. When the real frame is measured, edit the
`travel_mm` values here and nothing else.
"""

import os

# -------------------- AXIS GEOMETRY --------------------
#
# One entry per axis. Keys are lowercase and are used as the axis ID
# everywhere else in the codebase (URLs, socket events, DOM element IDs).
#
#   label        - human-readable name shown in the interface
#   travel_mm    - total usable travel, from home (0) to the far limit switch
#   steps_per_mm - stepper steps per millimetre; converts UI millimetres into
#                  the raw step counts the Arduino firmware actually expects
#   motors       - the physical motors driving this axis. The ALM panel renders
#                  one indicator light per motor listed here, so this list is
#                  what controls that part of the UI.
#
# THE FOUR-MOTOR DRIVE SCHEME
# ---------------------------
# The machine uses the classic FarmBot arrangement:
#
#   Y = the whole gantry rolling along the bed's LENGTH.
#       TWO motors, YL and YR, one on each rail plate. They must stay
#       synchronised or the gantry racks and jams across the rails.
#   X = the carriage riding across the top beam, over the bed's WIDTH.
#       ONE motor, on the carriage itself.
#   Z = the vertical extension sliding up and down through that carriage,
#       carrying the tool head. ONE motor, also on the carriage.
#
# Note the long axis is Y and the short axis is X - the opposite of what the
# names suggest to most people, which is exactly why BED_MAP below exists
# rather than the drawing code assuming "X is the long one".
#
# HEADS UP: the Arduino firmware in Farm-Bot/ still describes the OLD five
# motor layout (MOTOR_XL, MOTOR_XR, MOTOR_Y, MOTOR_ZL, MOTOR_ZR) with the axes
# the other way round. The firmware has not been rewritten for this design yet.
# Until it is, these names are what the simulation and the interface use, and
# the two will not agree.
AXES = {
    "x": {
        "label": "X (bed width)",
        "travel_mm": 520,
        "steps_per_mm": 5,
        "motors": ["X"],
    },
    "y": {
        "label": "Y (bed length)",
        "travel_mm": 1120,
        "steps_per_mm": 5,
        "motors": ["YL", "YR"],
    },
    "z": {
        "label": "Z (tool height)",
        "travel_mm": 285,
        "steps_per_mm": 5,
        "motors": ["Z"],
    },
}

# -------------------- BED MAP ORIENTATION --------------------
#
# Which axis is which on the top-down bed map. The map always draws the bed's
# LENGTH horizontally, because a long-and-narrow rectangle uses the width of a
# monitor far better than a tall-and-narrow one does.
#
# This mapping exists so that fact is stated once, here, instead of being
# baked into the drawing code. Our machine has X across the width and Y along
# the length - the opposite of stock FarmBot - and if the interface simply
# assumed "X is the long axis" the map would look plausible while being
# silently wrong, which is the worst kind of wrong for a position display.
# Rewiring the machine later means editing these three lines and nothing else.
#
# -------------------- MODEL TRAVEL DATA --------------------
#
# The travel_mm figures in AXES are taken from the 3D model, which carries
# them explicitly: it contains three marker objects - Axis_X_Travel,
# Axis_Y_Travel and Axis_Z_Travel - each tagged with the travel of its axis in
# millimetres. That is why this file and the 3D view agree about where 50% of
# an axis is, instead of the readouts claiming 1.5 m of travel on a 1.2 m
# table as they did while the Genesis placeholders were still here.
#
# Z is asymmetric in the model: 100 mm of rise above the beam and 185 mm of
# plunge below it, 285 mm total. The interface only deals in total travel, so
# only the total appears above.
#
# If the model is ever re-exported with different dimensions, the numbers in
# those markers are the ones to copy across.
BED_MAP = {
    "length": "y",   # axis running along the bed's length  -> horizontal on the map
    "width":  "x",   # axis running across the bed's width   -> vertical on the map
    "height": "z",   # axis running up and down              -> the separate Z gauge
}

# -------------------- SIMULATION BEHAVIOUR --------------------

# How fast the simulated gantry travels, in millimetres per second.
# Tuned to "feels like real hardware" rather than to any measured value -
# fast enough not to be tedious, slow enough that you can watch it move and
# hit the emergency stop mid-travel while testing.
SIM_SPEED_MM_S = 80.0

# How many times per second the simulation recalculates positions.
# 20 Hz is smooth to the eye without burning CPU on a Raspberry Pi.
SIM_TICK_HZ = 20.0

# -------------------- SERVER --------------------

# How often the server pushes a state update to every connected browser.
# Deliberately lower than SIM_TICK_HZ: the simulation needs fine time steps to
# move smoothly, but the browser only needs enough updates to look live. The
# CSS transition on the bed map smooths the gaps between these snapshots.
STATUS_BROADCAST_HZ = 8.0

# Port the web interface listens on. Browsers on the WiFi reach the interface
# at http://<pi-ip-address>:5000
#
# Overridable via the FARMBOT_PORT environment variable, because macOS claims
# port 5000 for its AirPlay Receiver. That does not affect the Raspberry Pi,
# so 5000 stays the default; developing on a Mac just needs, for example:
#     FARMBOT_PORT=5050 python run.py
SERVER_PORT = int(os.environ.get("FARMBOT_PORT", 5000))

# Bind address. 0.0.0.0 means "accept connections on every network interface",
# which is what allows phones and laptops elsewhere on the WiFi to connect.
# Binding to 127.0.0.1 instead would restrict access to the Pi itself only.
SERVER_HOST = "0.0.0.0"


# -------------------- DERIVED HELPERS --------------------
#
# Small helpers so the rest of the codebase never repeats these conversions.
# Every one of them reads from AXES above, so they stay correct automatically
# when the machine is resized.


def axis_ids():
    """Return the list of axis IDs, e.g. ['x', 'y', 'z']."""
    return list(AXES.keys())


def max_steps(axis_id):
    """Total travel of an axis expressed in stepper steps."""
    axis = AXES[axis_id]
    return int(axis["travel_mm"] * axis["steps_per_mm"])


def mm_to_steps(axis_id, mm):
    """Convert a millimetre distance into stepper steps for a given axis."""
    return int(round(mm * AXES[axis_id]["steps_per_mm"]))


def steps_to_mm(axis_id, steps):
    """Convert stepper steps into millimetres for a given axis."""
    return steps / AXES[axis_id]["steps_per_mm"]


def all_motor_names():
    """
    Flat list of every motor across every axis, e.g. ['X','YL','YR','Z'].

    Used to build the ALM status dictionary and, on the frontend, the row of
    alarm indicator lights. Because it is generated from AXES, adding or
    removing a motor there automatically adds or removes its indicator light.
    """
    names = []
    for axis in AXES.values():
        names.extend(axis["motors"])
    return names


def client_config():
    """
    The subset of this configuration the browser needs, as a JSON-safe dict.

    Served by the /api/config endpoint. The frontend uses this to draw the bed
    map at the correct proportions and to label controls, which means the
    geometry is never duplicated in JavaScript - there is exactly one source
    of truth for it, and this is that file.
    """
    return {
        "axes": {
            axis_id: {
                "label": axis["label"],
                "travel_mm": axis["travel_mm"],
                "steps_per_mm": axis["steps_per_mm"],
                "max_steps": max_steps(axis_id),
                "motors": axis["motors"],
            }
            for axis_id, axis in AXES.items()
        },
        "motors": all_motor_names(),
        # Tells the frontend which axis to draw where on the bed map, so the
        # JavaScript never has to assume an orientation.
        "bed_map": BED_MAP,
    }
