import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { FontLoader } from "three/examples/jsm/loaders/FontLoader.js";
import helvetikerFontData from "./helvetiker_regular.typeface.json";
import { FragmentsModels } from "@thatopen/fragments";

const data = JSON.parse(document.getElementById("ifc-data").textContent);
const canvas = document.getElementById("canvas");
const status = document.getElementById("status");
const props = document.getElementById("props");
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x20252b);

const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 100000);
camera.position.set(12, 10, 12);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.localClippingEnabled = true;
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 2.2));
const directionalLight = new THREE.DirectionalLight(0xffffff, 2);
directionalLight.position.set(10, 20, 10);
scene.add(directionalLight);

const gridFont = new FontLoader().parse(helvetikerFontData);
const workerText = document.getElementById("fragments-worker").textContent;
const workerURL = URL.createObjectURL(new Blob([workerText], { type: "text/javascript" }));
// Chrome behandelt direkt geöffnete file://-Dokumente als eindeutige Origins.
// Der vollständig gebündelte IIFE-Worker benötigt keine ES-Module und wird
// deshalb als klassischer Blob-Worker gestartet. So funktioniert die einzelne
// HTML-Datei auch per Doppelklick, nicht nur über http://localhost.
const manager = new FragmentsModels(workerURL, { maxWorkers: 2, classicWorker: true });
const models = [];
const modelById = new Map();
const gridGroupByModel = new Map();
const modelVisibilityById = new Map();
const metadataByModel = new Map();
const showIfcGrids = document.getElementById("showIfcGrids");
const flightMouse = document.getElementById("flightMouse");
const mouseLookDirection = new THREE.Vector3();
const mouseLookEuler = new THREE.Euler(0, 0, 0, "YXZ");
let mouseLookActive = false;
let mouseLookPrevious = null;
let activeTreeButton = null;
const treeButtonByKey = new Map();
const treeGroupByKey = new Map();
let modelBounds = new THREE.Box3();
let updateRunning = false;
let updatePending = false;

for (const item of data.models) {
  const elementIndex = new Map((item.metadata?.elements || []).map(element => [Number(element.expressID), element]));
  metadataByModel.set(item.modelId, { metadata: item.metadata, elementIndex });
}

function updateIfcGridVisibility() {
  const gridsEnabled = showIfcGrids.checked;
  for (const [modelId, gridGroup] of gridGroupByModel) {
    gridGroup.visible = gridsEnabled && modelVisibilityById.get(modelId) !== false;
  }
}

showIfcGrids.addEventListener("change", updateIfcGridVisibility);

function updateMouseNavigationMode() {
  mouseLookActive = false;
  mouseLookPrevious = null;
  controls.enableRotate = !flightMouse.checked;
  canvas.classList.toggle("flight-mouse-enabled", flightMouse.checked);
  canvas.classList.remove("flight-mouse-active");
}

flightMouse.addEventListener("change", updateMouseNavigationMode);
updateMouseNavigationMode();

const flySpeed = document.getElementById("flySpeed");
const flySpeedValue = document.getElementById("flySpeedValue");
const flyKeys = new Set();
const flyForward = new THREE.Vector3();
const flyRight = new THREE.Vector3();
const flyMovement = new THREE.Vector3();
let previousFrameTime = performance.now();

function updateFlySpeedLabel() {
  flySpeedValue.value = Number(flySpeed.value).toFixed(1);
}

function isTextInput(element) {
  if (!(element instanceof HTMLElement)) return false;
  if (element.isContentEditable || ["TEXTAREA", "SELECT"].includes(element.tagName)) return true;
  if (element.tagName !== "INPUT") return false;
  const inputType = (element.getAttribute("type") || "text").toLowerCase();
  return !["checkbox", "range", "radio", "button"].includes(inputType);
}

window.addEventListener("keydown", event => {
  const key = event.key.toLowerCase();
  if (!"wasd".includes(key) || event.ctrlKey || event.altKey || event.metaKey || isTextInput(event.target)) return;
  flyKeys.add(key);
  event.preventDefault();
});
window.addEventListener("keyup", event => {
  flyKeys.delete(event.key.toLowerCase());
});
window.addEventListener("blur", () => flyKeys.clear());
document.addEventListener("visibilitychange", () => {
  flyKeys.clear();
  previousFrameTime = performance.now();
});
flySpeed.addEventListener("input", updateFlySpeedLabel);
updateFlySpeedLabel();

