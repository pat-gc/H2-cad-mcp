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
                            target, sketch_op_id, variable_op_id, journal):
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
    mapped = map_source_extrusion(before, feature, target=target, sketch_feature_id=observation["feature_id"],
        sketch_definition=sketch, query_response=query_response, variables=variables)
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
            "from_mm": depth["value"]}


async def populate_source_extrusion(backend, target, source, *, logical_id, sketch_op_id,
                                    baseline, journal, variable_op_id=None):
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
        confirm = await backend.raw_state(target)
        if any(confirm.get(k) != before.get(k) for k in ("target", "connected", "editingFeatureId", "element_microversion", "tree")):
            raise Unsupported("Extrusion draft changed during source-region resolution")
        intent = source_extrusion_intent(features, logical_id, before, baseline, resolved, target=target,
            sketch_op_id=sketch_op_id, variable_op_id=variable_op_id, journal=journal)
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
                                     "sketch_definition": intent["saved_sketch_definition"]}})
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
