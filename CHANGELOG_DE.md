# IFC HTML Standalone – MVP

Dieses Projekt wandelt eine oder mehrere IFC-Dateien in **genau eine vollständig offline nutzbare HTML-Datei** um. Viewer-Code, Fragments-Worker, komprimierte Fragmentdaten und IFC-Metadaten werden inline eingebettet. Zur Laufzeit sind weder CDN noch Netzwerkzugriff erforderlich.

## Voraussetzungen

Die vorhandenen lokalen Installationen werden verwendet:

- Python `.venv` mit IfcOpenShell 0.8.5
- Node.js und `node_modules` mit `@thatopen/fragments` 3.4.7, Three.js, web-ifc und esbuild

## Start

Aus dem Projektordner in PowerShell:

```powershell
# CLI: eine IFC (das Startskript setzt PYTHONPATH automatisch)
.\ifc-html.cmd .\samples\generated_smoke.ifc -o .\output\generated_smoke.html

# CLI: mehrere IFC-Dateien in eine HTML
.\ifc-html.cmd .\a.ifc .\b.ifc -o .\output\combined.html

# Minimale Tkinter-GUI
.\ifc-html-gui.cmd
```

Alternativ ohne Editable-Install: `$env:PYTHONPATH="$PWD\src"` setzen.

## Entwicklung und Tests

```powershell
node .\src\node\build.mjs
node --test .\tests\node.test.mjs
$env:PYTHONPATH="$PWD\src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe .\samples\generate_smoke.py
```

## Architektur

- `src/ifc_html/core.py`: gemeinsamer Konvertierungskern, HTML-Assembly und Offline-Validator
- `src/ifc_html/metadata.py`: fehlertolerante IfcOpenShell-Metadatenextraktion
- `src/ifc_html/cli.py`, `gui.py`: CLI und Tkinter-Oberfläche
- `src/node/convert-ifc.mjs`: IFC → komprimierte Fragments (`IfcImporter`, lokales web-ifc WASM)
- `src/node/build.mjs`: esbuild-Bundles mit sandbox-robustem lokalem Resolver
- `src/web/viewer.js`: Three.js/FragmentsModels-Viewer
- `src/web/worker-entry.js`: lokal gebündelter Fragments-Worker, später als Blob-URL gestartet
- `samples/generated_smoke.ifc`: kleines, reproduzierbares IFC4-Testmodell mit Wandgeometrie

Jedes Modell erhält eine eindeutige `modelId` aus bereinigtem Dateinamen plus SHA-256-Anteil des absoluten Pfads; Kollisionen werden suffixiert.

## Implementierter MVP-Umfang

- Multi-IFC, Modellliste und Sichtbarkeit
- Orbit-Navigation und Fit View
- Klick-Raycast, Highlight und Metadatenanzeige
- temporäre X/Y/Z-Clipping-Planes plus Reset
- IFC-Schema, Entitäten und Kernattribute; Psets/Qtos; Typ, Material, Klassifikation, räumlicher Container/Struktur und Presentation Layer, jeweils fehlertolerant
- Inline-CSS, Inline-JS, Inline-Worker, Base64-Fragments und Inline-Metadaten
- Validator gegen externe `src`/`href` sowie direkte externe `fetch`/`importScripts`

## Korrekturstand v0.2

- Die Mausauswahl übergibt absolute Pointer-Koordinaten an den nativen `FragmentsModel.raycast(...)`; die zuvor doppelt normalisierten Koordinaten wurden entfernt.
- Klick und Orbit-Drag werden über eine Bewegungsschwelle getrennt.
- Highlighting läuft direkt über `FragmentsModel.highlight(...)`.
- Die Schnitt-Slider liefern native `THREE.Plane`-Objekte über `FragmentsModel.getClippingPlanesEvent` an Fragments.
- Änderungen an Kamera oder Schnittlage werden über einen serialisierten `FragmentsModels.update(...)`-Zyklus verarbeitet; parallele Updates pro Renderframe wurden entfernt.

## Korrekturstand v0.3

