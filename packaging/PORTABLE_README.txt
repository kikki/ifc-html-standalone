IFC HTML Generator 1.0
======================

Purpose
-------
Create one fully offline HTML model viewer from one or more IFC files.
The generated HTML can be opened directly in current Chrome, Edge or Firefox.

Start
-----
1. Keep the complete portable folder together.
2. Double-click "IFC HTML Generator.exe".
3. Enter the viewer title, optional prepared-by name and initial flight speed.
4. Add one or more IFC models.
5. Confirm that every model shows "Loaded successfully".
6. Click "Create standalone HTML..." and select the output file.
7. Wait for the "HTML creation complete" information window.

Checks performed
----------------
- Every input must be a readable .ifc file.
- IfcOpenShell must find an IfcProject.
- Schema, product count and spatial elements are reported.
- IFC2X3, IFC4, IFC4X1, IFC4X2 and IFC4X3 use their available spatial base class.
- Schema detection is informational: an unknown spatial class skips only the spatial count and does not prevent conversion.
- Unsupported advanced swept geometry is converted through the validated fallback.
- Every IFC is converted into a non-empty Fragments payload.
- The final HTML is checked for external dependencies.
- Every embedded model payload is Base64-decoded and checked for content.
- Required comments and embedded viewer sections are checked.

Viewer metadata
---------------
- Viewer title: configurable.
- Prepared by: optional.
- Creation date: added automatically.
- Initial flight speed: configurable from 0.5 to 50.0.
- "Created and distributed by waabe.de · n.rube@waabe.de" is always included.

Portable runtime
----------------
The application uses only the Python, Dear PyGui, Node.js, IfcOpenShell,
That Open Fragments, Three.js and web-ifc runtime files included in this folder.
Separate Python and Node.js installations are not required.

Do not move or delete the _internal or runtime folders next to the EXE.
