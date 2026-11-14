"""Source-faithful rectangle staging, not a native sketch submission plan.

Line geometry uses the plate's observed native curve types. The two external
Origin dimensions are deliberately not serialized: their native reference and
signed placement semantics still require captured editor/solver evidence.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Sequence

from .backend import Unsupported
from .fsgen import FsgenCompileError, _semantic_native_body
from .model import Feature
from .native import stage_length_variable
from .native_planes import _linear_expression


def stage_source_rectangle(feature: Feature, *, variables: Sequence[Feature] = ()) -> dict:
    raw = feature.provenance.get("fsgen_feature_json")
    if (feature.kind != "newSketch" or not isinstance(raw, dict)
            or raw.get("btType") != "BTMSketch-151" or raw.get("featureType") != "newSketch"
            or raw.get("name") != feature.logical_id):
        raise Unsupported("Original FSGen rectangle source required")
    try:
        if _semantic_native_body(raw) != feature.structure.get("fsgen_native"):
            raise Unsupported("Rectangle source semantic provenance differs")
    except FsgenCompileError as exc:
        raise Unsupported("Invalid rectangle source provenance") from exc
    params = raw.get("parameters")
    if (not isinstance(params, list) or len(params) != 1
            or feature.structure.get("parameter_schema") != {"sketchPlane": {
                "btType": "BTMParameterQueryList-148", "parameterId": "sketchPlane"}}):
        raise Unsupported("One source sketch plane required")
    plane = params[0]
    query = plane.get("queries")
    if (plane.get("btType") != "BTMParameterQueryList-148" or plane.get("parameterId") != "sketchPlane"
            or not isinstance(query, list) or len(query) != 1
            or query[0].get("btType") != "BTMIndividualQuery-138"
            or feature.parameters != {"sketchPlane": [query[0].get("queryString")]}):
        raise Unsupported("Source sketch-plane projection differs")
    reference = re.fullmatch(r'query=qCreatedBy\(makeId\("([^"\\]+)"\), EntityType\.FACE\);', query[0].get("queryString", ""))
    if not reference:
        raise Unsupported("Explicit source-created plane reference required")
    summary = feature.structure.get("sketch", {}).get("rectangle", {})
    xy = [summary.get(k) for k in ("x0", "y0", "x1", "y1")]
    if (summary.get("construction") is not False or any(type(v) not in (int, float) or not math.isfinite(v) for v in xy)
            or not xy[0] < xy[2] or not xy[1] < xy[3] or not xy[0] or not xy[1]):
        raise Unsupported("Nonzero first corner and positive rectangle extents required")
    x0, y0, x1, y1 = xy
    entities, constraints = raw.get("entities"), raw.get("constraints")
    if not isinstance(entities, list) or len(entities) != 4 or not isinstance(constraints, list) or len(constraints) != 12:
        raise Unsupported("Four source lines and twelve constraints required")
    first = entities[0].get("entityId", "")
    prefix = first[:-7] if first.endswith(".bottom") else ""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", prefix):
        raise Unsupported("Source rectangle line identities differ")
    line_fields = []
    for entity, (side, px, py, dx, dy, length) in zip(entities, (
            ("bottom", x0, y0, 1, 0, x1-x0), ("right", x1, y0, 0, 1, y1-y0),
            ("top", x1, y1, -1, 0, x1-x0), ("left", x0, y1, 0, -1, y1-y0))):
        ident = prefix + "." + side
        geometry = entity.get("geometry", {})
        expected = {"pntX": px, "pntY": py, "dirX": dx, "dirY": dy}
        if (entity.get("btType") != "BTMSketchCurveSegment-155" or entity.get("isConstruction") is not False
                or entity.get("entityId") != ident or entity.get("startPointId") != ident + ".start"
                or entity.get("endPointId") != ident + ".end" or entity.get("startParam") != 0
                or geometry.get("btType") != "BTCurveGeometryLine-117"):
            raise Unsupported("Rectangle source line schema or identity differs")
        for actual, value in [(entity.get("endParam"), length), *[(geometry.get(k), v) for k,v in expected.items()]]:
            if type(actual) not in (int, float) or not math.isfinite(actual) or not math.isclose(actual, value, rel_tol=0, abs_tol=1e-12):
                raise Unsupported("Source line geometry contradicts rectangle summary")
        line_fields.append({"source_entity_id": ident, "native_entity_type": "bsedit.GBTMSketchCurveSegment",
                            "native_geometry_type": "bsedit.GBTCurveGeometryLine", "geometry_fields": expected,
                            "startParam": 0, "endParam": length, "isConstruction": False})
    variable_stages = {f.logical_id: stage_length_variable(f) for f in variables}
    if len(variable_stages) != len(variables):
        raise Unsupported("Ambiguous source variables")
    used, dimensions, actual_constraints, constraint_ids = set(), [], [], set()
    for constraint in constraints:
        ident = constraint.get("entityId")
        ps = constraint.get("parameters", [])
        by = {p.get("parameterId"): p for p in ps}
        if (constraint.get("btType") != "BTMSketchConstraint-2" or not isinstance(ident, str) or not ident
                or ident in constraint_ids or len(by) != len(ps)):
            raise Unsupported("Source rectangle constraint identities differ")
        constraint_ids.add(ident)
        for key in ("localFirst", "localSecond"):
            if key in by and by[key].get("btType") != "BTMParameterString-149":
                raise Unsupported("Source local constraint reference type differs")
        kind = constraint.get("constraintType")
        first, second = by.get("localFirst", {}).get("value"), by.get("localSecond", {}).get("value")
        if kind in ("COINCIDENT", "HORIZONTAL", "VERTICAL"):
            if set(by) != ({"localFirst", "localSecond"} if kind == "COINCIDENT" else {"localFirst"}):
                raise Unsupported("Source geometric constraint parameters differ")
            actual_constraints.append((kind, first, second))
            continue
        if kind != "DISTANCE" or set(by) not in ({"localFirst", "localSecond", "direction", "length"},
                                                {"localFirst", "externalSecond", "direction", "length"}):
            raise Unsupported("Unsupported rectangle constraint")
        if (by["direction"].get("btType") != "BTMParameterEnum-145" or by["direction"].get("enumName") != "DimensionDirection"
                or by["length"].get("btType") != "BTMParameterQuantity-147"):
            raise Unsupported("Source distance schema differs")
        external = "externalSecond" in by
        if external and by["externalSecond"] != {"btType": "BTMParameterQueryList-148", "parameterId": "externalSecond",
                "queries": [{"btType": "BTMIndividualQuery-138", "queryString": 'query=qCreatedBy(makeId("Origin"), EntityType.VERTEX);'}]}:
            raise Unsupported("Source origin query differs")
        expression = by["length"].get("expression")
        if not isinstance(expression, str):
            raise Unsupported("Source dimension expression required")
        literal = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*mm", expression)
        if literal:
            value = float(literal[1])
        else:
            terms = _linear_expression(expression)
            value = 0
            for name, coefficient in terms.items():
                source = variable_stages.get(name)
                if source is None or source["source_line"] >= feature.provenance["source_line"]:
                    raise Unsupported("Dimension source variable missing or declared after sketch")
                value += float(coefficient) * float(source["expression"].strip()[:-2])
                used.add(name)
        direction = by["direction"].get("value")
        actual_constraints.append((kind, first, "Origin" if external else second, direction))
        dimensions.append({"source_constraint_id": ident, "expression": expression, "value_mm": value,
                           "direction": direction, "origin_relative": external})
    expected_constraints = [("COINCIDENT", prefix+"."+a, prefix+"."+b) for a,b in (
        ("bottom.start", "left.end"), ("bottom.end", "right.start"), ("right.end", "top.start"), ("top.end", "left.start"))]
    expected_constraints += [(k, prefix+"."+side, None) for k,side in (
        ("HORIZONTAL", "bottom"), ("HORIZONTAL", "top"), ("VERTICAL", "right"), ("VERTICAL", "left"))]
    expected_constraints += [("DISTANCE", prefix+"."+a, "Origin" if b == "Origin" else prefix+"."+b, d)
        for a,b,d in (("bottom.start", "bottom.end", "HORIZONTAL"), ("right.start", "right.end", "VERTICAL"),
                      ("bottom.start", "Origin", "HORIZONTAL"), ("bottom.start", "Origin", "VERTICAL"))]
    if sorted(map(repr, actual_constraints)) != sorted(map(repr, expected_constraints)):
        raise Unsupported("Rectangle constraint references contradict source topology")
    for d in dimensions:
        expected = abs(x0 if d["direction"] == "HORIZONTAL" else y0) if d["origin_relative"] else (
            x1-x0 if d["direction"] == "HORIZONTAL" else y1-y0)
        if not math.isfinite(d["value_mm"]) or not math.isclose(d["value_mm"], expected*1000, rel_tol=0, abs_tol=1e-9):
            raise Unsupported("Source dimension value contradicts line geometry")
    if set(feature.dependencies) != used | {reference[1]}:
        raise Unsupported("Rectangle source dependencies differ")
    return {"logical_id": feature.logical_id, "plane_logical_id": reference[1], "rectangle_m": xy,
            "line_fields": line_fields, "dimensions": dimensions, "source_constraints": copy.deepcopy(constraints),
            "source_variable_definitions": {name: variable_stages[name] for name in sorted(used)},
            "write_ready": False, "frame_verified": False, "regeneration_verified": False,
            "missing_native_evidence": ["fresh native line and constraint identities", "exact offset-plane query binding",
                "origin-relative signed dimension mapping and solver proof"]}
