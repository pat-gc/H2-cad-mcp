"""Source-driven fixed-anchor sketch population and durable preflight.

Fresh native node IDs come only from serializer constructors in the paired page
adapter. Opposite-sign alignment is a candidate until active solver proof passes.
"""
from __future__ import annotations

import copy
from uuid import uuid4

from .backend import Unsupported, UncertainWrite
from .native_circles import stage_source_circles
from .native_rectangles import stage_source_rectangle


def source_sketch_plan(feature, variables=()):
    rectangle = feature.structure.get("sketch", {}).get("rectangle")
    staged = stage_source_rectangle(feature, variables=variables) if rectangle else stage_source_circles(feature, variables=variables)
    common = {"hasUserCode": False, "name": "", "namespace": "", "sourceParseTreeNodes": {}}
    def param(kind, name, **fields):
        out = {"$type": "bsedit.GBTMParameter" + kind, "hasUserCode": False, "libraryRelationType": 0,
               "parameterId": name, "parameterName": "", "sourceParseTreeNodes": {}, **fields}
        if kind == "Enum": out["namespace"] = ""
        if kind == "Quantity": out["isInteger"] = False
        return out
    def string(name, value): return param("String", name, value=value)
    def enum(name, enum_name, value): return param("Enum", name, enumName=enum_name, value=value)
    def quantity(name, value, units, expression=""): return param("Quantity", name, value=value, units=units, expression=expression)
    entities, constraints, anchors, circles = [], [], {}, []
    def constraint(ident, kind, parameters, refs):
        constraints.append({"$type": "bsedit.GBTMSketchConstraint", **common, "constraintType": kind,
            "entityId": ident, "hasOffsetData1": False, "hasOffsetData2": False, "hasPierceParameter": False,
            "helpParameters": [], "offsetDistance1": 0, "offsetDistance2": 0,
            "offsetOrientation1": False, "offsetOrientation2": False, "parameters": parameters, "pierceParameter": 0})
        graph_constraints[ident] = {"type": kind, "references": refs}
    entity_common = {**common, "isConstruction": False, "isFromEndpointSplineHandle": False,
                     "isFromSplineControlPolygon": False, "isFromSplineHandle": False, "parameters": []}
    origin = "h2.localOrigin"
    graph_constraints = {}
    entities.append({"$type": "bsedit.GBTMSketchPoint", **entity_common, "entityId": origin,
                     "isUserPoint": True, "x": 0, "y": 0})
    anchors[origin] = [0, 0, 0]
    constraint("h2.fixedOrigin", 16, [string("localFirst", origin)], [origin])
    inferred = []
    def position(ident, point, direction, signed, expression, value):
        # Captured center->origin: negative X ALIGNED, positive X/Y ANTI_ALIGNED.
        # Negative Y is the corresponding sign-reversed candidate; solver proof
        # against source coordinates is mandatory before Commit.
        alignment = "ANTI_ALIGNED" if signed > 0 else "ALIGNED"
        if direction == "VERTICAL" and signed < 0: inferred.append(ident)
        constraint(ident, 12, [string("localFirst", point), string("localSecond", origin),
            enum("direction", "DimensionDirection", direction), quantity("length", value, "millimeter", expression),
            enum("alignment", "DimensionAlignment", alignment), quantity("labelRatio", .5, ""),
            quantity("labelDistance", .02, "meter")], [point, origin])
    if rectangle:
        x0, y0, x1, y1 = staged["rectangle_m"]
        prefix = staged["line_fields"][0]["source_entity_id"].rsplit(".", 1)[0]
        def local(side): return prefix + "." + side
        for side, px, py, dx, dy, distance, start, end in (
            ("bottom", (x0+x1)/2, y0, 1, 0, x1-x0, [x0,y0,0], [x1,y0,0]),
            ("right", x1, (y0+y1)/2, 0, 1, y1-y0, [x1,y0,0], [x1,y1,0]),
            ("top", (x0+x1)/2, y1, 1, 0, x1-x0, [x0,y1,0], [x1,y1,0]),
            ("left", x0, (y0+y1)/2, 0, 1, y1-y0, [x0,y0,0], [x0,y1,0])):
            ident = local(side)
            entities.append({"$type": "bsedit.GBTMSketchCurveSegment", **entity_common,
                "entityId": ident, "startPointId": ident + ".start", "endPointId": ident + ".end", "centerId": "",
                "curvedTextIds": [], "internalIds": [], "offsetCurveExtensions": [],
                "startParam": -distance/2, "endParam": distance/2,
                "geometry": {"$type": "bsedit.GBTCurveGeometryLine", "pntX": px, "pntY": py, "dirX": dx, "dirY": dy}})
            anchors[ident + ".start"], anchors[ident + ".end"] = start, end
        for name, kind, refs in (("perpendicular",5,[local("top"),local("left")]),
            ("parallel1",2,[local("bottom"),local("top")]), ("parallel2",2,[local("left"),local("right")]),
            ("horizontal",4,[local("top")]),
            ("corner0",1,[local("bottom.start"),local("left.start")]),
            ("corner1",1,[local("bottom.end"),local("right.start")]),
            ("corner2",1,[local("top.start"),local("left.end")]),
            ("corner3",1,[local("top.end"),local("right.end")])):
            constraint("h2." + name, kind, [string("localFirst", refs[0])] + ([string("localSecond", refs[1])] if len(refs)>1 else []), refs)
        for d in staged["dimensions"]:
            if d["origin_relative"]:
                position(d["source_constraint_id"], local("bottom.start"), d["direction"],
                         x0 if d["direction"] == "HORIZONTAL" else y0, d["expression"], d["value_mm"])
            else:
                line = local("top" if d["direction"] == "HORIZONTAL" else "right")
                constraint(d["source_constraint_id"], 11, [string("localFirst", line),
                    enum("direction", "DimensionDirection", "MINIMUM"), quantity("length", d["value_mm"], "millimeter", d["expression"]),
                    enum("alignment", "DimensionAlignment", "ALIGNED"), quantity("labelRatio", .5, ""),
                    quantity("labelDistance", .02, "meter")], [line])
    else:
        for circle in staged["circles"]:
            ident, center, geometry = circle["source_entity_id"], circle["source_center_id"], circle["seed_geometry"]
            entities.append({"$type": "bsedit.GBTMSketchCurve", **entity_common, "entityId": ident,
                "centerId": center, "curvedTextIds": [], "internalIds": [],
                "geometry": {"$type": "bsedit.GBTCurveGeometryCircle", **geometry}})
            anchors[center] = [geometry["xCenter"], geometry["yCenter"], 0]
            circles.append({"entity_id": ident, "center_id": center, "radius": geometry["radius"]})
            for d in circle["dimensions"]:
                mapped = d["native_mapping"]
                if mapped["constraintType"] == 25:
                    constraint(d["source_constraint_id"], 25, [string("localFirst", ident),
                        quantity("length", d["source_value_mm"], "millimeter", d["source_expression"]),
                        quantity("labelRatio", 1.5, ""), quantity("labelAngle", .7, "radian")], [ident])
                else:
                    direction = mapped["direction"]
                    position(d["source_constraint_id"], center, direction,
                        geometry["xCenter" if direction == "HORIZONTAL" else "yCenter"],
                        d["source_expression"], d["source_value_mm"])
    ids = [n["entityId"] for n in entities + constraints]
    if len(ids) != len(set(ids)):
        raise Unsupported("Source entity IDs collide with fixed-anchor mapping")
    return {"logical_id": feature.logical_id, "plane_logical_id": staged["plane_logical_id"],
        "source_stage": staged, "entities": entities, "constraints": constraints,
        "graph_constraints": graph_constraints, "graph_anchors": anchors, "graph_circles": circles,
        "inferred_alignment_constraints": inferred}