function updateFlyNavigation(now) {
  const deltaSeconds = Math.min(Math.max((now - previousFrameTime) / 1000, 0), 0.05);
  previousFrameTime = now;
  if (!flyKeys.size) return false;

  camera.updateMatrixWorld();
  camera.getWorldDirection(flyForward).normalize();
  flyRight.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
  flyMovement.set(0, 0, 0);
  if (flyKeys.has("w")) flyMovement.add(flyForward);
  if (flyKeys.has("s")) flyMovement.sub(flyForward);
  if (flyKeys.has("d")) flyMovement.add(flyRight);
  if (flyKeys.has("a")) flyMovement.sub(flyRight);
  if (flyMovement.lengthSq() === 0) return false;

  flyMovement.normalize().multiplyScalar(Number(flySpeed.value) * deltaSeconds);
  camera.position.add(flyMovement);
  controls.target.add(flyMovement);
  return true;
}

function decode(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function resize() {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== width || canvas.height !== height) {
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
}

function refreshBounds() {
  modelBounds = new THREE.Box3();
  for (const model of models) {
    // FragmentsModel.box enthält model.object.matrixWorld bereits.
    if (model.object.visible) modelBounds.union(model.box);
  }
}

function fit() {
  refreshBounds();
  if (modelBounds.isEmpty()) return;
  const size = modelBounds.getSize(new THREE.Vector3());
  const center = modelBounds.getCenter(new THREE.Vector3());
  const distance = Math.max(size.length(), 1);
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(distance * 0.7, distance * 0.55, distance * 0.7));
  camera.near = Math.max(distance / 10000, 0.01);
  camera.far = distance * 100;
  camera.updateProjectionMatrix();
  controls.update();
  requestFragmentsUpdate(true);
}

async function requestFragmentsUpdate(force = false) {
  updatePending = updatePending || force;
  if (updateRunning) return;
  updateRunning = true;
  try {
    do {
      const requestedForce = updatePending;
      updatePending = false;
      await manager.update(requestedForce);
    } while (updatePending);
  } catch (error) {
    console.error("Fragments update failed", error);
  } finally {
    updateRunning = false;
  }
}

function createSectionPlane(color) {
  const group = new THREE.Group();
  group.renderOrder = 1000;
  const geometry = new THREE.PlaneGeometry(1, 1);
  const surface = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.16,
    side: THREE.DoubleSide,
    depthWrite: false,
    depthTest: true
  }));
  surface.renderOrder = 1000;
  const border = new THREE.LineSegments(
    new THREE.EdgesGeometry(geometry),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95, depthTest: false })
  );
  border.renderOrder = 1001;
  group.add(surface, border);
  group.visible = false;
  scene.add(group);
  return group;
}

const clipState = {
  X: {
    index: 0,
    negative: { sliderId: "clipXNegative", plane: new THREE.Plane(new THREE.Vector3(1, 0, 0), 0), helper: createSectionPlane(0xc43d4d) },
    positive: { sliderId: "clipXPositive", plane: new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0), helper: createSectionPlane(0xff6b6b) }
  },
  Y: {
    index: 1,
    negative: { sliderId: "clipYNegative", plane: new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), helper: createSectionPlane(0x37934a) },
    positive: { sliderId: "clipYPositive", plane: new THREE.Plane(new THREE.Vector3(0, -1, 0), 0), helper: createSectionPlane(0x62d26f) }
  },
  Z: {
    index: 2,
    negative: { sliderId: "clipZNegative", plane: new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), helper: createSectionPlane(0x367ac5) },
    positive: { sliderId: "clipZPositive", plane: new THREE.Plane(new THREE.Vector3(0, 0, -1), 0), helper: createSectionPlane(0x65aaff) }
  }
};
let activeClippingPlanes = [];

function updateSectionHelper(axis, cutter, position, size, center) {
  const helper = cutter.helper;
  helper.visible = true;
  if (axis === "X") {
    helper.position.set(position, center.y, center.z);
    helper.rotation.set(0, Math.PI / 2, 0);
    helper.scale.set(Math.max(size.z, 0.1) * 1.08, Math.max(size.y, 0.1) * 1.08, 1);
  } else if (axis === "Y") {
    helper.position.set(center.x, position, center.z);
    helper.rotation.set(-Math.PI / 2, 0, 0);
    helper.scale.set(Math.max(size.x, 0.1) * 1.08, Math.max(size.z, 0.1) * 1.08, 1);
  } else {
    helper.position.set(center.x, center.y, position);
    helper.rotation.set(0, 0, 0);
    helper.scale.set(Math.max(size.x, 0.1) * 1.08, Math.max(size.y, 0.1) * 1.08, 1);
  }
  helper.updateMatrixWorld(true);
}

