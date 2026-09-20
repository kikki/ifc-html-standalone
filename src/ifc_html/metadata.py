from __future__ import annotations
import hashlib
import json
import logging
from pathlib import Path
from typing import Any
import ifcopenshell
import ifcopenshell.util.element

LOG = logging.getLogger(__name__)

ATTRS = ("GlobalId", "Name", "Description", "ObjectType", "Tag", "PredefinedType")

def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "wrappedValue"):
        return _plain(value.wrappedValue)
    if hasattr(value, "id") and callable(value.id):
        result={"expressID":value.id(),"class":value.is_a()}
        for key in ("GlobalId","Name","Description","Identification","Category","LayerSetName"):
            nested=getattr(value,key,None)
            if nested is not None: result[key]=_plain(nested)
        return result
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return str(value)

def model_id(path: Path, used: set[str]) -> str:
    base = "".join(c if c.isalnum() else "_" for c in path.stem).strip("_") or "model"
    digest = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:10]
    candidate = f"{base}_{digest}"
    n = 2
    while candidate in used:
        candidate = f"{base}_{digest}_{n}"; n += 1
    used.add(candidate)
    return candidate

def _safe(label: str, fn, warnings: list[str], default=None):
    try:
        return fn()
    except Exception as exc:
        msg = f"{label}: {type(exc).__name__}: {exc}"
        warnings.append(msg); LOG.warning(msg)
        return default

def extract_metadata(path: Path, mid: str) -> dict[str, Any]:
    warnings: list[str] = []
    f = ifcopenshell.open(str(path))
    layer_by_item: dict[int, list[str]] = {}
    def layers():
        for layer in f.by_type("IfcPresentationLayerAssignment"):
            name = getattr(layer, "Name", None) or f"#{layer.id()}"
            for item in getattr(layer, "AssignedItems", ()) or ():
                layer_by_item.setdefault(item.id(), []).append(name)
    _safe("presentation layers", layers, warnings)

    def classifications_for(el):
        out=[]
        for rel in getattr(el, "HasAssociations", ()) or ():
            if rel.is_a("IfcRelAssociatesClassification"):
                c=rel.RelatingClassification
                out.append({k:_plain(getattr(c,k,None)) for k in ("Identification","ItemReference","Name","Description","Location","ReferencedSource") if getattr(c,k,None) is not None})
        return out

    elements=[]
    # Nur IfcProduct-Instanzen können als gerenderte Bauteile ausgewählt werden.
    # Relationen, Geometrie-Hilfsobjekte und Definitionen bleiben über Referenzen,
    # Typen, Psets und QTOs erreichbar, werden aber nicht als eigene Baumzeilen
    # vervielfacht. Das hält auch sehr große IFC-Dateien performant.
    for el in f.by_type("IfcProduct"):
        eid=el.id(); row={"expressID":eid,"class":el.is_a()}
        for a in ATTRS:
            v=_safe(f"#{eid} {a}", lambda a=a: getattr(el,a,None), warnings)
            if v is not None: row[a]=_plain(v)
        # Vollständige direkte STEP-Attribute für die Property-Ansicht. Referenzen
        # werden von _plain auf IFC-ID und Klasse reduziert, damit das JSON
        # zyklusfrei und vollständig offline serialisierbar bleibt.
        info=_safe(f"#{eid} attributes", lambda: el.get_info(recursive=False, include_identifier=False), warnings,{}) or {}
        row["attributes"]={str(k):_plain(v) for k,v in info.items() if k not in ("id","type") and v is not None}
        row["isProduct"]=bool(_safe(f"#{eid} product", lambda: el.is_a("IfcProduct"), warnings,False))
        row["hasRepresentation"]=bool(getattr(el,"Representation",None))
        row["propertySets"]=_safe(f"#{eid} psets", lambda: _plain(ifcopenshell.util.element.get_psets(el, psets_only=True)), warnings,{})
        row["quantitySets"]=_safe(f"#{eid} qtos", lambda: _plain(ifcopenshell.util.element.get_psets(el, qtos_only=True)), warnings,{})
        typ=_safe(f"#{eid} type", lambda: ifcopenshell.util.element.get_type(el), warnings)
        if typ: row["type"]={"expressID":typ.id(),"class":typ.is_a(),"Name":getattr(typ,"Name",None)}
        mat=_safe(f"#{eid} material", lambda: ifcopenshell.util.element.get_material(el, should_skip_usage=False), warnings)
        if mat: row["material"]=_plain(mat)
        cont=_safe(f"#{eid} container", lambda: ifcopenshell.util.element.get_container(el), warnings)
        if cont: row["spatialContainer"]={"expressID":cont.id(),"class":cont.is_a(),"Name":getattr(cont,"Name",None)}
        aggregate=_safe(f"#{eid} aggregate", lambda: ifcopenshell.util.element.get_aggregate(el), warnings)
        if aggregate: row["partOf"]={"expressID":aggregate.id(),"class":aggregate.is_a(),"Name":getattr(aggregate,"Name",None)}
        cls=_safe(f"#{eid} classifications", lambda: classifications_for(el), warnings,[])
        if cls: row["classifications"]=cls
        # Product representation items can carry layer assignments.
        assigned=[]
        rep=getattr(el,"Representation",None)
        if rep:
            for r in getattr(rep,"Representations",()) or ():
                assigned.extend(layer_by_item.get(r.id(),[]))
                for it in getattr(r,"Items",()) or (): assigned.extend(layer_by_item.get(it.id(),[]))
        if assigned: row["presentationLayers"]=sorted(set(assigned))
        elements.append(row)
    spatial=[]
    roots=list(f.by_type("IfcProject"))
    spatial_entities=[]
    spatial_class_used=None
    spatial_candidates=("IfcSpatialStructureElement","IfcSpatialElement") if str(f.schema).upper().startswith("IFC2X3") else ("IfcSpatialElement","IfcSpatialStructureElement")
    for spatial_class in spatial_candidates:
        try:
            spatial_entities=list(f.by_type(spatial_class))
            spatial_class_used=spatial_class
            break
        except (RuntimeError,ValueError):
            continue
    if spatial_class_used is None:
        warnings.append(f"{f.schema}: no supported spatial base class was available; spatial structure may be incomplete")
    for e in roots + spatial_entities:
        parent=_safe(f"#{e.id()} spatial parent",lambda e=e: ifcopenshell.util.element.get_aggregate(e),warnings)
        if parent is None:
            parent=_safe(f"#{e.id()} spatial container",lambda e=e: ifcopenshell.util.element.get_container(e),warnings)
        spatial.append({"expressID":e.id(),"class":e.is_a(),"GlobalId":getattr(e,"GlobalId",None),"Name":getattr(e,"Name",None),"LongName":getattr(e,"LongName",None),"parent":parent.id() if parent else None})
    return {"modelId":mid,"sourceName":path.name,"schema":f.schema,"entityCount":sum(1 for _ in f),"productCount":len(elements),"elements":elements,"spatialStructure":spatial,"warnings":warnings}
