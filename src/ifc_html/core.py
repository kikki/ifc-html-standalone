from __future__ import annotations

import base64
import html
import json
import logging
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import ifcopenshell

from .geometry_fallback import prepare_for_fragments
from .metadata import extract_metadata, model_id

LOG = logging.getLogger(__name__)
SOURCE_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class ViewerOptions:
    """User-editable values embedded into the generated viewer."""

    title: str = "Free HTML Model Viewer"
    prepared_by: str = ""
    flight_speed: float = 5.0
    creation_date: str = ""

    def normalized(self) -> "ViewerOptions":
        title = self.title.strip()
        prepared_by = self.prepared_by.strip()
        if not title:
            raise ValueError("Viewer title is required.")
        if len(title) > 200:
            raise ValueError("Viewer title must not exceed 200 characters.")
        if len(prepared_by) > 200:
            raise ValueError("Prepared-by name must not exceed 200 characters.")
        speed = float(self.flight_speed)
        if not math.isfinite(speed) or not 0.5 <= speed <= 50.0:
            raise ValueError("Flight speed must be between 0.5 and 50.0.")
        return ViewerOptions(
            title=title,
            prepared_by=prepared_by,
            flight_speed=speed,
            creation_date=self.creation_date.strip() or date.today().isoformat(),
        )


def _resource(*parts: str) -> Path:
    return RESOURCE_ROOT.joinpath(*parts)


def _node_executable() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).resolve().parent / "runtime" / "node.exe"
        if not bundled.is_file():
            raise RuntimeError(f"Bundled Node.js runtime is missing: {bundled}")
        return bundled
    found = shutil.which("node")
    if not found:
        raise RuntimeError("Node.js was not found. Run the application from the portable folder or install Node.js for development.")
    return Path(found)


def _run(command: list[str | Path]) -> subprocess.CompletedProcess[str]:
    args = [str(part) for part in command]
    completed = subprocess.run(args, cwd=RESOURCE_ROOT, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\n{completed.stdout}\n{completed.stderr}".strip()
        )
    return completed


def _ensure_browser_bundles() -> None:
    """Build browser resources during development; packaged resources are immutable."""

    viewer = _resource("dist", "viewer.js")
    worker = _resource("dist", "worker.js")
    if getattr(sys, "frozen", False):
        missing = [str(path) for path in (viewer, worker) if not path.is_file()]
        if missing:
            raise RuntimeError(f"Packaged browser resources are missing: {missing}")
        return
    _run([_node_executable(), _resource("src", "node", "build.mjs")])


def validate_ifc(path: Path) -> dict:
    """Open an IFC with IfcOpenShell and return a concise preflight report."""

    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    if candidate.suffix.lower() != ".ifc":
        raise ValueError(f"Not an IFC file: {candidate.name}")
    if candidate.stat().st_size == 0:
        raise ValueError(f"IFC file is empty: {candidate.name}")
    try:
        model = ifcopenshell.open(candidate)
    except Exception as error:
        raise ValueError(f"IfcOpenShell could not load {candidate.name}: {error}") from error

    projects = model.by_type("IfcProject")
    if not projects:
        raise ValueError(f"No IfcProject was found in {candidate.name}.")
    products = model.by_type("IfcProduct")
    schema = str(model.schema)
    # Spatial base classes differ between IFC releases. Probe the classes
    # exposed by the loaded schema instead of rejecting an otherwise readable
    # model because one optional class name does not exist in that release.
    candidates = (
        ("IfcSpatialStructureElement", "IfcSpatialElement")
        if schema.upper().startswith("IFC2X3")
        else ("IfcSpatialElement", "IfcSpatialStructureElement")
    )
    spatial: list = []
    spatial_type = ""
    for class_name in candidates:
        try:
            spatial = list(model.by_type(class_name))
            spatial_type = class_name
            break
        except (RuntimeError, ValueError):
            continue
    notices: list[str] = []
    if spatial_type:
        schema_info = f"{schema}: spatial structure read via {spatial_type}."
    else:
        schema_info = (
            f"{schema}: no known spatial base class is exposed by this schema; "
            "spatial counting was skipped and conversion may continue."
        )
        notices.append(schema_info)
    return {
        "path": str(candidate),
        "name": candidate.name,
        "schema": schema,
        "schemaInfo": schema_info,
        "spatialClass": spatial_type or None,
        "projects": len(projects),
        "products": len(products),
        "spatialElements": len(spatial),
        "notices": notices,
        "bytes": candidate.stat().st_size,
        "status": f"IFC loaded successfully ({schema})",
    }


