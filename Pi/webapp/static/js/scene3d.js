/* ============================================================
   scene3d.js - The machine, rendered live, as the whole page

   Loads the Blender model and drives its moving parts from the same
   status_update data every other part of the interface uses. The 3D view is
   another way of looking at one shared truth, never a separate source of it.

   COORDINATE SYSTEMS
   ------------------
   The model was authored in Blender (Z-up) and exported to glTF (Y-up), so
   the exporter rotated it. The mapping is therefore:

       machine X (bed width)   ->  model X
       machine Y (bed length)  ->  model Z
       machine Z (tool height) ->  model Y   (up)

   Nothing below hardcodes that mapping, though. Each axis learns which model
   component it drives from its own travel marker, so a model exported with a
   different orientation still moves correctly.

   THE MOVING PARTS
   ----------------
   Parenting is Gantry -> X_Carriage -> Z_Extension, and each level adds one
   axis, exactly like the four-motor machine:

       Gantry        rolls along the bed's length    -> machine Y  (YL + YR)
       X_Carriage    rides across the top beam       -> machine X  (X)
       Z_Extension   slides down through the carriage-> machine Z  (Z)

   Because the chain nests, moving the gantry carries the carriage and tool
   head with it, and moving the carriage carries the vertical extension - the
   same way the steel does. Each part therefore only ever needs its own single
   axis set here; the rest follows for free.

   WHERE THE TRAVEL RANGES COME FROM
   ---------------------------------
   The model carries them. Alongside the visible parts it contains three
   marker objects - Axis_X_Travel, Axis_Y_Travel, Axis_Z_Travel - each an
   empty tagged with the travel of its axis in millimetres and pointing in the
   direction that axis moves. Reading those is far more trustworthy than
   inferring limits from bounding boxes, which is what this file used to do:
   a box tells you how big a part is, never how far it is allowed to go.

   Positions are still driven as percentages of travel, never millimetres, so
   the view stays correct even if config.py and the model ever disagree about
   the machine's size again.

   RENDERING ON DEMAND (this matters on a Raspberry Pi)
   ----------------------------------------------------
   The canvas fills the whole page, so a naive 60 fps loop would keep the GPU
   busy forever - including all the time the machine is sitting perfectly
   still. On a Pi that is work stolen from the server actually driving the
   motors.

   Instead nothing is drawn unless something changed: the machine moved, the
   user is dragging the camera, or the window resized. An idle machine costs
   essentially nothing.
   ============================================================ */

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const PART_GANTRY = "Gantry";
const PART_CARRIAGE = "X_Carriage";
const PART_EXTENSION = "Z_Extension";

// The travel markers, one per axis. See the header comment.
const MARKERS = { x: "Axis_X_Travel", y: "Axis_Y_Travel", z: "Axis_Z_Travel" };

// The model is authored in metres: the bed measures 0.7 x 1.2 model units for
// a real 700 x 1200 mm table. The markers state their travel in millimetres,
// so they need dividing by this to become model units.
const MM_PER_UNIT = 1000;

/**
 * Fallback colours, keyed by material name.
 *
 * An earlier export of the model arrived with material names but no colours,
 * so everything rendered white. The model has since been re-exported
 * correctly, and applyPalette() only touches materials that are still pure
 * white - so this table now does nothing. It is kept because it costs
 * nothing and quietly rescues the view if a future export loses colours
 * again, which is an easy mistake to make in Blender: the glTF exporter reads
 * only the Principled BSDF's Base Color input, and a colour plugged in
 * anywhere else in the node graph is silently dropped.
 */
const PALETTE = {
  FB_Extrusion: { color: 0x2b2f36, metalness: 0.55, roughness: 0.55 },
  FB_Slot:      { color: 0x3b414a, metalness: 0.45, roughness: 0.65 },
  FB_Silver:    { color: 0xb9bec6, metalness: 0.85, roughness: 0.35 },
  FB_Wood:      { color: 0xc2905c, metalness: 0.0,  roughness: 0.85 },
  FB_PVC:       { color: 0xe6e4de, metalness: 0.0,  roughness: 0.6  },
  FB_Teal:      { color: 0x1f8f8f, metalness: 0.3,  roughness: 0.5  },
  FB_Mustard:   { color: 0xd9a327, metalness: 0.3,  roughness: 0.5  },
  FB_Red:       { color: 0xc0392b, metalness: 0.3,  roughness: 0.5  },
  FB_Tool:      { color: 0x51575f, metalness: 0.6,  roughness: 0.45 }
};