function updateClips() {
  refreshBounds();
  if (modelBounds.isEmpty()) return;
  const size = modelBounds.getSize(new THREE.Vector3());
  const center = modelBounds.getCenter(new THREE.Vector3());
  activeClippingPlanes = [];
  for (const axis of ["X", "Y", "Z"]) {
    const axisState = clipState[axis];
    const min = modelBounds.min.getComponent(axisState.index);
    const max = modelBounds.max.getComponent(axisState.index);
    for (const side of ["negative", "positive"]) {
      const cutter = axisState[side];
      const value = Number(document.getElementById(cutter.sliderId).value);
      if (value >= 100) {
        cutter.helper.visible = false;
        continue;
      }
      const inward = 1 - value / 100;
      const position = side === "negative"
        ? min + inward * (max - min)
        : max - inward * (max - min);
      cutter.plane.constant = side === "negative" ? -position : position;
      activeClippingPlanes.push(cutter.plane);
      updateSectionHelper(axis, cutter, position, size, center);
    }
  }
  // That Open nutzt die Ebenen zweifach: globales GPU-Clipping schneidet
  // Dreiecke tatsächlich auf; der Fragments-Callback hält Culling und
  // Raycasting mit denselben sechs Schnittebenen synchron.
  renderer.clippingPlanes = activeClippingPlanes;
  requestFragmentsUpdate(true);
}

for (const axis of Object.values(clipState)) {
  for (const cutter of [axis.negative, axis.positive]) {
    document.getElementById(cutter.sliderId).addEventListener("input", updateClips);
  }
}

document.getElementById("resetClip").onclick = () => {
  for (const axis of Object.values(clipState)) {
    for (const cutter of [axis.negative, axis.positive]) {
      document.getElementById(cutter.sliderId).value = 100;
    }
  }
  updateClips();
};
document.getElementById("fit").onclick = fit;
controls.addEventListener("change", () => requestFragmentsUpdate(false));

function elementLabel(row) {
  const instanceName = typeof row.Name === "string" ? row.Name.trim() : "";
  const typeName = typeof row.type?.Name === "string" ? row.type.Name.trim() : "";
  return instanceName || typeName || row.class || `#${row.expressID}`;
}

function appendClassGroup(parent, className, rows, model, item) {
  const details = document.createElement("details");
  details.className = "tree-class";
  const summary = document.createElement("summary");
  summary.textContent = `${className} (${rows.length})`;
  const contents = document.createElement("div");
  contents.className = "tree-children";
  let populated = false;
  const populate = () => {
    if (populated) return;
    populated = true;
    const fragment = document.createDocumentFragment();
    for (const row of rows.sort((a, b) => elementLabel(a).localeCompare(elementLabel(b), "de"))) {
      const button = document.createElement("button");
      const key = `${item.modelId}:${row.expressID}`;
      button.type = "button";
      button.className = "tree-item";
      button.dataset.modelId = item.modelId;
      button.dataset.localId = String(row.expressID);
      button.textContent = elementLabel(row);
      button.title = `${row.class} · IFC #${row.expressID}`;
      button.addEventListener("click", event => {
        event.stopPropagation();
        selectTreeItem(model, item, row, button).catch(error => {
          console.error(error);
          status.textContent = `Tree selection error: ${error.message}`;
        });
      });
      treeButtonByKey.set(key, button);
      fragment.append(button);
    }
    contents.append(fragment);
  };
  details.addEventListener("toggle", () => {
    if (details.open) populate();
  });
  for (const row of rows) treeGroupByKey.set(`${item.modelId}:${row.expressID}`, { details, populate });
  details.append(summary, contents);
  parent.append(details);
}