- Aktive X-/Y-/Z-Schnitte besitzen jetzt sichtbare 3D-Ebenen im Modell.
- Farbcodierung: X rot, Y grün, Z blau.
- Die halbtransparenten Flächen und Rahmen bewegen sich synchron mit den Slidern.
- Bei Sliderstellung `100` ist der jeweilige Schnitt deaktiviert und seine Hilfsebene ausgeblendet.
- Größe und Mittelpunkt der Hilfsebenen werden aus der gemeinsamen Bounding Box der sichtbaren Modelle berechnet.

## Korrekturstand v0.4

- Die aktiven Schnitte werden zusätzlich in `WebGLRenderer.clippingPlanes` gesetzt – entsprechend der globalen That-Open-Clipper-Implementierung.
- Dadurch werden Dreiecke an der Ebene tatsächlich abgeschnitten, statt ausschließlich ganze Fragments-Objekte oder Tiles auf der ausgeblendeten Seite zu entfernen.
- Dieselben Ebenen bleiben parallel über `FragmentsModel.getClippingPlanesEvent` mit Fragments-Culling und Raycasting synchronisiert.
- Sichtbare Hilfsebenen und Slider bleiben unverändert erhalten.

## Korrekturstand v0.5

- Eigenschaften werden durch direkten Klick auf ein Bauteil in der 3D-Ansicht ausgewählt.
- Der Fragments-Raycaster liefert Modell, lokale Element-ID und IFC-Item-ID des tatsächlich getroffenen Bauteils.
- Das gewählte Bauteil erhält über `FragmentsModel.setColor(...)` eine kräftige gelbe Auswahlfarbe. Dadurch setzt Fragments intern die erforderlichen `_explicitProps`; die vorherige direkte Highlight-Definition konnte die Farbe unterdrücken.
- Zusätzlich umrahmt eine gelbe, tiefentestfreie Bounding Box das gewählte Bauteil.
- Beim nächsten Klick werden vorherige Farbe und Kontur entfernt.
- Die Property-Anzeige ist nach Identität, räumlicher Zuordnung, Typ, Material, Layer, Klassifikation, Property Sets und Quantity Sets gegliedert; rohe JSON-Ausgabe wurde entfernt.

## Korrekturstand v0.6

- Der falsch positionierte gelbe Bounding-Box-Rahmen wurde vollständig entfernt.
- Die funktionierende gelbe Farbhervorhebung des ausgewählten Bauteils bleibt erhalten.
- Das eingebettete JSON enthält für jedes auswählbare `IfcProduct` sämtliche direkten IFC-Attribute aus `get_info(recursive=False)`; IFC-Referenzen werden zyklusfrei als Express-ID und IFC-Klasse abgelegt.
- Die Property-Ansicht zeigt einen eigenen Abschnitt **IFC-ATTRIBUTE (JSON)** sowie Typ, Material, Layer, Klassifikationen, Property Sets und Quantity Sets.
- Verschachtelte Objekte und Listen werden rekursiv und lesbar dargestellt.
- Die Modellnavigation ist als aufklappbarer Baum aufgebaut: Modell → IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey → IFC-Klasse → Bauteil.
- Nicht räumlich zugeordnete Produkte werden separat unter **Ohne räumliche Zuordnung** dargestellt.
- Ein Bauteilklick im Baum verwendet `getLocalIdsFromItemIds(...)`, zeigt dieselben Eigenschaften und färbt dasselbe 3D-Bauteil gelb.
- Elementlisten einer IFC-Klasse werden erst beim Aufklappen erzeugt, damit große Modelle den Browser nicht mit tausenden DOM-Zeilen blockieren.
- Umfangreiche Metadaten werden nur für auswählbare `IfcProduct`-Objekte eingebettet; Relationen und Hilfsentities bleiben über Attribute, Typen, Psets und QTOs referenziert.

## Korrekturstand v0.7