let renderer, scene, camera, controls;

// The three moving parts, found in the model by name once it has loaded.
const parts = { gantry: null, carriage: null, extension: null };

/**
 * How each axis moves, filled in by measureTravel().
 *
 * One entry per machine axis, each shaped:
 *
 *     { node, prop, basePos, at0, at1 }
 *
 *   node    - the object that moves
 *   prop    - which of its local position components changes ("x"/"y"/"z")
 *   basePos - that component's value as the model was authored
 *   at0/at1 - the offset from basePos at 0% and at 100% of travel
 *
 * Storing offsets from the authored pose, rather than absolute coordinates,
 * means nothing here has to know about the model's internal origins or its
 * parent transforms - which is exactly what makes the nested chain work.
 */
const travel = { x: null, y: null, z: null };

let container = null;
let ready = false;
let pendingStatus = null;
let machineConfig = null;

// --- Render-on-demand bookkeeping ---
// `dirty` means something changed and one more frame is owed. `interactingUntil`
// keeps frames coming briefly after the user lets go of the camera, so the
// OrbitControls damping can glide to a stop instead of freezing mid-drift.
let dirty = true;
let interacting = false;
let interactingUntil = 0;

// The last pose actually drawn, so an unchanged status update costs nothing.
const lastDrawn = { x: null, y: null, z: null };

/* ============================================================
   SETUP
   ============================================================ */

export function init(containerElement, modelUrl) {
  container = containerElement;

  scene = new THREE.Scene();

  camera = new THREE.PerspectiveCamera(42, 1, 0.01, 100);

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    // The page behind the canvas provides the backdrop, so the canvas itself
    // is transparent. That lets the CSS gradient show through and avoids
    // painting a full-screen background colour every frame.
    alpha: true,
    powerPreference: "low-power"
  });
  // Cap the pixel ratio hard. Phones report 3x, which is nine times the pixels
  // for a barely perceptible gain - and this may be driving a monitor from a
  // Raspberry Pi.
  // Match the display's pixel density, capped at 2. Rendering below the
  // device's actual ratio means the canvas is upscaled to fit, which looks
  // exactly like a blurred image. Above 2 the extra pixels are imperceptible
  // and cost real work on a Pi.
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  // Keep the camera above the floor; below it is disorienting and shows
  // nothing useful.
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.minDistance = 0.6;
  controls.maxDistance = 6;

  // Any camera movement owes a frame.
  controls.addEventListener("change", requestRender);
  controls.addEventListener("start", function () {
    interacting = true;
  });
  controls.addEventListener("end", function () {
    interacting = false;
    // Keep drawing for a moment so damping can settle smoothly.
    interactingUntil = performance.now() + 1200;
  });

  addLighting();

  // WATCH THE CONTAINER, NOT JUST THE WINDOW.
  //
  // The scene now grows to fill whatever height the layout leaves it, so it
  // can change size without the window changing at all: an emergency-stop or
  // alarm banner appearing pushes it shorter, and dismissing one gives the
  // height back. Neither fires a window resize event. Listening only to the
  // window would leave the canvas at its old size while CSS stretched it to
  // the new one - which is precisely the mismatch that made the model look
  // blurred before.
  if (window.ResizeObserver) {
    new ResizeObserver(resize).observe(container);
  }
  // Kept as well: ResizeObserver is well supported, but a window resize is
  // the one case that must never be missed, and the handler is idempotent.
  window.addEventListener("resize", resize);

  // Size the renderer to its container straight away. Without this the canvas
  // keeps WebGL's default 300x150 and CSS stretches it across the panel,
  // which looks exactly like a badly blurred image - and leaves the camera
  // with a 1:1 aspect ratio, so the framing is wrong too.
  resize();

  return loadModel(modelUrl);
}

function addLighting() {
  // Hemisphere light gives a soft base: cool from above, warm bounce from the
  // ground. Cheap, and enough to read the machine's shape without shadows -
  // shadow maps would be a real cost on a Pi for little gain here.
  scene.add(new THREE.HemisphereLight(0xbfd4ff, 0x3a2f24, 2.2));

  const key = new THREE.DirectionalLight(0xffffff, 1.8);
  key.position.set(2, 3, 1.5);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xcfe0ff, 0.6);
  fill.position.set(-2, 1.5, -1.5);
  scene.add(fill);
}