function appendElementGroups(parent, rows, model, item) {
  const byClass = new Map();
  for (const row of rows) {
    if (!byClass.has(row.class)) byClass.set(row.class, []);
    byClass.get(row.class).push(row);
  }
  for (const [className, classRows] of [...byClass.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    appendClassGroup(parent, className, classRows, model, item);
  }
}

function appendModelTree(item, model) {
  const metadata = item.metadata || {};
  const spatialRows = metadata.spatialStructure || [];
  const spatialById = new Map(spatialRows.map(row => [Number(row.expressID), row]));
  const spatialChildren = new Map();
  for (const row of spatialRows) {
    const parentId = row.parent == null ? null : Number(row.parent);
    if (!spatialChildren.has(parentId)) spatialChildren.set(parentId, []);
    spatialChildren.get(parentId).push(row);
  }

  const elementsByContainer = new Map();
  const unassigned = [];
  for (const row of metadata.elements || []) {
    if (!row.isProduct || !row.hasRepresentation) continue;
    const containerId = Number(row.spatialContainer?.expressID);
    if (Number.isFinite(containerId) && spatialById.has(containerId)) {
      if (!elementsByContainer.has(containerId)) elementsByContainer.set(containerId, []);
      elementsByContainer.get(containerId).push(row);
    } else {
      unassigned.push(row);
    }
  }

  function appendSpatial(parent, spatial) {
    const details = document.createElement("details");
    details.className = "tree-spatial";
    const summary = document.createElement("summary");
    summary.textContent = `${spatial.class}: ${spatial.Name || spatial.LongName || `#${spatial.expressID}`}`;
    const contents = document.createElement("div");
    contents.className = "tree-children";
    for (const child of (spatialChildren.get(Number(spatial.expressID)) || []).sort((a, b) => (a.Name || "").localeCompare(b.Name || "", "de"))) {
      appendSpatial(contents, child);
    }
    appendElementGroups(contents, elementsByContainer.get(Number(spatial.expressID)) || [], model, item);
    details.append(summary, contents);
    parent.append(details);
  }

  const root = document.createElement("details");
  root.className = "tree-model";
  root.open = data.models.length === 1;
  const summary = document.createElement("summary");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = true;
  checkbox.title = "Modell ein-/ausblenden";
  checkbox.addEventListener("click", event => event.stopPropagation());
  checkbox.addEventListener("change", () => {
    model.object.visible = checkbox.checked;
    modelVisibilityById.set(item.modelId, checkbox.checked);
    updateIfcGridVisibility();
    fit();
  });
  const name = document.createElement("span");
  name.textContent = ` ${item.name}`;
  summary.append(checkbox, name);
  const contents = document.createElement("div");
  contents.className = "tree-children";
  const roots = spatialChildren.get(null) || spatialRows.filter(row => row.parent == null || !spatialById.has(Number(row.parent)));
  for (const spatial of roots) appendSpatial(contents, spatial);
  if (unassigned.length) {
    const unassignedDetails = document.createElement("details");
    const unassignedSummary = document.createElement("summary");
    unassignedSummary.textContent = `Without spatial assignment (${unassigned.length})`;
    const unassignedContents = document.createElement("div");
    unassignedContents.className = "tree-children";
    appendElementGroups(unassignedContents, unassigned, model, item);
    unassignedDetails.append(unassignedSummary, unassignedContents);
    contents.append(unassignedDetails);
  }
  root.append(summary, contents);
  document.getElementById("models").append(root);
}

async function loadModels() {
  try {
    let loadedGridCount = 0;
    let loadedAxisCount = 0;
    for (const item of data.models) {
      status.textContent = `Loading ${item.name}…`;
      const model = await manager.load(decode(item.fragmentBase64), {
        modelId: item.modelId,
        camera,
        onProgress: event => {
          if (typeof event?.progress === "number") status.textContent = `Loading ${item.name}: ${Math.round(event.progress * 100)}%`;
        }
      });
      scene.add(model.object);
      model.useCamera(camera);
      model.getClippingPlanesEvent = () => activeClippingPlanes;
      models.push(model);
      modelById.set(item.modelId, model);
      modelVisibilityById.set(item.modelId, true);


      try {
        const gridGroup = await model.getGrids({
          labels: {
            show: true,
            font: gridFont,
            config: { size: 0.32, curveSegments: 4, offset: 0.22 }
          }
        });
        const gridCount = gridGroup.children.length;
        let axisCount = 0;
        gridGroup.traverse(object => {
          if (object.userData?.kind === "axis") axisCount += 1;
          if (object.userData?.kind === "line" || object.userData?.kind === "label") object.renderOrder = 900;
        });
        if (gridCount > 0) {
          const gridMaterial = model.getGridMaterial();
          gridMaterial.color.set(0x32c5ff);
          gridMaterial.transparent = true;
          gridMaterial.opacity = 0.9;
          gridMaterial.depthTest = true;
          gridMaterial.depthWrite = false;
          gridMaterial.needsUpdate = true;
          const labelMaterial = model.getGridLabelMaterial();
          if (labelMaterial.color) labelMaterial.color.set(0xffffff);
          labelMaterial.transparent = true;
          labelMaterial.opacity = 0.95;
          labelMaterial.depthTest = false;
          labelMaterial.depthWrite = false;
          labelMaterial.needsUpdate = true;
          gridGroup.name = `${item.modelId}-ifc-grids`;
          // Grid-Kurven und Fragments-Geometrie verwenden dasselbe lokale
          // Modellkoordinatensystem. Als Kind von model.object übernimmt das
          // Raster exakt dieselbe Auto-Koordination und spätere Transformation.
          model.object.add(gridGroup);
          gridGroupByModel.set(item.modelId, gridGroup);
          updateIfcGridVisibility();
          loadedGridCount += gridCount;
          loadedAxisCount += axisCount;
        }
      } catch (gridError) {
        console.warn(`IFC grids could not be loaded for ${item.name}.`, gridError);
      }

      appendModelTree(item, model);
    }
    fit();
    updateClips();
    await requestFragmentsUpdate(true);
    const gridStatus = loadedGridCount
      ? ` ${loadedGridCount} IFC grids with ${loadedAxisCount} axes are visible.`
      : " No IFC grids were found in the model.";
    status.textContent = `${models.length} model(s) loaded.${gridStatus} Click an object in the viewer.`;
  } catch (error) {
    console.error(error);
    status.textContent = `Error: ${error.message}`;
  }
}

function displayValue(value) {
  if (value === undefined || value === null || value === "") return "—";
  if (typeof value === "boolean") return value ? "True" : "False";
  if (Array.isArray(value)) return value.map(displayValue).join(", ");
  if (typeof value === "object") {
    return value.Name || value.GlobalId || value.Identification || `${value.class || "IFC"} #${value.expressID ?? "?"}`;
  }
  return String(value);
}

function addFlatRows(rows, value, prefix = "") {
  if (value === undefined || value === null || value === "") return;
  if (Array.isArray(value)) {
    value.forEach((entry, index) => addFlatRows(rows, entry, `${prefix}[${index}]`));
    return;
  }
  if (typeof value === "object") {
    for (const [key, nested] of Object.entries(value)) {
      addFlatRows(rows, nested, prefix ? `${prefix}.${key}` : key);
    }
    return;
  }
  rows.push({ name: prefix || "Value", value: displayValue(value) });
}

function spatialPath(item, row) {
  const spatial = item.metadata?.spatialStructure || [];
  const byId = new Map(spatial.map(node => [Number(node.expressID), node]));
  const result = [];
  let current = byId.get(Number(row.spatialContainer?.expressID));
  const visited = new Set();
  while (current && !visited.has(Number(current.expressID))) {
    visited.add(Number(current.expressID));
    result.unshift(current);
    current = current.parent == null ? null : byId.get(Number(current.parent));
  }
  return result;
}

function propertyRows(row, item) {
  const attributes = [];
  addFlatRows(attributes, row.attributes || {});

  const properties = [];
  for (const [setName, values] of Object.entries(row.propertySets || {})) {
    properties.push({ group: setName });
    addFlatRows(properties, values);
  }

  const quantities = [];
  for (const [setName, values] of Object.entries(row.quantitySets || {})) {
    quantities.push({ group: setName });
    addFlatRows(quantities, values);
  }

  const location = [];
  for (const node of spatialPath(item, row)) {
    location.push({ name: node.class, value: node.Name || node.LongName || `#${node.expressID}` });
  }
  if (!location.length && row.spatialContainer) addFlatRows(location, row.spatialContainer);

  const material = [];
  addFlatRows(material, row.material || {});
  if (row.presentationLayers?.length) material.push({ name: "Presentation Layer", value: row.presentationLayers.join(", ") });

  const relations = [];
  if (row.type) {
    relations.push({ group: "Type" });
    addFlatRows(relations, row.type);
  }
  if (row.spatialContainer) {
    relations.push({ group: "ContainedInStructure" });
    addFlatRows(relations, row.spatialContainer);
  }
  if (row.partOf) {
    relations.push({ group: "PartOf" });
    addFlatRows(relations, row.partOf);
  }
  if (row.classifications?.length) {
    relations.push({ group: "Classifications" });
    addFlatRows(relations, row.classifications);
  }

  return [
    { id: "attributes", label: "Attributes", rows: attributes },
    { id: "properties", label: "Properties", rows: properties },
    { id: "quantities", label: "Quantities", rows: quantities },
    { id: "location", label: "Location", rows: location },
    { id: "material", label: "Material", rows: material },
    { id: "relations", label: "Part of", rows: relations }
  ];
}

function renderPropertyTable(container, rows) {
  container.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "property-empty";
    empty.textContent = "No data in this tab.";
    container.append(empty);
    return;
  }
  const table = document.createElement("table");
  table.className = "property-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const title of ["Property", "Value"]) {
    const th = document.createElement("th");
    th.textContent = title;
    headRow.append(th);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  let activeGroupRows = null;
  for (const entry of rows) {
    const tr = document.createElement("tr");
    if (entry.group) {
      tr.className = "property-group";
      const td = document.createElement("td");
      td.colSpan = 2;
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "property-group-toggle";
      const childRows = [];
      let expanded = true;
      const update = () => {
        toggle.textContent = `${expanded ? "▾" : "▸"} ${entry.group}`;
        toggle.setAttribute("aria-expanded", String(expanded));
        childRows.forEach(row => { row.hidden = !expanded; });
      };
      toggle.addEventListener("click", () => {
        expanded = !expanded;
        update();
      });
      update();
      td.append(toggle);
      tr.append(td);
      activeGroupRows = childRows;
    } else {
      const name = document.createElement("td");
      const value = document.createElement("td");
      name.textContent = entry.name;
      value.textContent = displayValue(entry.value);
      tr.append(name, value);
      if (activeGroupRows) activeGroupRows.push(tr);
    }
    body.append(tr);
  }
  table.append(head, body);
  container.append(table);
}

