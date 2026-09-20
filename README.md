# IFC HTML Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

IFC HTML Generator creates one fully self-contained, offline HTML model viewer from one or more IFC files. The HTML embeds the viewer code, Fragments worker, compressed model data, IFC metadata and interface resources. It opens directly from `file://` in current Chrome, Edge and Firefox without a server, CDN or network connection.

Created and maintained by [waabe.de](https://waabe.de)  
Contact: [n.rube@waabe.de](mailto:n.rube@waabe.de)

Use the source code, build your own version, or use the ready-to-run Windows application. The project is released under the [MIT License](LICENSE).

The previous German implementation history is preserved in [CHANGELOG_DE.md](CHANGELOG_DE.md).

## Download the portable Windows application

Download the latest portable ZIP from [GitHub Releases](https://github.com/kikki/ifc-html-standalone/releases/latest).

Extract the complete archive and double-click `IFC HTML Generator.exe`. Keep the `_internal` and `runtime` directories next to the executable. The target computer does not need Python or Node.js installed.

Application workflow:

1. Enter the viewer title.
2. Optionally enter the person who prepared the viewer.
3. Set the initial flight speed from 0.5 to 50.0.
4. Add one or more IFC files.
5. Confirm that each model reports `Loaded successfully`.
6. Select `Create standalone HTML...` and choose the output file.
7. Wait for the `HTML creation complete` information dialog.

Every generated viewer contains:

- the configurable viewer title;
- the optional `Prepared by` name;
- the automatic creation date;
- the configured initial flight speed;
- the fixed attribution `Created and distributed by waabe.de · n.rube@waabe.de`;
- commented HTML sections for the interface, IFC manifest, worker and viewer application.

## Input and output validation

Before conversion, each input is checked with IfcOpenShell for:

- a readable `.ifc` file;
- the IFC schema reported by IfcOpenShell, including IFC2X3, IFC4, IFC4X1, IFC4X2 and IFC4X3;
- at least one `IfcProject`;
- product and spatial element counts using the spatial base class exposed by that schema.

Schema detection is informational. A readable IFC is not rejected merely because a release uses another spatial base-class name. The application tries `IfcSpatialElement` and `IfcSpatialStructureElement`; if neither is exposed, it reports that spatial counting was skipped and continues with conversion.

After conversion, the application verifies:

- that the HTML file exists and is readable;
- that it contains no external runtime dependencies;
- that the expected number of model fragments is embedded;
- that every embedded Base64 fragment decodes and is non-empty;
- that the required commented viewer sections are present.

Unsupported `IfcSurfaceCurveSweptAreaSolid` bodies are tessellated in a temporary IFC copy. The original IFC, GlobalId, Express ID, properties and spatial relationships are preserved. A failed fallback aborts conversion instead of producing silently missing geometry.

## Functionality preview

### Generator and IFC preflight

The desktop application collects one or more IFC models, checks each readable file with IfcOpenShell and reports its schema, product count and spatial-structure status before conversion. Viewer title, optional author information and initial flight speed are configured in the same interface.

![IFC HTML Generator with validated IFC models](docs/images/generator-preflight.png)

### Offline multi-model viewer

The generated HTML opens directly from `file://`. It combines the embedded models in one 3D scene and provides independent model visibility, a hierarchical model and spatial tree, IFC grids, element selection and property tabs.

![Standalone viewer with multiple embedded IFC models and spatial tree](docs/images/viewer-model-structure.png)

### Navigation and section tool

The viewer supports orbit navigation, optional flight-mouse navigation and frame-rate-independent WASD movement with configurable speed. Six independent clipping controls cut the model from the positive and negative X, Y and Z directions.

![Standalone viewer with six-sided section controls](docs/images/viewer-section-tool.png)

## Viewer functions

- Multiple IFC models with independent visibility.
- Hierarchical model and spatial tree.
- Direct 3D and tree selection with yellow highlighting.
- Property tabs for Attributes, Properties, Quantities, Location, Material and Part of.
- Native IFC grid display.
- Six-sided GPU clipping.
- Orbit navigation and optional flight-mouse navigation.
- Frame-rate-independent WASD movement with configurable speed.
- Fully offline classic Blob worker for direct `file://` use.

## Standalone HTML example

Download [Free HTML Model Viewer](examples/html/Free-HTML-Model-Viewer.html) and open it locally in a current Chrome, Edge or Firefox browser. The example is intentionally large because all viewer code, resources, metadata and model fragments are embedded in this single offline HTML file.

The IFC sample models used to create this example originate from [youshengCode/IfcSampleFiles](https://github.com/youshengCode/IfcSampleFiles). The source IFC files are not included in this repository.

## Development setup

Requirements for development only:

- Python 3.11 or 3.12
- uv
- Node.js

From PowerShell in the project root:

```powershell
uv sync --extra build
node .\src\node\build.mjs
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node --test .\tests\node.test.mjs
```

Run the development GUI:

```powershell
.\.venv\Scripts\python.exe -m ifc_html.gui
```

Run the CLI:

```powershell
.\.venv\Scripts\python.exe -m ifc_html.cli `
  .\samples\001_082026_Architectural_L01.ifc `
  .\samples\001_082026_Structural_L01.ifc `
  -o .\output\coordination.html `
  --title "Factory Coordination Model" `
  --prepared-by "Example Author" `
  --flight-speed 8.5
```

## Build the portable application

```powershell
powershell -ExecutionPolicy Bypass -File .\build_portable.ps1
```

The build script:

1. synchronizes the uv environment;
2. builds the browser bundles;
3. runs the Python and Node test suites;
4. creates the PyInstaller application folder;
5. adds the private Node.js runtime;
6. adds usage and license documentation;
7. runs a packaged-resource self-test.

Output:

```text
dist-portable\IFC HTML Generator\IFC HTML Generator.exe
```

## Project structure

- `src/ifc_html/core.py` — conversion pipeline, configuration and final validation.
- `src/ifc_html/gui.py` — English native desktop GUI.
- `src/ifc_html/cli.py` — command-line interface.
- `src/ifc_html/metadata.py` — IFC metadata extraction.
- `src/ifc_html/geometry_fallback.py` — advanced swept-solid fallback.
- `src/node/convert-ifc.mjs` — IFC to Fragments conversion.
- `src/node/build.mjs` — browser bundle build.
- `src/web/viewer.js` — offline Three.js/Fragments viewer.
- `packaging/IFC_HTML_Generator.spec` — PyInstaller configuration.
- `build_portable.ps1` — reproducible portable-folder build.
- `tests/` — Python and Node validation tests.

## Current technical versions

- IfcOpenShell 0.8.5
- That Open Fragments 3.4.7
- Three.js 0.186
- Node.js 24.15.0 in the portable folder
- Dear PyGui 2.1.1
- PyInstaller 6.16.0
