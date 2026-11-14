"""Source circle staging with explicitly partial, observed native mappings.

No identifiers are allocated and no external snap query is synthesized. Circle
seed geometry is distinct from evaluated solver geometry after variable edits.
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


def stage_source_circles(feature: Feature, *, variables: Sequence[Feature] = ()) -> dict:
    raw = feature.provenance.get("fsgen_feature_json")
    if (feature.kind != "newSketch" or not isinstance(raw, dict)
            or raw.get("btType") != "BTMSketch-151" or raw.get("featureType") != "newSketch"
            or raw.get("name") != feature.logical_id):
        raise Unsupported("Original FSGen circle sketch required")
    try:
        if _semantic_native_body(raw) != feature.structure.get("fsgen_native"):
            raise Unsupported("Circle source semantic provenance differs")
    except FsgenCompileError as exc:
        raise Unsupported("Invalid circle source provenance") from exc
    params = raw.get("parameters")
    schema = {"sketchPlane": {"btType": "BTMParameterQueryList-148", "parameterId": "sketchPlane"}}
    if not isinstance(params, list) or len(params) != 1 or feature.structure.get("parameter_schema") != schema:
        raise Unsupported("One exact source sketch plane required")
    plane = params[0]
    queries = plane.get("queries")
    if (plane.get("btType") != "BTMParameterQueryList-148" or plane.get("parameterId") != "sketchPlane"
            or not isinstance(queries, list) or len(queries) != 1
            or queries[0].get("btType") != "BTMIndividualQuery-138"
            or feature.parameters != {"sketchPlane": [queries[0].get("queryString")]}):
        raise Unsupported("Circle plane semantic projection differs")
    reference = re.fullmatch(r'query=qCreatedBy\(makeId\("([^"\\]+)"\), EntityType\.FACE\);', queries[0].get("queryString", ""))
    if not reference:
        raise Unsupported("Explicit source-created circle plane required")
    entities, constraints = raw.get("entities"), raw.get("constraints")
    if not isinstance(entities, list) or not entities or not isinstance(constraints, list) or len(constraints) != 3 * len(entities):
        raise Unsupported("Each source circle requires diameter and two origin dimensions")
    variable_stages = {v.logical_id: stage_length_variable(v) for v in variables}
    if len(variable_stages) != len(variables):
        raise Unsupported("Ambiguous source variables")
    used = set()

    def value_mm(expression):
        if not isinstance(expression, str):
            raise Unsupported("Circle dimension expression required")
        literal = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*mm", expression)
        if literal:
            return float(literal[1])
        value = 0
        for name, coefficient in _linear_expression(expression).items():
            source = variable_stages.get(name)
            if source is None or source["source_line"] >= feature.provenance["source_line"]:
                raise Unsupported("Circle source variable missing or declared after sketch")
            value += float(coefficient) * float(source["expression"].strip()[:-2])
            used.add(name)
        return value

    circles = {}
    for entity in entities:
        ident, geometry = entity.get("entityId"), entity.get("geometry", {})
        if (not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", ident) or ident in circles
                or entity.get("centerId") != ident + ".center" or entity.get("btType") != "BTMSketchCurve-4"
                or entity.get("isConstruction") is not False or geometry.get("btType") != "BTCurveGeometryCircle-115"
                or geometry.get("clockwise") is not False or geometry.get("xDir") != 1 or geometry.get("yDir") != 0
                or any(type(geometry.get(k)) not in (int, float) or not math.isfinite(geometry[k]) for k in ("radius", "xCenter", "yCenter"))
                or geometry["radius"] <= 0):
            raise Unsupported("Source circle geometry or entity identity differs")
        circles[ident] = {"source_entity_id": ident, "source_center_id": ident + ".center",
                          "native_entity_type": "bsedit.GBTMSketchCurve", "native_geometry_type": "bsedit.GBTCurveGeometryCircle",
                          "seed_geometry": {k: v for k, v in geometry.items() if k != "btType"}, "dimensions": []}
    constraint_ids, dimensions_seen = set(), set()
    for constraint in constraints:
        cid = constraint.get("entityId")
        ps = constraint.get("parameters", [])
        by = {p.get("parameterId"): p for p in ps}
        if (constraint.get("btType") != "BTMSketchConstraint-2" or not isinstance(cid, str) or not cid
                or cid in constraint_ids or len(by) != len(ps)
                or by.get("localFirst", {}).get("btType") != "BTMParameterString-149"
                or by.get("length", {}).get("btType") != "BTMParameterQuantity-147"):
            raise Unsupported("Circle constraint schema or identity differs")
        constraint_ids.add(cid)
        first, expression = by["localFirst"].get("value"), by["length"].get("expression")
        value = value_mm(expression)
        kind = constraint.get("constraintType")
        if kind == "DIAMETER" and set(by) == {"localFirst", "length"} and first in circles:
            circle, direction, expected = circles[first], "DIAMETER", circles[first]["seed_geometry"]["radius"] * 2000
            mapped = {"constraintType": 25, "localFirst": first, "expression": expression, "mapping_observed": True}
        elif kind == "DISTANCE" and set(by) == {"localFirst", "externalSecond", "direction", "length"}:
            circle = next((c for c in circles.values() if c["source_center_id"] == first), None)
            external = by["externalSecond"]
            if (circle is None or external.get("btType") != "BTMParameterQueryList-148"
                    or external.get("queries") != [{"btType": "BTMIndividualQuery-138", "queryString": 'query=qCreatedBy(makeId("Origin"), EntityType.VERTEX);'}]
                    or by["direction"].get("btType") != "BTMParameterEnum-145"
                    or by["direction"].get("enumName") != "DimensionDirection"
                    or by["direction"].get("value") not in {"HORIZONTAL", "VERTICAL"}):
                raise Unsupported("Circle origin reference or direction differs")
            direction = by["direction"]["value"]
            signed = circle["seed_geometry"]["xCenter" if direction == "HORIZONTAL" else "yCenter"]
            expected = abs(signed) * 1000
            # Only these point-order/sign combinations were actually captured.
            alignment = "ALIGNED" if direction == "HORIZONTAL" and signed < 0 else "ANTI_ALIGNED" if direction == "VERTICAL" and signed > 0 else None
            mapped = {"constraintType": 12, "localFirst": first, "localSecond_role": "verified_local_origin_anchor",
                      "direction": direction, "alignment": alignment, "expression": expression,
                      "mapping_observed": alignment is not None}
        else:
            raise Unsupported("Unsupported circle constraint topology")
        signature = (circle["source_entity_id"], direction)
        if signature in dimensions_seen or not math.isfinite(value) or value <= 0 or not math.isclose(value, expected, rel_tol=0, abs_tol=1e-9):
            raise Unsupported("Circle dimension contradicts source seed geometry")
        dimensions_seen.add(signature)
        circle["dimensions"].append({"source_constraint_id": cid, "source_expression": expression,
                                     "source_value_mm": value, "native_mapping": mapped})
    if len(dimensions_seen) != 3 * len(circles) or set(feature.dependencies) != used | {reference[1]}:
        raise Unsupported("Circle constraint coverage or source dependencies differ")
    return {"logical_id": feature.logical_id, "plane_logical_id": reference[1], "circles": list(circles.values()),
            "source_constraints": copy.deepcopy(constraints),
            "source_variable_definitions": {name: variable_stages[name] for name in sorted(used)},
            "anchor_evidence": {"point_type": "bsedit.GBTMSketchPoint", "x": 0, "y": 0,
                "isConstruction": False, "fix_constraint_type": 16, "external_snap_constraint_type": 1,
                "independent_fix_without_snap_verified": False},
            "write_ready": False, "frame_verified": False, "regeneration_verified": False,
            "missing_native_evidence": ["fresh native entity and constraint identities", "exact offset-plane binding",
                "independent fixed local anchor or verified external snap binding",
                "local horizontal positive-X alignment", "fresh solver proof for all generated circles"]}