function renderProperties(row, fallback, item) {
  const title = document.getElementById("property-title");
  if (!row) {
    title.textContent = "Properties";
    props.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "property-empty";
    empty.textContent = `No IFC metadata for ${fallback.modelId} / #${fallback.itemId}.`;
    props.append(empty);
    return;
  }
  title.textContent = `${row.class}: ${elementLabel(row)}`;
  props.replaceChildren();
  const tabs = propertyRows(row, item);
  const tabBar = document.createElement("div");
  tabBar.className = "property-tabs";
  tabBar.setAttribute("role", "tablist");
  const content = document.createElement("div");
  content.className = "property-content";
  const activate = tab => {
    for (const button of tabBar.children) button.classList.toggle("active", button.dataset.tab === tab.id);
    renderPropertyTable(content, tab.rows);
  };
  tabs.forEach((tab, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "property-tab";
    button.dataset.tab = tab.id;
    button.textContent = tab.label;
    button.addEventListener("click", () => activate(tab));
    tabBar.append(button);
    if (index === 0) queueMicrotask(() => activate(tab));
  });
  props.append(tabBar, content);
}
function revealTreeButton(modelId, localId) {
  const key = `${modelId}:${localId}`;
  const group = treeGroupByKey.get(key);
  if (group) {
    const ancestors = [];
    let node = group.details;
    while (node) {
      if (node.tagName === "DETAILS") ancestors.push(node);
      node = node.parentElement?.closest("details") || null;
    }
    ancestors.reverse().forEach(details => { details.open = true; });
    group.populate();
  }
  return treeButtonByKey.get(key) || null;
}