def sketch_population_intent(features, logical_id, before, baseline, *, target, plane_op_id, variable_op_ids, journal):
    from .native import _native_model_metadata
    from .native_planes import _observed_row, stage_offset_plane
    variables = [f for f in features if f.kind == "assignVariable"]
    found = [f for f in features if f.kind == "newSketch" and f.logical_id == logical_id]
    if len(found) != 1:
        raise Unsupported("One explicit source sketch required")
    feature = found[0]
    plan = source_sketch_plan(feature, variables)
    td = target.to_dict()
    if (baseline.get("target") != td or baseline.get("connected") is not True or baseline.get("editingFeatureId") is not None
            or before.get("target") != td or before.get("connected") is not True or not before.get("editingFeatureId")):
        raise Unsupported("Saved idle baseline and exact active draft target required")
    children = before.get("tree", {}).get("children", [])
    fid = before["editingFeatureId"]
    drafts = [n for n in children if n.get("featureId") == fid]
    if (len(drafts) != 1 or drafts[0].get("featureType") != "newSketch" or not drafts[0].get("nodeId")
            or drafts[0].get("entities") != [] or drafts[0].get("constraints") != []
            or [n for n in children if n.get("featureId") != fid] != baseline.get("tree", {}).get("children")
            or _native_model_metadata(before["tree"]) != _native_model_metadata(baseline["tree"])):
        raise Unsupported("Fresh blank sketch allocation changed unrelated source tree")
    key = "/".join(td[k] for k in ("did", "wid", "eid"))
    row, plane_intent, observation = _observed_row(journal, plane_op_id, key, "experimental_plane_populate")
    planes = [f for f in features if f.kind == "cPlane" and f.logical_id == plan["plane_logical_id"]]
    if len(planes) != 1 or row["logical_id"] != plan["plane_logical_id"]:
        raise Unsupported("Source sketch plane journal identity differs")
    if plane_intent["source_stages"][plane_intent["source_index"]] != stage_offset_plane(planes[0], variables=variables):
        raise Unsupported("Source sketch plane provenance differs")
    plane_id = observation["feature_id"]
    expected_plane = [n for n in plane_intent["expected_tree"]["children"] if n.get("featureId") == plane_id]
    if len(expected_plane) != 1 or [n for n in children if n.get("featureId") == plane_id] != expected_plane:
        raise Unsupported("Observed source plane definition changed")
    source_variables = plan["source_stage"]["source_variable_definitions"]
    if set(variable_op_ids) != set(source_variables):
        raise Unsupported("Exact observed operations for sketch variables required")
    for name, op_id in variable_op_ids.items():
        vr, vi, vo = _observed_row(journal, op_id, key, "experimental_variable_populate")
        if (vr["logical_id"] != name or vi["source_stages"][vi["source_index"]] != source_variables[name]):
            raise Unsupported("Source sketch variable provenance differs")
        expected_variable = [n for n in vi["expected_tree"]["children"] if n.get("featureId") == vo["feature_id"]]
        if len(expected_variable) != 1 or [n for n in children if n.get("featureId") == vo["feature_id"]] != expected_variable:
            raise Unsupported("Observed sketch variable definition changed")
    return {"before_state": before, "baseline": baseline, "plan": plan, "plane_op_id": plane_op_id,
            "plane_feature_id": plane_id, "variable_op_ids": variable_op_ids,
            "source_feature": copy.deepcopy(feature.provenance["fsgen_feature_json"])}