function loadModel(modelUrl) {
  return new Promise(function (resolve, reject) {
    new GLTFLoader().load(
      modelUrl,
      function (gltf) {
        scene.add(gltf.scene);

        parts.gantry = gltf.scene.getObjectByName(PART_GANTRY);
        parts.carriage = gltf.scene.getObjectByName(PART_CARRIAGE);
        parts.extension = gltf.scene.getObjectByName(PART_EXTENSION);

        const missing = [
          !parts.gantry && PART_GANTRY,
          !parts.carriage && PART_CARRIAGE,
          !parts.extension && PART_EXTENSION
        ].filter(Boolean);

        if (missing.length) {
          reject(new Error("Model is missing: " + missing.join(", ")));
          return;
        }

        applyPalette(gltf.scene);

        try {
          measureTravel(gltf.scene);
        } catch (err) {
          reject(err);
          return;
        }

        // Re-measure before framing. The panel may still have been settling
        // when init() ran, and frameCamera depends on camera.aspect being
        // right - a stale aspect would frame the machine badly.
        resize();
        frameCamera(gltf.scene);

        ready = true;
        requestRender();
        resolve();
      },
      undefined,
      reject
    );
  });
}

/** Recolour only materials that arrived pure white. See PALETTE above. */
function applyPalette(root) {
  root.traverse(function (object) {
    if (!object.isMesh) { return; }

    const materials = Array.isArray(object.material)
      ? object.material
      : [object.material];

    materials.forEach(function (material) {
      if (!material) { return; }

      const preset = PALETTE[material.name];
      if (!preset) { return; }

      // glTF's default when baseColorFactor is absent is pure white; anything
      // else means the exporter carried a real colour through.
      const isDefaultWhite =
        material.color &&
        material.color.r === 1 && material.color.g === 1 && material.color.b === 1;

      if (!isDefaultWhite) { return; }

      material.color.setHex(preset.color);
      if (material.metalness !== undefined) { material.metalness = preset.metalness; }
      if (material.roughness !== undefined) { material.roughness = preset.roughness; }
    });
  });
}

/**
 * Read one travel marker out of the model.
 *
 * A marker is an empty object carrying its travel as custom data, positioned
 * and rotated to point the way its axis moves. glTF hands custom data through
 * as `userData`, so the numbers authored in Blender arrive here untouched.
 *
 * DIRECTION: an empty's own "forward" is +Z in Blender, and the Z-up to Y-up
 * conversion the glTF exporter applies turns that into local +Y. Rotating +Y
 * by the marker's own rotation therefore gives the direction of travel in the
 * scene. It is then snapped to whichever scene axis it most nearly follows,
 * because these parts slide along one axis each - snapping keeps a fraction
 * of a degree of authoring slop from leaking a wobble into the motion.
 *
 * Returns null when the marker is absent, so the caller can say so plainly.
 */
function readTravelMarker(root, markerName) {
  const marker = root.getObjectByName(markerName);
  if (!marker) { return null; }

  const travelMm = marker.userData && marker.userData.travel_mm;
  if (!travelMm) { return null; }

  const direction = new THREE.Vector3(0, 1, 0).applyQuaternion(marker.quaternion);

  const components = ["x", "y", "z"];
  let prop = "x";
  components.forEach(function (c) {
    if (Math.abs(direction[c]) > Math.abs(direction[prop])) { prop = c; }
  });

  return {
    prop: prop,
    sign: direction[prop] < 0 ? -1 : 1,
    travel: travelMm / MM_PER_UNIT,
    // Z alone is authored somewhere in the middle of its stroke, so it also
    // states how much of that stroke is above and how much below.
    up: (marker.userData.travel_up_mm || 0) / MM_PER_UNIT,
    down: (marker.userData.travel_down_mm || 0) / MM_PER_UNIT
  };
}

/**
 * Work out how each part moves, from the model's travel markers.
 *
 * Throws if a marker is missing rather than falling back to a guess. A guess
 * here would be invisible: the machine would still glide about convincingly
 * while reporting the tool head somewhere it is not, which for a position
 * display is the worst way to be wrong. An error names the missing marker and
 * puts it on screen, and re-exporting the model with it takes a minute.
 */