async function clearSelection() {
  for (const model of models) await model.resetHighlight();
  if (activeTreeButton) activeTreeButton.classList.remove("selected");
  activeTreeButton = null;
}

async function applySelection(model, item, row, localId, treeButton = null) {
  await clearSelection();
  if (localId !== undefined && localId !== null) {
    await model.setColor([localId], new THREE.Color(0xffc400));
  }
  const synchronizedButton = treeButton || revealTreeButton(item.modelId, localId);
  if (synchronizedButton) {
    activeTreeButton = synchronizedButton;
    activeTreeButton.classList.add("selected");
    activeTreeButton.scrollIntoView({ block: "nearest" });
  }
  renderProperties(row, {
    modelId: item.modelId,
    itemId: row?.expressID,
    localId
  }, item);
  status.textContent = `Selected: ${row?.class || "IFC object"} ${elementLabel(row || {})} · IFC #${row?.expressID ?? "?"}`;
  requestFragmentsUpdate(true);
}

async function selectTreeItem(model, item, row, treeButton) {
  // Der offizielle IFC-Importer schreibt Express-IDs als öffentliche localIds.
  // itemId ist dagegen nur ein interner Fragments-Index.
  await applySelection(model, item, row, Number(row.expressID), treeButton);
}

async function selectAt(clientX, clientY) {
  const mouse = new THREE.Vector2(clientX, clientY);
  let best = null;

  for (const model of models) {
    if (!model.object.visible) continue;
    const hit = await model.raycast({ camera, mouse, dom: canvas });
    if (hit && (!best || hit.distance < best.distance)) best = hit;
  }

  if (!best) {
    await clearSelection();
    document.getElementById("property-title").textContent = "Properties";
    props.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "property-empty";
    empty.textContent = "No selection";
    props.append(empty);
    status.textContent = `${models.length} model(s) loaded. No object was hit.`;
    requestFragmentsUpdate(true);
    return;
  }

  // localId ist die öffentliche IFC-nahe ID; itemId ist nur der interne
  // Fragments-Index. Deshalb werden Properties und Baum über localId verbunden.
  const modelData = metadataByModel.get(best.fragments.modelId);
  const row = modelData?.elementIndex.get(Number(best.localId));
  const item = data.models.find(candidate => candidate.modelId === best.fragments.modelId) || { modelId: best.fragments.modelId };
  await applySelection(best.fragments, item, row, best.localId);
}