- Das bisherige Text-/JSON-Feld wurde durch ein BIMcollab-/That-Open-artiges Property-Fenster mit horizontalen Registern und einer zweispaltigen **Eigenschaft/Wert**-Tabelle ersetzt.
- Register: **Summary**, **Attributes**, **Properties**, **Quantities**, **Location**, **Material** und **PartOf**.
- **Properties** enthält die Property Sets selbst als Gruppenzeilen und darunter ihre einzelnen Property-Werte.
- **Attributes** enthält alle direkten IFC-Attribute des gewählten Objekts.
- **Quantities** stellt Quantity Sets getrennt von Property Sets dar.
- **Location** zeigt den vollständigen räumlichen Pfad Project → Site → Building → Storey.
- **Material** zeigt die IFC-Materialreferenzen und Presentation Layer.
- **PartOf** zeigt Typ-, Container-, Aggregations- und Klassifikationsbeziehungen.
- Die Objektbenennung folgt der aktuellen That-Open-Konvention: primär `Name`, danach `type.Name`, danach IFC-Klasse und zuletzt die lokale ID.
- Die Baumselektion verwendet jetzt die öffentliche Fragments-`localId` direkt. Der vorherige Aufruf von `getLocalIdsFromItemIds(expressID)` war semantisch falsch, weil `itemId` ein interner Fragments-Index ist.
- 3D-Klick → passender Modellbaumpfad wird geöffnet, Baumzeile wird ausgewählt und Property-Register werden aktualisiert.
- Baumklick → dasselbe Bauteil wird im 3D-Modell gelb markiert und seine Property-Register werden geladen.
- Offizielle Referenzen: That Open `ItemsData`, `SpatialTree`, `FragmentsModel.raycast()` und `getItemsData()`.

## Korrekturstand v0.8

- Das Register **Summary** wurde vollständig entfernt.
- Verbleibende Register: **Attributes**, **Properties**, **Quantities**, **Location**, **Material** und **PartOf**.
- Gruppenzeilen in **Properties** und **Quantities** sind über Pfeil-Schaltflächen auf- und zuklappbar.
- Geöffnete Gruppen zeigen `▾`, geschlossene Gruppen `▸`; `aria-expanded` bildet den Zustand zusätzlich barrierearm ab.
- Beim Einklappen werden ausschließlich die Werte der gewählten Pset-/Qset-Gruppe ausgeblendet; benachbarte Gruppen bleiben unverändert.
- Property-Hintergrund, Tabellen, Register und Gruppen wurden auf Schwarz beziehungsweise Dunkelgrau mit weißer Schrift umgestellt.

## Korrekturstand v0.9

- Das bisherige generische Three.js-Bodenraster wurde entfernt.
- Reale `IfcGrid`-Objekte werden über die native Fragments-API `FragmentsModel.getGrids(...)` als 3D-Achslinien dargestellt.
- Rasterachsen sind cyan, ihre Achskennzeichnungen weiß; die dafür verwendete Helvetiker-Schrift ist lokal in das Viewer-Bundle eingebettet.
- Der neue Schalter **IFC-Raster** blendet alle Raster ein oder aus und ist standardmäßig aktiviert.
- Wird ein Modell im Modellbaum ausgeblendet, wird seine Rastergruppe synchron ebenfalls ausgeblendet.
- Der Structural-Testviewer lädt 8 Raster mit 56 darstellbaren Achsen; der kombinierte Viewer lädt 29 Raster mit 209 darstellbaren Achsen.
- Raster, Labels und Schalter funktionieren vollständig offline ohne CDN- oder Laufzeitabruf.
- Chrome-`file://`-Korrektur: Der inline gebündelte Fragments-Worker wird mit `classicWorker: true` als klassischer Blob-Worker gestartet. Dadurch blockiert Chrome den Worker beim direkten Öffnen der einzelnen HTML-Datei nicht mehr als origin-fremden ES-Modul-Worker.

## Korrekturstand v0.10

- Nicht von web-ifc/Fragments gerenderte `IfcSurfaceCurveSweptAreaSolid`-Bodies werden vor dem Fragments-Import in einer temporären IFC-Kopie mit IfcOpenShell tesselliert.
- Original-IFC, GlobalId, Express-ID, Properties und räumliche Zuordnung bleiben unverändert.
- Im Structural-Modell werden 4, im kombinierten Viewer insgesamt 56 Geometrien repariert; ein Fallback-Fehler bricht die Konvertierung ab, statt unsichtbare Bauteile zu erzeugen.

