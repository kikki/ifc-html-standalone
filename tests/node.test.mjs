import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

test("browser bundles are self-contained build artifacts", () => {
  for (const file of ["dist/viewer.js", "dist/worker.js"]) {
    const source = fs.readFileSync(file, "utf8");
    assert.ok(source.length > 1000);
    assert.equal(/^\s*import\s/m.test(source), false);
    assert.equal(/^\s*export\s/m.test(source), false);
  }
  const viewerSource = fs.readFileSync("src/web/viewer.js", "utf8");
  assert.match(viewerSource, /classicWorker:\s*true/);
  assert.match(viewerSource, /URL\.createObjectURL\(new Blob\(\[workerText\]/);
});

test("selection passes absolute pointer coordinates to Fragments raycast", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  assert.match(source, /new THREE\.Vector2\(clientX, clientY\)/);
  assert.doesNotMatch(source, /clientX[^\n]+\*\s*2\s*-\s*1/);
  assert.match(source, /model\.raycast\(\{ camera, mouse, dom: canvas \}\)/);
});

test("selection keeps color highlight, removes the 3D box and renders property tabs", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  assert.match(source, /model\.setColor\(\[localId\]/);
  assert.doesNotMatch(source, /Box3Helper|showSelectionBox/);
  assert.match(source, /function propertyRows\(row, item\)/);
  assert.match(source, /function renderPropertyTable\(container, rows\)/);
  for (const tab of ["Attributes", "Properties", "Quantities", "Location", "Material", "Part of"]) {
    assert.ok(source.includes(`label: "${tab}"`));
  }
  assert.doesNotMatch(source, /label: "Summary"/);
  assert.match(source, /property-group-toggle/);
  assert.match(source, /aria-expanded/);
  assert.match(source, /row\.hidden = !expanded/);
  assert.doesNotMatch(source, /props\.textContent\s*=\s*JSON\.stringify/);
});

test("model browser contains model, spatial, class and selectable element levels", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  assert.match(source, /function appendModelTree\(item, model\)/);
  assert.match(source, /function appendSpatial\(parent, spatial\)/);
  assert.match(source, /function appendClassGroup\(parent, className, rows, model, item\)/);
  assert.match(source, /applySelection\(model, item, row, Number\(row\.expressID\), treeButton\)/);
  assert.doesNotMatch(source, /getLocalIdsFromItemIds\(\[Number\(row\.expressID\)\]\)/);
  assert.match(source, /Without spatial assignment/);
});

test("3D selection maps by localId and reveals the matching tree row", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  assert.match(source, /elementIndex\.get\(Number\(best\.localId\)\)/);
  assert.match(source, /function revealTreeButton\(modelId, localId\)/);
  assert.match(source, /treeGroupByKey/);
  assert.match(source, /scrollIntoView\(\{ block: "nearest" \}\)/);
});

test("clipping uses the native Fragments clipping callback and update cycle", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  assert.match(source, /model\.getClippingPlanesEvent\s*=\s*\(\)\s*=>\s*activeClippingPlanes/);
  assert.match(source, /renderer\.clippingPlanes\s*=\s*activeClippingPlanes/);
  assert.match(source, /manager\.update\(requestedForce\)/);
  assert.doesNotMatch(source, /models\.forEach\(m\s*=>\s*m\.update/);
});

test("six independent sliders show synchronized 3D section planes", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  const core = fs.readFileSync("src/ifc_html/core.py", "utf8");
  assert.match(source, /function createSectionPlane\(color\)/);
  assert.match(source, /function updateSectionHelper\(axis, cutter, position, size, center\)/);
  assert.match(source, /for \(const side of \["negative", "positive"\]\)/);
  assert.match(source, /side === "negative" \? -position : position/);
  assert.match(source, /updateSectionHelper\(axis, cutter, position, size, center\)/);
  for (const id of ["clipXNegative", "clipXPositive", "clipYNegative", "clipYPositive", "clipZNegative", "clipZPositive"]) {
    assert.ok(source.includes(`sliderId: "${id}"`));
    assert.ok(core.includes(`id="${id}"`));
  }
});

test("cutting, model overview and properties are independent collapsible panels", () => {
  const core = fs.readFileSync("src/ifc_html/core.py", "utf8");
  assert.match(core, /<details id="clip-panel" class="panel-section" open>/);
  assert.match(core, /<details id="model-panel" class="panel-section" open>/);
  assert.match(core, /<details id="property-panel-section" class="panel-section" open>/);
  assert.match(core, /<summary id="property-title">Properties<\/summary>/);
});

test("interface, property tabs and attribution are consistently English", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  const core = fs.readFileSync("src/ifc_html/core.py", "utf8");
  const css = fs.readFileSync("src/web/style.css", "utf8");
  assert.match(core, /<html lang="en">/);
  assert.match(core, /<title>\{title\}<\/title>/);
  assert.match(core, /<h1>\{title\}<\/h1>/);
  assert.match(core, /Prepared by <strong>\{prepared_by\}<\/strong>/);
  assert.match(core, /Created on <strong>\{created\}<\/strong>/);
  assert.match(core, /Created and distributed by <strong>waabe\.de<\/strong><br><span>n\.rube@waabe\.de<\/span>/);
  assert.match(css, /\.viewer-byline\{[^}]*border-left:3px solid #a0a5a8[^}]*background:#171b1e/);
  assert.doesNotMatch(core, /viewer-footer/);
  for (const label of ["Attributes", "Properties", "Quantities", "Location", "Material", "Part of"]) {
    assert.ok(source.includes(`label: "${label}"`));
  }
  assert.match(css, /\.property-tabs\{[^}]*display:flex[^}]*overflow-x:auto/);
  assert.doesNotMatch(core + source, /Ansicht einpassen|IFC-Raster|Flug-Maus|Schnittwerkzeug|Eigenschaften|Keine Auswahl|Modell\(e\) geladen/);
});

