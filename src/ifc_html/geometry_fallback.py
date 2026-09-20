from __future__ import annotations

import logging
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import numpy as np
from ifcopenshell.api.geometry import add_mesh_representation, edit_object_placement

LOG = logging.getLogger(__name__)
UNSUPPORTED_BODY_ITEMS = {"IfcSurfaceCurveSweptAreaSolid"}


def _body_representations(product):
    definition = getattr(product, "Representation", None)
    if not definition:
        return []
    return [
        representation
        for representation in definition.Representations
        if representation.RepresentationIdentifier == "Body"
    ]


def _requires_tessellation(model, product) -> bool:
    return any(
        item.is_a() in UNSUPPORTED_BODY_ITEMS
        for representation in _body_representations(product)
        for item in model.traverse(representation)
    )


def prepare_for_fragments(source: Path, output: Path) -> dict:
    """Write a temporary IFC with unsupported body solids converted to meshes.

    The source IFC is never modified. Products keep their original IFC identity,
    relations and metadata. Their generated mesh vertices use world coordinates;
    the temporary product placement is therefore reset to world identity.
    """
    model = ifcopenshell.open(source)
    candidates = [
        product
        for product in model.by_type("IfcProduct")
        if _requires_tessellation(model, product)
    ]
    if not candidates:
        return {"path": source, "converted": 0, "failed": []}

    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    converted = 0
    failed: list[dict] = []

    for product in candidates:
        try:
            body_representations = _body_representations(product)
            body_context = body_representations[0].ContextOfItems
            shape = ifcopenshell.geom.create_shape(settings, product)
            vertices = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
            faces = np.asarray(shape.geometry.faces, dtype=int).reshape(-1, 3)
            if not len(vertices) or not len(faces):
                raise ValueError("IfcOpenShell returned no triangles")

            mesh_representation = add_mesh_representation(
                model,
                context=body_context,
                vertices=[vertices.tolist()],
                faces=[faces.tolist()],
            )
            original_representations = list(product.Representation.Representations)
            non_body = [
                representation
                for representation in original_representations
                if representation.RepresentationIdentifier != "Body"
            ]
            product.Representation.Representations = tuple(
                [mesh_representation, *non_body]
            )
            edit_object_placement(
                model,
                product=product,
                matrix=np.eye(4),
                is_si=True,
                should_transform_children=False,
            )
            converted += 1
        except Exception as exc:  # best effort; retain the original representation
            failed.append(
                {
                    "expressID": product.id(),
                    "class": product.is_a(),
                    "GlobalId": getattr(product, "GlobalId", None),
                    "error": str(exc),
                }
            )
            LOG.warning(
                "Fallback tessellation failed for %s #%s: %s",
                product.is_a(),
                product.id(),
                exc,
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    model.write(output)
    return {"path": output, "converted": converted, "failed": failed}