## Korrekturstand v0.11

- Der Schalter **IFC-Raster** besitzt nun einen vollständigen `change`-Handler und blendet alle geladenen Rastergruppen tatsächlich ein oder aus.
- Die individuelle Modellsichtbarkeit und der globale Rasterschalter werden gemeinsam ausgewertet.
- Rastergruppen sind Kinder des jeweiligen `model.object` und übernehmen dadurch exakt dieselbe Fragments-Auto-Koordination und Modelltransformation wie die Geometrie.
- Die bereits in Weltkoordinaten gelieferte `FragmentsModel.box` wird beim Einpassen nicht mehr ein zweites Mal mit `model.object.matrixWorld` transformiert.

## Korrekturstand v0.12

- Jede Raumachse besitzt zwei unabhängige Schneider: `−X`/`+X`, `−Y`/`+Y` und `−Z`/`+Z`.
- Die beiden Regler einer Achse stehen nebeneinander und schneiden mit entgegengesetzten Plane-Normalen von beiden Modellseiten nach innen.
- Alle sechs aktiven Clipping-Planes werden gleichzeitig an Three.js und Fragments übergeben; Raycasting und GPU-Clipping verwenden damit denselben begrenzten Schnittraum.
- **Schnittwerkzeug**, **Modelle und Baustruktur** sowie **Eigenschaften** sind drei voneinander unabhängige, standardmäßig geöffnete Klappbereiche.
- **Schnitte zurücksetzen** setzt alle sechs Regler und Schnitthelfer gemeinsam zurück.

## Korrekturstand v0.13

- Die Seitenleiste und alle Klappbereiche verwenden eine schwarze Darstellung mit weißer Beschriftung.
- Die Schnittregler besitzen browserübergreifend graue Tracks und graue Griffe für Chrome/Edge sowie Firefox.
- Die Seitenleiste wurde auf 500 Pixel erweitert; jeder der beiden Regler einer Achse erhält mindestens 190 Pixel Breite.
- Die Reihenfolge je Achse lautet `+X | −X`, `+Y | −Y` und `+Z | −Z`.
- Schnitt-Einstellungen, Modellübersicht und Property-Ansicht bleiben unabhängig einklappbar.

## Korrekturstand v0.14

- Die bisherige blaue Button-Darstellung wurde vollständig durch dunkelgraue Normal-, Hover- und Aktivzustände ersetzt.
- Alle Checkboxen, einschließlich IFC-Raster und Modell-Sichtbarkeit, verwenden eine eigene dunkelgraue Darstellung mit weißem Haken.
- Buttons, Checkboxen und der Checkbox-Container besitzen sichtbares Mouseover-Feedback.
- Die Tastaturfokussierung bleibt durch einen neutralgrauen Fokusrahmen erkennbar.

## Korrekturstand v0.15

- `W` und `S` bewegen Kamera und Orbit-Ziel entlang der aktuellen Blickrichtung vorwärts beziehungsweise rückwärts.
- `A` und `D` verschieben Kamera und Orbit-Ziel seitlich; diagonale Bewegung wird normalisiert.
- Der dunkelgraue `Speed`-Regler stellt die Fluggeschwindigkeit zwischen `0,5` und `50,0` Modelleinhheiten pro Sekunde ein.
- Die Bewegung ist bildratenunabhängig; die maximale Frame-Zeit ist gegen Sprünge nach Tabwechseln begrenzt.
- Tastatureingaben in Formularfeldern lösen keine Kamerabewegung aus. Bei Fokusverlust oder ausgeblendetem Tab werden aktive Navigationstasten zurückgesetzt.

## Korrekturstand v0.16