function measureTravel(root) {
  const marks = {};
  const missing = [];

  Object.keys(MARKERS).forEach(function (axisId) {
    const mark = readTravelMarker(root, MARKERS[axisId]);
    if (mark) { marks[axisId] = mark; } else { missing.push(MARKERS[axisId]); }
  });

  if (missing.length) {
    throw new Error(
      "the model has no travel data for: " + missing.join(", ") +
      ". Re-export it with those marker objects included."
    );
  }

  // X and Y are authored parked at one end of their stroke - the gantry at
  // the near end of the rails, the carriage at one side of the beam - so the
  // authored pose is 0% and the whole travel runs from there.
  travel.y = linearTravel(parts.gantry, marks.y, 0, marks.y.travel * marks.y.sign);
  travel.x = linearTravel(parts.carriage, marks.x, 0, marks.x.travel * marks.x.sign);

  // Z is authored part-way down, with room both above and below. Machine Z
  // counts up as the tool DESCENDS, so 0% is the extension fully raised and
  // 100% is fully plunged - hence up first, down second.
  travel.z = linearTravel(
    parts.extension, marks.z,
    marks.z.up * marks.z.sign,
    -marks.z.down * marks.z.sign
  );
}

/** Bundle a part, the component it slides along, and its two end offsets. */
function linearTravel(node, mark, at0, at1) {
  return {
    node: node,
    prop: mark.prop,
    basePos: node.position[mark.prop],
    at0: at0,
    at1: at1
  };
}

/**
 * Point the camera at the machine, framed to fill the view.
 *
 * The distance is computed from the model's bounding sphere and the camera's
 * actual field of view, rather than multiplied out of the bounding box by
 * some hand-picked factor. Guessed factors were what left the machine sitting
 * small in the middle of a wide frame: the box diagonal of a long, low
 * machine is much larger than the height that actually needs to fit, so
 * scaling by it pushed the camera far further back than necessary.
 *
 * Both dimensions are checked because a wide panel constrains vertically
 * while a narrow one constrains horizontally, and the view must fit either
 * way.
 */
function frameCamera(root) {
  const box = new THREE.Box3().setFromObject(root);
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const centre = sphere.center;
  const radius = sphere.radius;

  const vFov = THREE.MathUtils.degToRad(camera.fov);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);

  // A three-quarter view: along the bed, slightly across it, from above.
  const direction = new THREE.Vector3(0.52, 0.42, 0.74).normalize();

  // Start from the distance that fits the bounding sphere. That is guaranteed
  // not to clip, but it is a loose fit - the sphere is much bigger than the
  // machine's actual silhouette from this angle, which leaves it looking
  // small and far away in a wide frame.
  let distance = Math.max(
    radius / Math.sin(vFov / 2),
    radius / Math.sin(hFov / 2)
  );

  camera.near = Math.max(radius / 500, 0.01);
  camera.far = radius * 40;

  // Now close in on the real silhouette. Measuring how much of the frame the
  // model's projected corners actually occupy, and scaling the distance by
  // how far that is from the target, converges in a couple of passes -
  // projected size varies as roughly 1/distance, so each pass lands close.
  const TARGET_FILL = 0.92;   // of the tighter frame axis, leaving a margin

  for (let pass = 0; pass < 4; pass++) {
    camera.position.copy(centre).addScaledVector(direction, distance);
    camera.lookAt(centre);
    camera.updateMatrixWorld(true);
    camera.updateProjectionMatrix();

    const occupied = projectedFill(box, camera);
    if (occupied <= 0) { break; }

    distance *= occupied / TARGET_FILL;
  }

  controls.target.copy(centre);
  camera.position.copy(centre).addScaledVector(direction, distance);
  camera.updateProjectionMatrix();
  controls.update();
  requestRender();
}

/**
 * How much of the frame the box occupies, as a fraction of the tighter axis.
 *
 * Projects the box's eight corners into normalised device coordinates, where
 * the visible frame runs -1..1 on both axes, and returns the larger of the
 * two extents. 1.0 means the model exactly touches the frame edge; above 1.0
 * it is being cropped.
 */