async def populate_source_sketch(backend, target, source, *, logical_id, baseline, plane_op_id, variable_op_ids, journal):
    from .fsgen import compile_fsgen
    from .native import PreDispatchRejected, _confirm_pending_readback
    if target.to_dict() != backend.create_target or backend.tab_id is None:
        raise Unsupported("Authorized exact source sketch studio/tab required")
    features = compile_fsgen(source, target).features
    key = "/".join(target.to_dict()[k] for k in ("did", "wid", "eid"))
    with journal.target_lock(key):
        if journal.has_unresolved():
            raise UncertainWrite("Prior write unresolved; reconcile before source sketch population")
        health = await backend.bridge.health()
        if (health.get("extension_connected") is not True
                or "h2_source_sketch_server_v1" not in health.get("capabilities", [])
                or "h2_source_sketch_page_v1" not in (health.get("extension") or {}).get("capabilities", [])):
            raise Unsupported("Paired source sketch writer capability unavailable")
        before = await backend.raw_state(target)
        intent = sketch_population_intent(features, logical_id, before, baseline, target=target,
                                         plane_op_id=plane_op_id, variable_op_ids=variable_op_ids, journal=journal)
        draft = next(n for n in before["tree"]["children"] if n.get("featureId") == before["editingFeatureId"])
        ps = [p for p in draft.get("parameters", []) if p.get("parameterId") == "sketchPlane"]
        if len(ps) != 1 or len(ps[0].get("queries", [])) != 1 or not ps[0]["queries"][0].get("deterministicIds"):
            raise Unsupported("UI-bound source sketch plane required")
        query = ps[0]["queries"][0]
        response = await backend.bridge.command({"kind": "native", "target": target.to_dict(), "tab_id": backend.tab_id,
            "command": "ui.GBTUiGetQueryDataCall", "body": {"elementId": target.eid, "queries": [query],
                "qFunction": "", "additionalArguments": [], "queryNodeIdToInContextNodeId": {}}})
        data = response.get("result", {}).get("queryData")
        if (response.get("result", {}).get("$type") != "ui.GBTUiGetQueryDataResponse"
                or not isinstance(data, list) or len(data) != 1 or data[0].get("featureId") != intent["plane_feature_id"]
                or data[0].get("deterministicIds") != query["deterministicIds"] or data[0].get("selectionName") != "Face"
                or data[0].get("evaluationDetails", {}).get("entityType") != 2
                or data[0].get("evaluationDetails", {}).get("status") != 0 or data[0].get("hasErrorEntity") is not False):
            raise Unsupported("Sketch plane query does not resolve to the exact source plane")
        after_query = await backend.raw_state(target)
        if any(after_query.get(k) != before.get(k) for k in ("tree", "connected", "editingFeatureId", "element_microversion")):
            raise Unsupported("Sketch editor changed during plane binding readback")
        intent["plane_query_evidence"] = response
        op_id = "source-sketch-" + uuid4().hex
        journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                        action="experimental_source_sketch_populate", logical_id=logical_id, intent=intent)
        try:
            receipt = await backend.bridge.command({"kind": "partstudio_populate_source_sketch", "op_id": op_id,
                "target": target.to_dict(), "tab_id": backend.tab_id,
                "expected_element_microversion": before["element_microversion"],
                "source_sketch": {"feature_id": before["editingFeatureId"], "plane_feature_id": intent["plane_feature_id"],
                                  "before_tree": before["tree"], "plan": intent["plan"]}})
        except PreDispatchRejected as exc:
            journal.transition(op_id, "rejected", error=str(exc)); raise
        except Exception as exc:
            journal.transition(op_id, "unknown", error=str(exc))
            raise UncertainWrite(f"Source sketch outcome unknown; journal operation {op_id}") from exc
        if receipt.get("op_id") != op_id:
            journal.transition(op_id, "unknown", error="Source sketch receipt identity differs")
            raise UncertainWrite(f"Source sketch outcome unknown; journal operation {op_id}")
        journal.transition(op_id, "sent", receipt=receipt)
        return await _confirm_pending_readback(backend.bridge.reconcile_saved_source_sketch, op_id, backend.tab_id, "Source sketch")
