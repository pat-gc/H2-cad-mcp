"""Pure source extrusion mapping. No allocation, transport, or journal mutation.

The current writer must still journal the returned exact expected tree and verify
saved state independently. A whole-sketch query is not proof of region count or
regenerated solids. Numeric quantity values here are source seeds, not evaluation.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Sequence

from .backend import Unsupported
from .model import Feature, Target, canonical
from .native import _verify_source_region_query, stage_length_variable

_REGION = re.compile(r'query=qSketchRegion\(makeId\("([^"\\]+)"\)\);\Z')
_LITERAL = re.compile(r'[+]?(?:\d+(?:\.\d*)?|\.\d+)\s*mm\Z')


def stage_source_extrusion(feature: Feature, variables: Sequence[Feature] = ()) -> dict:
    """Validate source provenance and retain a literal/direct-variable depth."""
    raw = feature.provenance.get("fsgen_feature_json")
    if (feature.kind != "extrude" or not isinstance(raw, dict)
            or raw.get("btType") != "BTMFeature-134" or raw.get("featureType") != "extrude"
            or raw.get("name") != feature.logical_id):
        raise Unsupported("Original FSGen extrusion template required")
    params = raw.get("parameters")
    if not isinstance(params, list) or any(not isinstance(p, dict) or not p.get("parameterId") for p in params):
        raise Unsupported("Complete source extrusion parameters required")
    projection, schema = {}, {}
    for p in params:
        key = p["parameterId"]
        if key in projection:
            raise Unsupported("Duplicate source extrusion parameter")
        if "queries" in p:
            if not isinstance(p["queries"], list) or any(not isinstance(q, dict) for q in p["queries"]):
                raise Unsupported("Invalid source extrusion queries")
            value = [q.get("queryString") for q in p["queries"]]
        else:
            value = p.get("expression", p.get("value"))
        projection[key] = value
        schema[key] = {k: v for k, v in p.items() if k not in {"expression", "value", "queries"}}
    if (canonical(projection) != canonical(feature.parameters)
            or canonical(schema) != canonical(feature.structure.get("parameter_schema"))
            or canonical({k: v for k, v in raw.items() if k != "parameters"})
            != canonical(feature.structure.get("fsgen_native"))):
        raise Unsupported("Extrusion source and semantic projection differ")
    for key, value in (("domain", "MODEL"), ("bodyType", "SOLID"), ("operationType", "NEW"), ("endBound", "BLIND")):
        if projection.get(key) != value:
            raise Unsupported("Only MODEL/SOLID/NEW/BLIND source extrusions are supported")
    for key in ("midplane", "oppositeDirection", "hasOffset", "hasExtrudeDirection", "startOffset",
                "symmetric", "hasDraft", "hasSecondDirection"):
        if projection.get(key) is not False:
            raise Unsupported("Offset, symmetric, reversed or draft extrusion is unsupported")
    queries = projection.get("entities")
    match = _REGION.fullmatch(queries[0]) if isinstance(queries, list) and len(queries) == 1 and isinstance(queries[0], str) else None
    if not match:
        raise Unsupported("One whole-source-sketch region query required")
    expression = projection.get("depth")
    if not isinstance(expression, str):
        raise Unsupported("Source depth expression required")
    dependencies = {match[1]}
    variable = None
    if _LITERAL.fullmatch(expression.strip()):
        value = float(expression.strip()[:-2])
    elif re.fullmatch(r"#[A-Za-z][A-Za-z0-9_]*", expression):
        candidates = [v for v in variables if v.logical_id == expression]
        if len(candidates) != 1:
            raise Unsupported("One source length variable is required for depth")
        variable = stage_length_variable(candidates[0])
        value = float(variable["expression"].strip()[:-2])
        dependencies.add(expression)
    else:
        raise Unsupported("Only positive literal or direct length-variable depths are supported")
    if not math.isfinite(value) or not 0 < value <= 1000 or set(feature.dependencies) != dependencies:
        raise Unsupported("Source depth bounds or dependency identities differ")
    return {"logical_id": feature.logical_id, "sketch_logical_id": match[1], "depth_expression": expression,
            "depth_seed_mm": value, "source_template": copy.deepcopy(raw), "variable": variable,
            "regeneration_verified": False, "solid_geometry_verified": False}


def map_source_extrusion(before: dict, feature: Feature, *, target: Target, sketch_feature_id: str,
                         sketch_definition: dict, query_response: dict,
                         variables: Sequence[Feature] = ()) -> dict:
    """Map only depth on a UI-created draft already bound to the exact sketch.

    ``sketch_definition`` must come from the caller's previously observed source
    sketch operation. This pure function does not authenticate journal provenance.
    """
    staged = stage_source_extrusion(feature, variables)
    if (before.get("target") != {"did": target.did, "wid": target.wid, "eid": target.eid}
            or before.get("connected") is not True
            or not re.fullmatch(r"[a-f0-9]{24}", str(before.get("element_microversion", "")))):
        raise Unsupported("Exact connected extrusion target/revision required")
    tree = before.get("tree", {})
    children = tree.get("children")
    if not isinstance(children, list) or tree.get("$type") != "bsedit.GBTMModel":
        raise Unsupported("Complete native model tree required")
    sketches = [n for n in children if n.get("featureId") == sketch_feature_id]
    if (len(sketches) != 1 or sketches[0] != sketch_definition
            or sketch_definition.get("featureType") != "newSketch" or not sketch_definition.get("nodeId")):
        raise Unsupported("Exact previously observed source sketch definition required")
    fid = before.get("editingFeatureId")
    matches = [n for n in children if fid and n.get("featureId") == fid]
    if (len(matches) != 1 or matches[0].get("featureType") != "extrude" or not matches[0].get("nodeId")
            or matches[0].get("suppressed") is not False):
        raise Unsupported("One active UI-allocated native extrusion required")
    draft = matches[0]
    params = draft.get("parameters", [])
    by_id = {p.get("parameterId"): p for p in params}
    source = staged["source_template"]["parameters"]
    if len(by_id) != len(params) or set(by_id) != {p["parameterId"] for p in source}:
        raise Unsupported("Native extrusion parameter schema differs")
    for p in source:
        actual = by_id[p["parameterId"]]
        if actual.get("$type") != "bsedit.G" + p["btType"].split("-")[0] or not actual.get("nodeId"):
            raise Unsupported("Native extrusion parameter type or identity differs")
        if p["parameterId"] in {"entities", "depth"}:
            continue
        for key in ("value", "expression", "enumName", "queries"):
            if key in p and actual.get(key) != p[key]:
                raise Unsupported("Native extrusion defaults differ from source semantics")
    depth, regions = by_id["depth"], by_id["entities"].get("queries")
    if (depth.get("units") != "millimeter" or type(depth.get("value")) not in (float, int)
            or not math.isfinite(depth["value"]) or depth["value"] <= 0
            or depth.get("expression") != f'{depth["value"]:g} mm'):
        raise Unsupported("Fresh literal native extrusion depth required")
    if (not isinstance(regions, list) or len(regions) != 1
            or regions[0].get("$type") != "bsedit.GBTMIndividualSketchRegionQuery"
            or regions[0].get("featureId") != sketch_feature_id or regions[0].get("filterInnerLoops") is not True):
        raise Unsupported("Observed whole-sketch region selection required; single canvas face is insufficient")
    _verify_source_region_query(query_response, regions[0], sketch_feature_id)
    expected = copy.deepcopy(tree)
    result = next(n for n in expected["children"] if n.get("featureId") == fid)
    next(p for p in result["parameters"] if p["parameterId"] == "depth").update(
        expression=staged["depth_expression"], value=staged["depth_seed_mm"])
    return {**staged, "feature_id": fid, "sketch_feature_id": sketch_feature_id,
            "expected_tree": expected, "source_region_verified": True,
            "region_count_verified": False, "ready_to_submit": False}
