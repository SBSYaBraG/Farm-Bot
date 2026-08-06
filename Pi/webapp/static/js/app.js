/* ============================================================
   app.js - FarmBot Control Interface, browser side

   Two responsibilities, and deliberately nothing more:

     1. Turn button presses into commands sent to the server
     2. Redraw the interface whenever the server reports new machine state

   What this file does NOT do is track the machine's position itself. Every
   number and indicator you see is drawn from the last `status_update` the
   server sent. That matters because several people can have this page open
   at once - the monitor on the Pi, someone's phone in the garden - and if
   each browser guessed at the state locally, those screens would drift out
   of agreement with each other and with the machine. The server (and behind
   it, the hardware) is the single source of truth; this page is a view of it.
   ============================================================ */

(function () {
  "use strict";

  // ---------- Connection ----------
  // Connects back to whichever host served this page, so the same code works
  // at localhost on the Pi and at the Pi's LAN address from a phone.
  const socket = io();

  // Machine geometry, fetched once from /api/config. Held here so the render
  // functions can convert step counts into positions on screen.
  let machineConfig = null;

  // Per-axis: may this axis currently be driven? Set from the homed flag in
  // each status update, and combined with the emergency-stop state in
  // applyControlAvailability(). Kept out here so both renderers can see it.
  const axisMovable = {};

  // ---------- Element references ----------
  const el = {
    connDot:     document.getElementById("conn-dot"),
    connText:    document.getElementById("conn-text"),
    modeBadge:   document.getElementById("mode-badge"),
    estopBanner: document.getElementById("estop-banner"),
    almBanner:   document.getElementById("alm-banner"),
    miniBed:     document.getElementById("mini-bed"),
    miniGantry:  document.getElementById("mini-gantry"),
    miniTool:    document.getElementById("mini-tool"),
    miniX:       document.getElementById("mini-x"),
    miniY:       document.getElementById("mini-y"),
    miniZ:       document.getElementById("mini-z"),
    axisControls: document.getElementById("axis-controls"),
    almLights:   document.getElementById("alm-lights"),
    devButtons:  document.getElementById("dev-alm-buttons"),
    log:         document.getElementById("log"),
    btnEstop:    document.getElementById("btn-estop"),
    btnResume:   document.getElementById("btn-resume"),
    btnHomeAll:  document.getElementById("btn-home-all"),
    btnClearAlm: document.getElementById("btn-clear-alm")
  };

  /* ============================================================
     STARTUP

     Fetch the machine geometry first, then build the parts of the interface
     that depend on it. Nothing is hardcoded about the machine's size or how
     many axes and motors it has - it is all read from the server, which in
     turn reads it from config.py. Resize the machine there and this page
     reshapes itself with no changes here.
     ============================================================ */
  fetch("/api/config")
    .then(function (response) { return response.json(); })
    .then(function (cfg) {
      machineConfig = cfg;
      applyBedProportions(cfg);
      buildAxisControls(cfg);
      buildAlmLights(cfg);
      buildDevButtons(cfg);

      // Publish for the 3D view. Stored on window as well as dispatched,
      // because the 3D view loads lazily and may only start up long after
      // this event has been and gone - it needs to be able to catch up.
      window.farmbotConfig = cfg;
      window.dispatchEvent(new CustomEvent("farmbot:config", { detail: cfg }));
    })
    .catch(function (err) {
      appendLog("[web] Failed to load machine configuration: " + err.message);
    });

  /**
   * Draw the minimap's bed at the machine's true proportions.
   *
   * A long, narrow bed should look long and narrow; a square one should look
   * square. Deriving the aspect ratio from real travel distances keeps the
   * plan honest, so a glance at it corresponds to the real garden.
   *
   * Which axis is the length and which the width comes from the server
   * (config.BED_MAP), never from an assumption here. On our machine Y is the
   * long axis and X the short one - the reverse of stock FarmBot - and an
   * assumption baked into this file would draw a plan that looked entirely
   * reasonable while putting the tool head in the wrong place.
   */
  function applyBedProportions(cfg) {
    const lengthMm = cfg.axes[cfg.bed_map.length].travel_mm;
    const widthMm  = cfg.axes[cfg.bed_map.width].travel_mm;
    el.miniBed.style.aspectRatio = lengthMm + " / " + widthMm;
  }

  /* ============================================================
     BUILDING THE CONTROLS
     ============================================================ */

  /**
   * Create a control panel for each axis: jog buttons, a custom-distance
   * field, absolute-position shortcuts, and a home button.
   *
   * Jog distances are in millimetres rather than steps because that is what
   * the operator can actually picture. The server converts to steps.
   */
  function buildAxisControls(cfg) {
    // Millimetres. Laid out as two rows so each negative step sits above its
    // positive twin: -100/-10/-1 over +100/+10/+1.
    const JOG_ROWS = [
      [-100, -10, -1],
      [100, 10, 1]
    ];

    Object.keys(cfg.axes).forEach(function (axisId) {
      const axis = cfg.axes[axisId];

      const panel = document.createElement("div");
      panel.className = "panel axis-panel";

      // --- Header: axis name and whether it has been homed ---
      const head = document.createElement("div");
      head.className = "axis-head";

      const name = document.createElement("span");
      name.className = "axis-name";
      name.textContent = axis.label;

      const badge = document.createElement("span");
      badge.className = "homed-badge";
      badge.id = "homed-" + axisId;
      badge.textContent = "NOT HOMED";

      head.appendChild(name);
      head.appendChild(badge);
      panel.appendChild(head);

      // Live position, in the panel for the axis it belongs to. The minimap
      // gives the at-a-glance picture; this is where the exact figure lives.
      const readout = document.createElement("div");
      readout.className = "axis-readout";
      readout.innerHTML =
        '<span class="axis-mm" id="posval-' + axisId + '">0.0 mm</span>' +
        '<span class="axis-sub" id="possub-' + axisId + '">0 steps · 0%</span>';
      panel.appendChild(readout);

      // --- Jog buttons ---
      //
      // Two rows of three rather than one row of six: the negative steps sit
      // directly above their positive counterparts, so -10 and +10 line up in
      // the same column. That makes the pair easy to find without reading,
      // which is the point when you are nudging a machine by hand.
      JOG_ROWS.forEach(function (row) {
        const jogRow = document.createElement("div");
        jogRow.className = "jog-row";

        row.forEach(function (mm) {
          const button = document.createElement("button");
          button.className = "btn axis-btn";
          // Tagged with its axis so the renderer can disable just this axis's
          // controls while that axis is unhomed.
          button.dataset.axis = axisId;
          // Explicit sign, so direction is never ambiguous.
          button.textContent = (mm > 0 ? "+" : "") + mm;
          button.addEventListener("click", function () {
            socket.emit("move_relative", { axis: axisId, mm: mm });
          });
          jogRow.appendChild(button);
        });

        panel.appendChild(jogRow);
      });

      // --- Absolute position shortcuts ---
      const absRow = document.createElement("div");
      absRow.className = "abs-row";

      [25, 50, 75].forEach(function (percent) {
        const button = document.createElement("button");
        button.className = "btn btn-small axis-btn";
        button.dataset.axis = axisId;
        button.textContent = percent + "%";
        button.addEventListener("click", function () {
          socket.emit("move_absolute", { axis: axisId, percent: percent });
        });
        absRow.appendChild(button);
      });

      // Per-axis home button. Deliberately NOT tagged with data-axis: homing
      // is the one command that must stay available on an unhomed axis, since
      // it is the way out of that state.
      const homeButton = document.createElement("button");
      homeButton.className = "btn btn-small axis-btn";
      homeButton.textContent = "HOME";
      homeButton.addEventListener("click", function () {
        socket.emit("home_axis", { axis: axisId });
      });
      absRow.appendChild(homeButton);

      panel.appendChild(absRow);
      el.axisControls.appendChild(panel);
    });
  }

  /**
   * Create one indicator light per motor.
   *
   * The motor list comes from the server, which builds it from config.py.
   * This is why the interface currently shows four lights (X, YL, YR, Z) - it
   * is reflecting the machine's actual motor configuration rather than an
   * assumption made here. Add or remove a motor in config.py and the row of
   * lights follows with no edit to this file.
   */
  function buildAlmLights(cfg) {
    cfg.motors.forEach(function (motorName) {
      const light = document.createElement("div");
      light.className = "alm-light";
      light.id = "alm-" + motorName;

      const bulb = document.createElement("div");
      bulb.className = "alm-bulb";

      const label = document.createElement("div");
      label.className = "alm-name";
      label.textContent = motorName;

      light.appendChild(bulb);
      light.appendChild(label);
      el.almLights.appendChild(light);
    });
  }

  /** Simulation-only: one fault-injection button per motor. */
  function buildDevButtons(cfg) {
    cfg.motors.forEach(function (motorName) {
      const button = document.createElement("button");
      button.className = "btn btn-small";
      button.textContent = "Fault " + motorName;
      button.addEventListener("click", function () {
        socket.emit("inject_alm", { motor: motorName });
      });
      el.devButtons.appendChild(button);
    });
  }

  /* ============================================================
     RENDERING MACHINE STATE

     Called every time the server broadcasts, roughly 8 times a second.
     ============================================================ */

  socket.on("status_update", function (status) {
    // Guard: broadcasts can arrive before /api/config has resolved.
    if (!machineConfig) { return; }

    renderMode(status);
    renderBedMap(status);
    renderPositions(status);
    renderAlarms(status);
    renderEmergencyStop(status);

    // Hand the very same payload to the 3D view, so both views are drawing
    // one shared truth rather than two independent interpretations of it.
    window.farmbotStatus = status;
    window.dispatchEvent(new CustomEvent("farmbot:status", { detail: status }));
  });

  /** Show whether we are driving a simulation or the real machine. */
  function renderMode(status) {
    const isSimulated = status.mode === "simulated";
    el.modeBadge.textContent = status.mode.toUpperCase();
    el.modeBadge.className = "badge " + (isSimulated ? "badge-sim" : "badge-live");
  }

  /**
   * Position the gantry and tool head on the bed map.
   *
   * Positions are expressed as percentages of each axis's travel, which is
   * exactly what CSS needs, and means the map stays correct no matter what
   * pixel size the bed is rendered at on a given screen.
   */
  function renderBedMap(status) {
    // Which axis plays which role on the plan, as declared by the server.
    const lengthAxis = machineConfig.bed_map.length;
    const widthAxis  = machineConfig.bed_map.width;
    const heightAxis = machineConfig.bed_map.height;

    // The gantry slides along the bed's LENGTH, drawn horizontally, so the
    // length axis drives its `left`.
    const alongPercent = travelPercent(lengthAxis, status.axes[lengthAxis]);
    el.miniGantry.style.left = alongPercent + "%";

    // The tool head rides on the gantry (so it shares the gantry's position
    // along the bed) and slides across the bed's WIDTH, drawn vertically.
    const acrossPercent = travelPercent(widthAxis, status.axes[widthAxis]);
    el.miniTool.style.left = alongPercent + "%";
    el.miniTool.style.top  = acrossPercent + "%";

    // Numeric readout beneath the dial. Rounded to whole millimetres: the
    // minimap is for a glance, and the per-axis panels carry the precision.
    el.miniX.textContent = "X " + Math.round(status.axes.x.mm);
    el.miniY.textContent = "Y " + Math.round(status.axes.y.mm);
    el.miniZ.textContent = "Z " + Math.round(status.axes[heightAxis].mm);
  }

  /**
   * Position as a percentage of travel, recomputed from raw steps rather
   * than using the integer `percent` the server sends.
   *
   * The server rounds that field to a whole number, which is fine for a text
   * readout but would make the tool head visibly jump between 1%-wide
   * positions as it travels - on a 2.7 m bed that is a 27 mm hop per update.
   * Recomputing here gives a fractional percentage and therefore smooth
   * motion on screen.
   */
  function travelPercent(axisId, axisState) {
    const maxSteps = machineConfig.axes[axisId].max_steps;
    if (!maxSteps) { return 0; }

    const pct = (axisState.steps / maxSteps) * 100;
    // Clamp so a rounding artefact can never push the marker off the map.
    return Math.max(0, Math.min(100, pct));
  }

  /** Update the numeric readouts and the per-axis HOMED badges. */
  function renderPositions(status) {
    Object.keys(status.axes).forEach(function (axisId) {
      const axis = status.axes[axisId];

      const valueEl = document.getElementById("posval-" + axisId);
      const subEl   = document.getElementById("possub-" + axisId);
      const badgeEl = document.getElementById("homed-" + axisId);

      if (valueEl) {
        valueEl.textContent = axis.mm.toFixed(1) + " mm";
      }
      if (subEl) {
        subEl.textContent = axis.steps + " steps · " + axis.percent + "%";
      }
      if (badgeEl) {
        // Three states, not two: an axis part-way through its homing sequence
        // is neither homed nor idle, and saying "NOT HOMED" while it is
        // visibly travelling reads as though nothing is happening.
        if (axis.homed) {
          badgeEl.textContent = "HOMED";
        } else if (axis.moving) {
          badgeEl.textContent = "HOMING…";
        } else {
          badgeEl.textContent = "NOT HOMED";
        }
        badgeEl.classList.toggle("is-homed", axis.homed);
      }

      // Record whether this axis may be driven. Actually applying it to the
      // buttons happens in applyControlAvailability(), which combines this
      // with the emergency-stop state - the two rules must compose, not
      // overwrite each other.
      axisMovable[axisId] = axis.homed;
    });
  }

  /** Light up motor alarm indicators and show the alarm banner. */
  function renderAlarms(status) {
    Object.keys(status.alm).forEach(function (motorName) {
      const light = document.getElementById("alm-" + motorName);
      if (!light) { return; }

      const faulted = status.alm[motorName];
      light.classList.toggle("fault", faulted);
      light.classList.toggle("ok", !faulted);
    });

    el.almBanner.classList.toggle("hidden", !status.alm_critical);
  }

  /**
   * Reflect the emergency stop: show the banner and disable everything that
   * could command motion.
   *
   * Disabling the controls is not merely cosmetic. While the stop is latched
   * the machine refuses movement commands anyway, so leaving the buttons live
   * would let an operator press them repeatedly and conclude the interface
   * had frozen. Greying them out says plainly: the machine is stopped, and
   * RESUME is the way out.
   */
  function renderEmergencyStop(status) {
    const stopped = status.emergency_stop;

    el.estopBanner.classList.toggle("hidden", !stopped);
    el.btnHomeAll.disabled = stopped;

    // The stop button itself is pointless once already stopped; RESUME is
    // pointless until you are.
    el.btnEstop.disabled = stopped;
    el.btnResume.disabled = !stopped;

    applyControlAvailability(stopped);
  }

  /**
   * Decide which controls are usable, from BOTH rules at once.
   *
   * A control is enabled only if the machine is not emergency-stopped AND its
   * axis is homed. These are applied together in one place because they were
   * previously applied in two, and whichever ran last silently undid the
   * other - an unhomed axis would have its buttons re-enabled the moment the
   * emergency stop was cleared.
   *
   * Per-axis HOME buttons carry no data-axis attribute and so are governed
   * only by the emergency stop: homing must remain available on an unhomed
   * axis, because it is the way out of that state.
   */
  function applyControlAvailability(stopped) {
    document.querySelectorAll(".axis-btn").forEach(function (button) {
      const axisId = button.dataset.axis;
      // Untagged buttons (the HOME buttons) are movement-neutral.
      const axisReady = !axisId || axisMovable[axisId];
      button.disabled = stopped || !axisReady;
    });
  }

  /* ============================================================
     GLOBAL CONTROLS
     ============================================================ */

  el.btnEstop.addEventListener("click", function () {
    socket.emit("emergency_stop");
  });

  el.btnResume.addEventListener("click", function () {
    socket.emit("resume");
  });

  el.btnHomeAll.addEventListener("click", function () {
    socket.emit("home_all");
  });

  el.btnClearAlm.addEventListener("click", function () {
    socket.emit("clear_alm");
  });

  /* ============================================================
     EVENT LOG
     ============================================================ */

  socket.on("log", function (payload) {
    (payload.lines || []).forEach(appendLog);
  });

  /**
   * Append a line to the on-screen log.
   *
   * Lines are colour-coded by their content so that the messages that matter
   * are findable in a busy log, and the list is capped so a long session
   * cannot grow the DOM without limit.
   */
  function appendLog(line) {
    const div = document.createElement("div");
    div.className = "log-line";

    // Classify by keyword. These match the wording the hardware layer emits.
    if (/EMERGENCY|refused|Cannot/i.test(line)) {
      div.classList.add("is-alert");
    } else if (/Warning|clamped/i.test(line)) {
      div.classList.add("is-warn");
    } else if (/\[SIM\]/.test(line)) {
      div.classList.add("is-sim");
    }

    div.textContent = line;
    el.log.appendChild(div);

    // Keep only the most recent lines.
    while (el.log.childElementCount > 300) {
      el.log.removeChild(el.log.firstChild);
    }

    // Follow the newest entry, the way a terminal does.
    el.log.scrollTop = el.log.scrollHeight;
  }

  /* ============================================================
     CONNECTION STATUS

     A disconnected page keeps showing the last state it received, which
     would look identical to a stopped machine. The indicator is what
     distinguishes "nothing is moving" from "we have lost contact".
     ============================================================ */

  socket.on("connect", function () {
    el.connDot.className = "dot dot-on";
    el.connText.textContent = "Connected";
  });

  socket.on("disconnect", function () {
    el.connDot.className = "dot dot-off";
    el.connText.textContent = "Disconnected";
    appendLog("[web] Connection to FarmBot server lost.");
  });

})();