- Neben `IFC-Raster` steht die standardmäßig deaktivierte Checkbox `Flug-Maus`.
- Ist `Flug-Maus` aktiviert, dreht linkes Ziehen die Blickrichtung am eigenen Kamerastandpunkt; die Kameraposition bleibt dabei unverändert.
- Ist `Flug-Maus` deaktiviert, bleibt die bisherige Orbit-Rotation um das aktuelle Modellziel aktiv.
- Die vertikale Flugrotation ist kurz vor ±90 Grad begrenzt, um ein Umkippen der Kamera zu verhindern.
- Ein einfacher Linksklick wählt weiterhin IFC-Elemente aus; erst eine Ziehbewegung wird als Rotation behandelt.

## Korrekturstand v0.17

- `W/A/S/D` bleibt auch bei aktivierter und unmittelbar zuvor angeklickter `Flug-Maus`-Checkbox aktiv.
- Checkboxen und Range-Regler blockieren die Navigationstasten nicht mehr; echte Texteingabefelder schützen weiterhin vor unbeabsichtigter Kamerabewegung.
- Unter den Checkboxen wird eine Bedieninformation für `IFC-Raster`, `Flug-Maus`, `WASD` und `Speed` eingeblendet.
- Die Geschwindigkeit besitzt keine eigene Tastenbelegung und wird ausschließlich über den `Speed`-Regler eingestellt.

## Korrekturstand v0.18

- Die sichtbare Viewer-Oberfläche wurde vollständig auf Englisch umgestellt.
- Browser- und Seitentitel lauten `Free HTML Model Viewer`.
- Buttons, Checkboxen, Tooltips, Panels, Modellbaum-Zusatztexte, Statusmeldungen, Fehlertexte und Property-Tabellen sind englisch beschriftet.
- Die Property-Reiter lauten `Attributes`, `Properties`, `Quantities`, `Location`, `Material` und `Part of` und bleiben innerhalb der 500-Pixel-Seitenleiste nutzbar.
- In v0.18 stand `Created and distributed by waabe.de · n.rube@waabe.de` am unteren Rand; ein Lizenzhinweis wird nicht ausgegeben.

## Korrekturstand v0.19

- Der Erstellerhinweis steht nun direkt unter `Free HTML Model Viewer` statt am unteren Rand.
- `waabe.de` und `n.rube@waabe.de` werden auf einem dezenten dunkelgrauen Informationsfeld mit neutralgrauer Akzentlinie prominenter dargestellt.
- Der frühere Footer wurde entfernt, damit der Hinweis nur einmal erscheint.

## Bekannte MVP-Grenzen

- Die fünf bereitgestellten IFC-Dateien enthalten keine eigenständigen `IfcAnnotation`-, `IfcTextLiteral`- oder vergleichbaren 2D-Planobjekte. Vorhandene `Curve2D`-/`FootPrint`-Repräsentationen gehören zu Produkten und Rastern; eine pauschale Darstellung aller Produkt-Footprints als Planoverlay ist daher nicht automatisch aktiviert.
- Externe PDF-, DWG- oder Bildpläne benötigen vor einer 3D-Einblendung eine definierte Datei, Skalierung, Ausrichtung und Geschosshöhe.
- Für sehr große IFCs wird die HTML vollständig im Speicher zusammengesetzt; Produktionsreife für Very-Large-Modelle ist nicht behauptet.
- Base64 erhöht die Dateigröße. Der Browser muss das komplette HTML initial laden.
- Metadaten sind bewusst API-sicher/best-effort. Exotische benutzerdefinierte Beziehungen oder tief verschachtelte Presentation-Layer-Zuordnungen können fehlen; Kategorienfehler werden als Warnungen protokolliert.
- Auswahl ordnet Fragments `itemId` der IFC-`expressID` zu. Bei speziellen/delta-basierten Fragmentmodellen kann diese Zuordnung abweichen.
- Clipping ist temporär und wird nicht persistiert. Es gibt noch keine Mess-, Annotations- oder Exportfunktionen.
- Browser-Laufzeit wurde mit dem generierten Smoke-Modell geprüft; eine breite Browser-/GPU-Matrix und große reale IFC-Suite stehen aus.


