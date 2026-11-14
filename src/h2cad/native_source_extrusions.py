"""Journal-bound source extrusions using the existing native depth editor path."""
from __future__ import annotations

import copy
import json
import re
from uuid import uuid4

from .backend import Unsupported, UncertainWrite
from .native_extrusions import map_source_extrusion, stage_source_extrusion
from .native_planes import _observed_row


def source_extrusion_intent(features, logical_id, before, baseline, query_response, *,
                            target, sketch_op_id, variable_op_id, journal, target_body_op_id=None, scope_query_response=None):
    """Bind source semantics to one observed sketch and one newly allocated draft."""
    matches = [f for f in features if f.kind == "extrude" and f.logical_id == logical_id]
    variables = [f for f in features if f.kind == "assignVariable"]
    if len(matches) != 1:
        raise Unsupported("One explicit source extrusion required")
    feature = matches[0]
    stage = stage_source_extrusion(feature, variables)
    td = target.to_dict()
    key = "/".join(td[k] for k in ("did", "wid", "eid"))
    if (baseline.get("target") != td or baseline.get("connected") is not True
            or baseline.get("editingFeatureId", "missing") is not None
            or not re.fullmatch(r"[a-f0-9]{24}", str(baseline.get("element_microversion", "")))
            or baseline["element_microversion"] == before.get("element_microversion")):
        raise Unsupported("Exact saved idle pre-allocation baseline required")
    fid = before.get("editingFeatureId")
    stripped = copy.deepcopy(before.get("tree", {}))
    stripped["children"] = [n for n in stripped.get("children", []) if n.get("featureId") != fid]
    if (not fid or stripped != baseline.get("tree")
            or any(n.get("featureId") == fid for n in baseline.get("tree", {}).get("children", []))):
        raise Unsupported("Fresh extrusion allocation changed the saved baseline")
    row, sketch_intent, observation = _observed_row(journal, sketch_op_id, key, "experimental_source_sketch_populate")
    source_sketches = [f for f in features if f.kind == "newSketch" and f.logical_id == stage["sketch_logical_id"]]
    sketch = observation.get("saved_feature")
    if (len(source_sketches) != 1 or row["logical_id"] != stage["sketch_logical_id"]
            or sketch_intent.get("source_feature") != source_sketches[0].provenance.get("fsgen_feature_json")
            or observation.get("constraint_graph_verified") is not True or observation.get("origin_verified") is not True
            or not isinstance(sketch, dict) or sketch.get("featureId") != observation["feature_id"]
            or sketch.get("nodeId") != observation.get("node_id")
            or source_sketches[0].provenance["source_line"] >= feature.provenance["source_line"]):
        raise Unsupported("Observed source sketch definition, graph, origin or provenance differs")
    variable_feature_id = None
    if stage["variable"] is None:
        if variable_op_id is not None:
            raise Unsupported("Literal depth has no variable journal dependency")
    else:
        if not variable_op_id:
            raise Unsupported("Observed source variable operation required for depth")
        vr, vi, vo = _observed_row(journal, variable_op_id, key, "experimental_variable_populate")
        index = vi.get("source_index")
        if (vr["logical_id"] != stage["depth_expression"] or type(index) is not int
                or not 0 <= index < len(vi.get("source_stages", []))
                or vi["source_stages"][index] != stage["variable"]):
            raise Unsupported("Depth variable source provenance differs")
        variable_feature_id = vo["feature_id"]
        expected = [n for n in vi["expected_tree"]["children"] if n.get("featureId") == variable_feature_id]
        live = [n for n in before["tree"]["children"] if n.get("featureId") == variable_feature_id]
        if len(expected) != 1 or live != expected:
            raise Unsupported("Live depth variable differs from observed source definition")
    target_definition = None
    if stage["operation_type"] == "REMOVE":
        tr, ti, to = _observed_row(journal, target_body_op_id, key, "experimental_source_extrude_populate")
        targets = [f for f in features if f.kind == "extrude" and f.logical_id == stage["target_body_logical_id"]]
        if (len(targets)!=1 or tr["logical_id"]!=stage["target_body_logical_id"]
                or ti.get("source_feature")!=targets[0].provenance.get("fsgen_feature_json")
                or stage_source_extrusion(targets[0],variables)["operation_type"]!="NEW"
                or targets[0].provenance["source_line"]>=feature.provenance["source_line"]):
            raise Unsupported("REMOVE target source NEW operation provenance differs")
        target_sketch = ti.get("saved_sketch_definition")
        if (not isinstance(target_sketch,dict) or target_sketch.get("featureType")!="newSketch"
                or not target_sketch.get("nodeId") or target_sketch.get("featureId")!=ti.get("sketch_feature_id")
                or [n for n in before["tree"]["children"] if n.get("featureId")==ti.get("sketch_feature_id")] != [target_sketch]):
            raise Unsupported("Target NEW source sketch changed since its observed creation")
        target_stage = stage_source_extrusion(targets[0],variables)
        target_sketches = [f for f in features if f.kind=="newSketch" and f.logical_id==target_stage["sketch_logical_id"]]
        if len(target_sketches)!=1 or ti.get("sketch_source_feature")!=target_sketches[0].provenance.get("fsgen_feature_json"):
            raise Unsupported("Target body source sketch provenance differs")
        from .native_sketches import source_sketch_plan
        target_plan=source_sketch_plan(target_sketches[0],variables)
        if not target_sketches[0].structure.get("sketch",{}).get("rectangle") and len(target_plan["graph_circles"])!=1:
            raise Unsupported("REMOVE scope requires a single-region source NEW body; multi-body source is unsupported")
        saved = [n for n in ti.get("expected_tree",{}).get("children",[]) if n.get("featureId")==to["feature_id"]]
        if len(saved)!=1:
            raise Unsupported("Observed target body definition missing")
        target_definition = saved[0]
    elif target_body_op_id is not None or scope_query_response is not None:
        raise Unsupported("NEW extrusion cannot carry a target-body dependency")
    mapped = map_source_extrusion(before, feature, target=target, sketch_feature_id=observation["feature_id"],
        sketch_definition=sketch, query_response=query_response, variables=variables,
        target_body_definition=target_definition, scope_query_response=scope_query_response)
    order = [n.get("featureId") for n in before["tree"]["children"]]
    if order.index(observation["feature_id"]) >= order.index(fid) or (
            variable_feature_id and order.index(variable_feature_id) >= order.index(fid)):
        raise Unsupported("Source sketch and depth variable must precede the extrusion")
    depth = next(p for n in before["tree"]["children"] if n.get("featureId") == fid
                 for p in n["parameters"] if p["parameterId"] == "depth")
    return {"before_state": before, "baseline": baseline, "expected_tree": mapped["expected_tree"],
            "source_stage": stage, "source_feature": copy.deepcopy(feature.provenance["fsgen_feature_json"]),
            "sketch_source_feature": copy.deepcopy(source_sketches[0].provenance["fsgen_feature_json"]),
            "sketch_op_id": sketch_op_id, "sketch_feature_id": observation["feature_id"],
            "saved_sketch_definition": copy.deepcopy(sketch), "variable_op_id": variable_op_id,
            "variable_feature_id": variable_feature_id, "region_query_evidence": query_response,
            "from_mm": depth["value"], "target_body_op_id": target_body_op_id,
            "saved_target_body_definition": target_definition, "scope_query_evidence": scope_query_response}