def validate_html(path: Path) -> list[str]:
    """Return every forbidden external dependency reference in an HTML file."""

    text = path.read_text("utf-8")
    hits: list[str] = []
    pattern = r'''(?:src|href)\s*=\s*["']\s*(https?://|//)|\b(?:fetch|importScripts)\s*\(\s*["']https?://'''
    for match in re.finditer(pattern, text, re.I):
        hits.append(match.group(0))
    return hits


def _manifest_from_html(text: str) -> dict:
    match = re.search(
        r'<script\s+id="ifc-data"\s+type="application/json">(.*?)</script>',
        text,
        re.S,
    )
    if not match:
        raise ValueError("Embedded IFC manifest was not found.")
    return json.loads(match.group(1).replace("<\\/", "</"))


def validate_generated_html(path: Path, expected_models: int) -> dict:
    """Verify offline safety, manifest integrity and every embedded fragment payload."""

    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Generated HTML file is missing or empty.")
    text = path.read_text("utf-8")
    external = validate_html(path)
    if external:
        raise ValueError(f"External dependencies detected: {external}")
    manifest = _manifest_from_html(text)
    models = manifest.get("models", [])
    if len(models) != expected_models:
        raise ValueError(f"Expected {expected_models} embedded models, found {len(models)}.")
    fragment_bytes = 0
    for model in models:
        payload = model.get("fragmentBase64", "")
        try:
            decoded = base64.b64decode(payload, validate=True)
        except Exception as error:
            raise ValueError(f"Invalid fragment payload for {model.get('name', 'unknown model')}.") from error
        if not decoded:
            raise ValueError(f"Empty fragment payload for {model.get('name', 'unknown model')}.")
        fragment_bytes += len(decoded)
    required_markers = [
        "<!-- Viewer interface -->",
        "<!-- Embedded IFC model manifest -->",
        "<!-- Embedded Fragments worker -->",
        "<!-- Embedded viewer application -->",
    ]
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise ValueError(f"Generated HTML comments are incomplete: {missing}")
    return {
        "passed": True,
        "checks": [
            "HTML file created and readable",
            "No external dependencies detected",
            f"{len(models)} model fragment(s) embedded",
            f"{fragment_bytes:,} fragment bytes decoded successfully",
            "Commented viewer sections present",
        ],
        "embeddedModels": len(models),
        "fragmentBytes": fragment_bytes,
    }