let pointerStart = null;
canvas.addEventListener("pointerdown", event => {
  if (event.button !== 0) return;
  pointerStart = { x: event.clientX, y: event.clientY };
  if (!flightMouse.checked) return;
  mouseLookActive = true;
  mouseLookPrevious = { x: event.clientX, y: event.clientY };
  canvas.classList.add("flight-mouse-active");
  canvas.setPointerCapture(event.pointerId);
  event.preventDefault();
}, { capture: true });
canvas.addEventListener("pointermove", event => {
  if (!mouseLookActive || !flightMouse.checked || !mouseLookPrevious) return;
  const deltaX = event.clientX - mouseLookPrevious.x;
  const deltaY = event.clientY - mouseLookPrevious.y;
  mouseLookPrevious = { x: event.clientX, y: event.clientY };
  if (deltaX === 0 && deltaY === 0) return;

  const targetDistance = Math.max(camera.position.distanceTo(controls.target), 0.1);
  mouseLookEuler.setFromQuaternion(camera.quaternion, "YXZ");
  mouseLookEuler.y -= deltaX * 0.0025;
  mouseLookEuler.x = THREE.MathUtils.clamp(mouseLookEuler.x - deltaY * 0.0025, -Math.PI / 2 + 0.01, Math.PI / 2 - 0.01);
  camera.quaternion.setFromEuler(mouseLookEuler);
  camera.getWorldDirection(mouseLookDirection);
  controls.target.copy(camera.position).addScaledVector(mouseLookDirection, targetDistance);
  requestFragmentsUpdate(false);
  event.preventDefault();
}, { capture: true });
canvas.addEventListener("pointerup", event => {
  if (event.button !== 0 || !pointerStart) return;
  const distance = Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y);
  pointerStart = null;
  mouseLookActive = false;
  mouseLookPrevious = null;
  canvas.classList.remove("flight-mouse-active");
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  if (distance <= 4) selectAt(event.clientX, event.clientY).catch(error => {
    console.error(error);
    status.textContent = `Selection error: ${error.message}`;
  });
}, { capture: true });
canvas.addEventListener("pointercancel", event => {
  pointerStart = null;
  mouseLookActive = false;
  mouseLookPrevious = null;
  canvas.classList.remove("flight-mouse-active");
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
}, { capture: true });

function loop(now = performance.now()) {
  resize();
  const cameraMoved = updateFlyNavigation(now);
  controls.update();
  if (cameraMoved) requestFragmentsUpdate(false);
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}

loadModels();
loop();
window.addEventListener("beforeunload", () => {
  URL.revokeObjectURL(workerURL);
  manager.dispose();
});