async def populate_source_extrusion(backend, target, source, *, logical_id, sketch_op_id,
                                    baseline, journal, variable_op_id=None, target_body_op_id=None):
    from .fsgen import compile_fsgen
    from .native import PreDispatchRejected, _confirm_pending_readback
    if target.to_dict() != backend.create_target or backend.tab_id is None:
        raise Unsupported("Authorized exact source extrusion studio/tab required")
    features = compile_fsgen(source, target).features
    key = "/".join(target.to_dict()[k] for k in ("did", "wid", "eid"))
    with journal.target_lock(key):
        if journal.has_unresolved():
            raise UncertainWrite("Reconcile the unresolved write before source extrusion")
        health = await backend.bridge.health()
        if (health.get("extension_connected") is not True
                or "h2_source_extrude_server_v1" not in health.get("capabilities", [])
                or "h2_source_extrude_page_v1" not in (health.get("extension") or {}).get("capabilities", [])
                or "h2_native_completion_receipt_page_v1" not in (health.get("extension") or {}).get("capabilities", [])):
            raise Unsupported("Paired source extrusion capability unavailable")
        requested_stage = stage_source_extrusion(next(f for f in features if f.logical_id==logical_id),
                                                [f for f in features if f.kind=="assignVariable"])
        if requested_stage["operation_type"]=="REMOVE" and (
                "h2_source_remove_server_v1" not in health.get("capabilities",[]) or
                "h2_source_remove_page_v1" not in (health.get("extension") or {}).get("capabilities",[])):
            raise Unsupported("Paired explicit-scope REMOVE writer capability unavailable")
        before = await backend.raw_state(target)
        drafts = [n for n in before.get("tree", {}).get("children", []) if n.get("featureId") == before.get("editingFeatureId")]
        if len(drafts) != 1 or drafts[0].get("featureType") != "extrude":
            raise Unsupported("One active source extrusion draft required")
        params = [p for p in drafts[0].get("parameters", []) if p.get("parameterId") == "entities"]
        if len(params) != 1 or len(params[0].get("queries", [])) != 1:
            raise Unsupported("One whole-sketch region selection required")
        resolved = await backend.bridge.command({"kind": "native", "target": target.to_dict(), "tab_id": backend.tab_id,
            "command": "ui.GBTUiGetQueryDataCall", "body": {"elementId": target.eid,
                "queries": params[0]["queries"], "qFunction": "", "additionalArguments": [], "queryNodeIdToInContextNodeId": {}}})
        scope_response = None
        source_stage = requested_stage
        if source_stage["operation_type"] == "REMOVE":
            scope = [p for p in drafts[0].get("parameters",[]) if p.get("parameterId")=="booleanScope"]
            if len(scope)!=1 or len(scope[0].get("queries",[]))!=1:
                raise Unsupported("UI must explicitly select one target body before REMOVE population")
            scope_response = await backend.bridge.command({"kind":"native","target":target.to_dict(),"tab_id":backend.tab_id,
                "command":"ui.GBTUiGetQueryDataCall","body":{"elementId":target.eid,"queries":scope[0]["queries"],
                "qFunction":"","additionalArguments":[],"queryNodeIdToInContextNodeId":{}}})
        confirm = await backend.raw_state(target)
        if any(confirm.get(k) != before.get(k) for k in ("target", "connected", "editingFeatureId", "element_microversion", "tree")):
            raise Unsupported("Extrusion draft changed during source-region resolution")
        intent = source_extrusion_intent(features, logical_id, before, baseline, resolved, target=target,
            sketch_op_id=sketch_op_id, variable_op_id=variable_op_id, journal=journal,
            target_body_op_id=target_body_op_id,scope_query_response=scope_response)
        stage = intent["source_stage"]
        op_id = "extrude-" + uuid4().hex
        journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                        action="experimental_source_extrude_populate", logical_id=logical_id, intent=intent)
        try:
            receipt = await backend.bridge.command({"kind": "partstudio_populate_extrude", "op_id": op_id,
                "target": target.to_dict(), "tab_id": backend.tab_id,
                "expected_element_microversion": before["element_microversion"],
                "extrude_edit": {"feature_id": before["editingFeatureId"], "sketch_feature_id": intent["sketch_feature_id"],
                                 "from_mm": intent["from_mm"], "to_mm": stage["depth_seed_mm"]},
                "source_extrusion": {"depth_expression": stage["depth_expression"],
                                     "before_tree": before["tree"], "expected_tree": intent["expected_tree"],
                                     "sketch_definition": intent["saved_sketch_definition"],
                                     **({"operation_type": "REMOVE", "target_body_definition": intent["saved_target_body_definition"],
                                        "scope_query_evidence": intent["scope_query_evidence"]} if stage["operation_type"]=="REMOVE" else {})}})
        except PreDispatchRejected as exc:
            journal.transition(op_id, "rejected", error=str(exc)); raise
        except Exception as exc:
            journal.transition(op_id, "unknown", error=str(exc))
            raise UncertainWrite(f"Source extrusion outcome unknown; journal operation {op_id}") from exc
        if receipt.get("op_id") != op_id:
            journal.transition(op_id, "unknown", error="Source extrusion receipt identity differs")
            raise UncertainWrite(f"Source extrusion outcome unknown; journal operation {op_id}")
        journal.transition(op_id, "sent", receipt=receipt)
        return await _confirm_pending_readback(backend.bridge.reconcile_saved_source_extrude,
                                               op_id, backend.tab_id, "Source extrusion")