test("WASD fly navigation moves camera and orbit target with adjustable speed", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  const core = fs.readFileSync("src/ifc_html/core.py", "utf8");
  const css = fs.readFileSync("src/web/style.css", "utf8");
  assert.match(core, /id="flySpeed" type="range" min="0\.5" max="50" step="0\.5" value="\{speed\}"/);
  assert.match(core, /id="flySpeedValue"/);
  assert.match(source, /window\.addEventListener\("keydown"/);
  assert.match(source, /!"wasd"\.includes\(key\)/);
  assert.match(source, /!\["checkbox", "range", "radio", "button"\]\.includes\(inputType\)/);
  assert.match(core, /Flight mouse rotates the view around the current camera position; WASD remains active/);
  assert.match(core, /Speed is adjusted only with the slider/);
  assert.match(css, /\.navigation-help\{/);
  assert.match(source, /function updateFlyNavigation\(now\)/);
  assert.match(source, /Math\.min\(Math\.max\(\(now - previousFrameTime\) \/ 1000, 0\), 0\.05\)/);
  assert.match(source, /camera\.position\.add\(flyMovement\)/);
  assert.match(source, /controls\.target\.add\(flyMovement\)/);
  assert.match(source, /Number\(flySpeed\.value\) \* deltaSeconds/);
  assert.match(css, /\.fly-controls\{/);
});

test("flight mouse checkbox switches between camera-point look and existing orbit rotation", () => {
  const source = fs.readFileSync("src/web/viewer.js", "utf8");
  const core = fs.readFileSync("src/ifc_html/core.py", "utf8");
  const css = fs.readFileSync("src/web/style.css", "utf8");
  assert.match(core, /id="flightMouse" type="checkbox"> Flight mouse/);
  assert.match(source, /controls\.enableRotate = !flightMouse\.checked/);
  assert.match(source, /flightMouse\.addEventListener\("change", updateMouseNavigationMode\)/);
  assert.match(source, /canvas\.addEventListener\("pointermove"/);
  assert.match(source, /mouseLookEuler\.setFromQuaternion\(camera\.quaternion, "YXZ"\)/);
  assert.match(source, /controls\.target\.copy\(camera\.position\)\.addScaledVector\(mouseLookDirection, targetDistance\)/);
  assert.match(source, /MathUtils\.clamp/);
  assert.match(css, /canvas\.flight-mouse-enabled\{cursor:crosshair\}/);
});

test("clip controls use black-white theme, grey sliders and positive-negative order", () => {
  const core = fs.readFileSync("src/ifc_html/core.py", "utf8");
  const css = fs.readFileSync("src/web/style.css", "utf8");
  for (const axis of ["X", "Y", "Z"]) {
    const positive = core.indexOf(`id="clip${axis}Positive"`);
    const negative = core.indexOf(`id="clip${axis}Negative"`);
    assert.ok(positive >= 0 && negative > positive);
  }
  assert.match(css, /grid-template-columns:500px 1fr/);
  assert.match(css, /\.panel-section\{[^}]*background:#000[^}]*color:#fff/);
  assert.match(css, /::-webkit-slider-runnable-track\{[^}]*background:#686868/);
  assert.match(css, /::-moz-range-track\{[^}]*background:#686868/);
  assert.match(css, /minmax\(190px,1fr\)/);
  assert.match(css, /button\{[^}]*background:#303438/);
  assert.match(css, /button:hover\{[^}]*background:#474d52/);
  assert.match(css, /input\[type=checkbox\]\{[^}]*background:#25292c/);
  assert.match(css, /input\[type=checkbox\]:checked\{[^}]*background:#555c61/);
  assert.match(css, /input\[type=checkbox\]:hover\{[^}]*background:#3d4347/);
  assert.match(css, /\.toolbar-toggle:hover\{/);
  assert.doesNotMatch(css, /#28679b|#2aa9ff/i);
});

test("viewer renders native labeled IFC grids instead of a synthetic floor grid", () => {
  const viewer = fs.readFileSync("src/web/viewer.js", "utf8");
  const core = fs.readFileSync("src/ifc_html/core.py", "utf8");
  assert.match(viewer, /model\.getGrids\(\{/);
  assert.match(viewer, /show:\s*true/);
  assert.match(viewer, /font:\s*gridFont/);
  assert.match(viewer, /gridGroupByModel/);
  assert.match(viewer, /modelVisibilityById/);
  assert.match(viewer, /showIfcGrids\.addEventListener\("change", updateIfcGridVisibility\)/);
  assert.match(viewer, /gridGroup\.visible = gridsEnabled && modelVisibilityById\.get\(modelId\) !== false/);
  assert.match(viewer, /model\.object\.add\(gridGroup\)/);
  assert.doesNotMatch(viewer, /scene\.add\(gridGroup\)/);
  assert.match(viewer, /modelBounds\.union\(model\.box\)/);
  assert.doesNotMatch(viewer, /model\.box\.clone\(\)\.applyMatrix4/);
  assert.doesNotMatch(viewer, /new THREE\.GridHelper/);
  assert.match(core, /id=\\?"showIfcGrids\\?"/);
});