function projectedFill(box, camera) {
  const corner = new THREE.Vector3();
  let maxX = 0;
  let maxY = 0;

  for (const x of [box.min.x, box.max.x]) {
    for (const y of [box.min.y, box.max.y]) {
      for (const z of [box.min.z, box.max.z]) {
        corner.set(x, y, z).project(camera);
        maxX = Math.max(maxX, Math.abs(corner.x));
        maxY = Math.max(maxY, Math.abs(corner.y));
      }
    }
  }

  return Math.max(maxX, maxY);
}

/* ============================================================
   DRIVING THE MODEL FROM MACHINE STATE
   ============================================================ */

export function setMachineConfig(cfg) {
  machineConfig = cfg;
  requestRender();
}

/**
 * Hand the newest machine status to the 3D view.
 *
 * Only stores it; the render loop applies it. A burst of status updates
 * therefore cannot cause more work than there are frames to draw.
 */
export function update(status) {
  pendingStatus = status;
  requestRender();
}

/** Mark that one more frame is owed. */
function requestRender() {
  dirty = true;
}

/**
 * Apply the stored status to the model.
 *
 * Returns true if anything actually moved. An unchanged pose returns false,
 * which is what lets an idle machine stop consuming frames entirely - the
 * server keeps broadcasting several times a second even when nothing is
 * happening, and redrawing for each of those would defeat the whole point.
 */
function applyStatus() {
  if (!ready || !pendingStatus || !machineConfig) { return false; }

  const axes = pendingStatus.axes;
  const fx = fractionOf("x", axes.x);
  const fy = fractionOf("y", axes.y);
  const fz = fractionOf("z", axes.z);

  if (fx === lastDrawn.x && fy === lastDrawn.y && fz === lastDrawn.z) {
    return false;
  }
  lastDrawn.x = fx; lastDrawn.y = fy; lastDrawn.z = fz;

  // Each axis drives exactly one part along exactly one component. Everything
  // that makes that correct - which part, which direction, how far, and which
  // end is 0% - was settled once in measureTravel(), so all that is left here
  // is to slide each part to its fraction of its own stroke. The nesting in
  // the model does the rest: the carriage rides the gantry, the extension
  // rides the carriage.
  place(travel.y, fy);
  place(travel.x, fx);
  place(travel.z, fz);

  return true;
}

/** Slide one part to `fraction` (0..1) along its travel. */
function place(axisTravel, fraction) {
  axisTravel.node.position[axisTravel.prop] =
    axisTravel.basePos + lerp(axisTravel.at0, axisTravel.at1, fraction);
}

/**
 * An axis's position as a fraction (0..1) of its travel.
 *
 * Recomputed from raw steps rather than the server's rounded `percent`: a
 * whole-number percentage would make the gantry advance in visible jumps
 * instead of gliding.
 */
function fractionOf(axisId, axisState) {
  if (!axisState) { return 0; }

  const axisConfig = machineConfig.axes[axisId];
  if (!axisConfig || !axisConfig.max_steps) {
    return clamp01(axisState.percent / 100);
  }
  return clamp01(axisState.steps / axisConfig.max_steps);
}

function clamp01(v) { return Math.max(0, Math.min(1, v)); }
function lerp(a, b, t) { return a + (b - a) * t; }

/* ============================================================
   RENDER LOOP
   ============================================================ */

/** Begin the loop. Frames are only actually drawn when something changed. */
export function start() {
  renderer.setAnimationLoop(tick);
}

function tick(now) {
  // Damping keeps the camera drifting for a moment after the user lets go.
  const settling = interacting || now < interactingUntil;

  // applyStatus() must run every tick, not only when a frame is due, so that
  // a change is noticed the moment it arrives.
  const moved = applyStatus();

  if (!dirty && !moved && !settling) { return; }

  if (settling) { controls.update(); }   // required for damping

  renderer.render(scene, camera);
  dirty = false;
}

// The size the canvas was last set to. Dragging a window edge fires resize
// events far faster than frames are drawn, and reallocating the drawing buffer
// is not free - on a Pi least of all. Comparing first turns the repeats into
// nothing.
const lastSize = { width: 0, height: 0 };

function resize() {
  if (!container || !renderer) { return; }
  const width = container.clientWidth;
  const height = container.clientHeight;
  if (width === 0 || height === 0) { return; }
  if (width === lastSize.width && height === lastSize.height) { return; }

  lastSize.width = width;
  lastSize.height = height;

  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  requestRender();
}

/** Reset the camera to its framing shot. */
export function resetView() {
  if (scene) { frameCamera(scene); }
}