def _render_html(manifest: dict, options: ViewerOptions) -> str:
    """Create the single-file viewer document from validated data and resources."""

    css = _resource("src", "web", "style.css").read_text("utf-8")
    viewer_js = _resource("dist", "viewer.js").read_text("utf-8")
    worker_js = _resource("dist", "worker.js").read_text("utf-8")
    safe_json = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = html.escape(options.title, quote=True)
    prepared_by = html.escape(options.prepared_by, quote=True)
    created = html.escape(options.creation_date, quote=True)
    speed = f"{options.flight_speed:g}"
    speed_label = f"{options.flight_speed:.1f}"
    prepared_line = f"<div>Prepared by <strong>{prepared_by}</strong></div>" if prepared_by else ""

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="generator" content="IFC HTML Generator by waabe.de">
<title>{title}</title>
<!-- Self-contained viewer styles: no network resources are referenced. -->
<style>{css}</style>
</head>
<body>
<!-- Viewer interface -->
<div id="app">
<aside>
<h1>{title}</h1>
<div class="viewer-byline">
{prepared_line}<div>Created on <strong>{created}</strong></div>
<div>Created and distributed by <strong>waabe.de</strong><br><span>n.rube@waabe.de</span></div>
</div>
<div class="viewer-toolbar">
<button id="fit">Fit view</button>
<label class="toolbar-toggle"><input id="showIfcGrids" type="checkbox" checked> IFC grids</label>
<label class="toolbar-toggle" title="Enabled: rotate the view around the current camera position"><input id="flightMouse" type="checkbox"> Flight mouse</label>
<div class="navigation-help"><strong>Controls:</strong> IFC grids toggles grid visibility. Flight mouse rotates the view around the current camera position; WASD remains active. Speed is adjusted only with the slider.</div>
<div class="fly-controls" title="W/S: forward and backward · A/D: strafe left and right">
<strong>WASD</strong>
<label for="flySpeed">Speed</label>
<input id="flySpeed" type="range" min="0.5" max="50" step="0.5" value="{speed}" aria-label="Navigation speed">
<output id="flySpeedValue" for="flySpeed">{speed_label}</output>
</div>
</div>
<details id="clip-panel" class="panel-section" open>
<summary>Section tool</summary>
<div class="panel-content clip-panel-content">
<div class="clip-axis-row"><strong>X</strong><label>+X<input id="clipXPositive" type="range" min="0" max="100" value="100"></label><label>−X<input id="clipXNegative" type="range" min="0" max="100" value="100"></label></div>
<div class="clip-axis-row"><strong>Y</strong><label>+Y<input id="clipYPositive" type="range" min="0" max="100" value="100"></label><label>−Y<input id="clipYNegative" type="range" min="0" max="100" value="100"></label></div>
<div class="clip-axis-row"><strong>Z</strong><label>+Z<input id="clipZPositive" type="range" min="0" max="100" value="100"></label><label>−Z<input id="clipZNegative" type="range" min="0" max="100" value="100"></label></div>
<button id="resetClip">Reset sections</button>
</div>
</details>
<details id="model-panel" class="panel-section" open>
<summary>Models and spatial structure</summary>
<div class="panel-content"><div id="models"></div></div>
</details>
<details id="property-panel-section" class="panel-section" open>
<summary id="property-title">Properties</summary>
<div class="panel-content"><div id="props" class="property-panel"><div class="property-empty">Click an element…</div></div></div>
</details>
<div id="status"></div>
</aside>
<main><canvas id="canvas"></canvas></main>
</div>
<!-- Embedded IFC model manifest -->
<script id="ifc-data" type="application/json">{safe_json}</script>
<!-- Embedded Fragments worker -->
<script id="fragments-worker" type="text/plain">{worker_js.replace('</script>', '<\\/script>')}</script>
<!-- Embedded viewer application -->
<script>{viewer_js.replace('</script>', '<\\/script>')}</script>
</body>
</html>'''


def convert(
    ifcs: list[Path],
    output: Path,
    options: ViewerOptions | None = None,
    progress: ProgressCallback | None = None,
) -> dict:
    """Validate IFC files and create one fully offline, post-validated HTML viewer."""

    if not ifcs:
        raise ValueError("At least one IFC file is required.")
    options = (options or ViewerOptions()).normalized()
    sources = [Path(path).expanduser().resolve() for path in ifcs]
    output = Path(output).expanduser().resolve()
    if output in sources:
        raise ValueError("The output HTML must not overwrite an input IFC file.")

    def report(message: str) -> None:
        LOG.info(message)
        if progress:
            progress(message)

    report("Validating IFC input files…")
    ifc_checks = [validate_ifc(path) for path in sources]
    _ensure_browser_bundles()
    manifest = {
        "format": "ifc-html-standalone",
        "version": 2,
        "viewer": {
            "title": options.title,
            "preparedBy": options.prepared_by,
            "creationDate": options.creation_date,
            "flightSpeed": options.flight_speed,
            "creator": "waabe.de",
            "contact": "n.rube@waabe.de",
        },
        "models": [],
    }
    fallback_total = 0
    fallback_failures: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="ifc-html-generator-") as temporary:
        temp = Path(temporary)
        used: set[str] = set()
        for index, src in enumerate(sources, start=1):
            report(f"Converting model {index}/{len(sources)}: {src.name}")
            mid = model_id(src, used)
            fragment = temp / f"{mid}.frag"
            prepared = temp / f"{mid}.prepared.ifc"
            fallback = prepare_for_fragments(src, prepared)
            fragment_source = Path(fallback["path"])
            fallback_total += fallback["converted"]
            fallback_failures.extend(fallback["failed"])
            if fallback["failed"]:
                details = ", ".join(
                    f"{item['class']} #{item['expressID']} ({item['GlobalId']}): {item['error']}"
                    for item in fallback["failed"]
                )
                raise RuntimeError(f"Geometry fallback failed for {src.name}: {details}")
            _run([
                _node_executable(),
                _resource("src", "node", "convert-ifc.mjs"),
                fragment_source,
                fragment,
            ])
            if not fragment.is_file() or fragment.stat().st_size == 0:
                raise RuntimeError(f"Fragments conversion produced no data for {src.name}.")
            metadata = extract_metadata(src, mid)
            manifest["models"].append({
                "modelId": mid,
                "name": src.name,
                "fragmentBase64": base64.b64encode(fragment.read_bytes()).decode("ascii"),
                "metadata": metadata,
                "geometryFallbacks": fallback["converted"],
            })

    report("Writing commented standalone HTML…")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_html(manifest, options), "utf-8")
    try:
        report("Validating generated HTML and embedded model data…")
        validation = validate_generated_html(output, len(sources))
    except Exception:
        output.unlink(missing_ok=True)
        raise

    warnings = sum(len(model["metadata"]["warnings"]) for model in manifest["models"]) + len(fallback_failures)
    report("HTML viewer created and validated successfully.")
    return {
        "output": str(output),
        "models": len(sources),
        "bytes": output.stat().st_size,
        "warnings": warnings,
        "geometryFallbacks": fallback_total,
        "geometryFallbackFailures": fallback_failures,
        "ifcChecks": ifc_checks,
        "validation": validation,
        "viewer": manifest["viewer"],
    }
