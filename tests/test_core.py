import base64
import os
import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from ifc_html.core import (
    ViewerOptions,
    _render_html,
    validate_generated_html,
    validate_html,
    validate_ifc,
)
from ifc_html.geometry_fallback import prepare_for_fragments


_private_ifc_value = os.environ.get("IFC_PRIVATE_REGRESSION_MODEL", "" )
PRIVATE_REGRESSION_IFC = Path(_private_ifc_value) if _private_ifc_value else None


class TestValidator(unittest.TestCase):
    def test_external(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "external.html"
            path.write_text('<script src="https://example.com/x.js"></script>', encoding="utf8")
            self.assertTrue(validate_html(path))

    def test_inline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "inline.html"
            path.write_text("<script>console.log(1)</script>", encoding="utf8")
            self.assertFalse(validate_html(path))

    def test_commented_generated_html_and_embedded_fragment_validation(self):
        manifest = {
            "format": "ifc-html-standalone",
            "version": 2,
            "models": [
                {
                    "modelId": "test-model",
                    "name": "test.ifc",
                    "fragmentBase64": base64.b64encode(b"fragment-data").decode("ascii"),
                    "metadata": {"warnings": []},
                }
            ],
        }
        options = ViewerOptions(
            title="Test & Review",
            prepared_by="Jane <BIM>",
            flight_speed=7.5,
            creation_date="2026-09-20",
        ).normalized()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "viewer.html"
            path.write_text(_render_html(manifest, options), encoding="utf8")
            result = validate_generated_html(path, 1)
            text = path.read_text("utf8")
        self.assertTrue(result["passed"])
        self.assertEqual(result["embeddedModels"], 1)
        self.assertIn("<title>Test &amp; Review</title>", text)
        self.assertIn("Prepared by <strong>Jane &lt;BIM&gt;</strong>", text)
        self.assertIn("Created on <strong>2026-09-20</strong>", text)
        self.assertIn('value="7.5" aria-label="Navigation speed"', text)
        self.assertIn("Created and distributed by <strong>waabe.de</strong>", text)
        self.assertIn("<!-- Embedded IFC model manifest -->", text)


class TestIfcPreflight(unittest.TestCase):
    @unittest.skipUnless(
        bool(PRIVATE_REGRESSION_IFC and PRIVATE_REGRESSION_IFC.is_file()),
        "set IFC_PRIVATE_REGRESSION_MODEL to run this private regression test",
    )
    def test_real_ifc_loads_with_project_and_products(self):
        report = validate_ifc(PRIVATE_REGRESSION_IFC)
        self.assertEqual(report["status"], "IFC loaded successfully (IFC4X3)")
        self.assertEqual(report["schema"], "IFC4X3")
        self.assertEqual(report["spatialClass"], "IfcSpatialElement")
        self.assertGreaterEqual(report["projects"], 1)
        self.assertGreater(report["products"], 0)

    def test_ifc4_release_variants_are_informational_and_supported(self):
        for schema in ("IFC4", "IFC4X1", "IFC4X2", "IFC4X3"):
            with self.subTest(schema=schema), tempfile.TemporaryDirectory() as folder:
                model = ifcopenshell.file(schema=schema)
                model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name=f"{schema} test project")
                model.create_entity("IfcBuilding", GlobalId=ifcopenshell.guid.new(), Name=f"{schema} test building")
                path = Path(folder) / f"{schema.lower()}_preflight.ifc"
                model.write(path)
                report = validate_ifc(path)
                self.assertEqual(report["schema"], schema)
                self.assertEqual(report["status"], f"IFC loaded successfully ({schema})")
                self.assertEqual(report["spatialClass"], "IfcSpatialElement")
                self.assertEqual(report["spatialElements"], 1)
                self.assertFalse(report["notices"])

    def test_ifc2x3_uses_spatial_structure_element(self):
        model = ifcopenshell.file(schema="IFC2X3")
        model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="IFC2X3 test project")
        model.create_entity("IfcBuilding", GlobalId=ifcopenshell.guid.new(), Name="IFC2X3 test building")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ifc2x3_preflight.ifc"
            model.write(path)
            report = validate_ifc(path)
        self.assertEqual(report["schema"], "IFC2X3")
        self.assertEqual(report["status"], "IFC loaded successfully (IFC2X3)")
        self.assertEqual(report["spatialClass"], "IfcSpatialStructureElement")
        self.assertEqual(report["spatialElements"], 1)
        self.assertFalse(report["notices"])

    def test_options_require_title_and_bounded_speed(self):
        with self.assertRaises(ValueError):
            ViewerOptions(title=" ").normalized()
        with self.assertRaises(ValueError):
            ViewerOptions(flight_speed=50.5).normalized()


class TestGeometryFallback(unittest.TestCase):
    @unittest.skipUnless(
        bool(PRIVATE_REGRESSION_IFC and PRIVATE_REGRESSION_IFC.is_file()),
        "set IFC_PRIVATE_REGRESSION_MODEL to run this private regression test",
    )
    def test_surface_curve_swept_beam_is_tessellated(self):
        source = PRIVATE_REGRESSION_IFC
        prepared = Path(".tmp/test_structural_prepared.ifc")
        result = prepare_for_fragments(source, prepared)
        self.assertEqual(result["converted"], 4)
        self.assertFalse(result["failed"])
        model = ifcopenshell.open(prepared)
        target = model.by_guid("0Ww6qbe0r3FPSKaH3Gfoge")
        self.assertEqual(target.id(), 2179)
        body = [
            representation
            for representation in target.Representation.Representations
            if representation.RepresentationIdentifier == "Body"
        ]
        types = {
            item.is_a()
            for representation in body
            for item in model.traverse(representation)
        }
        self.assertNotIn("IfcSurfaceCurveSweptAreaSolid", types)
        self.assertIn("IfcPolygonalFaceSet", types)
        prepared.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
