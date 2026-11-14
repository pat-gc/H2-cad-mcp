"""Inspect source-journal body history without granting mutation authority."""
from __future__ import annotations

import hashlib
import json
import re

from .backend import Unsupported
from .source_run import _adopt, _load, _lock


def inspect_source_body_history(path, source, target, journal, *, logical_id, current_state):
    """Require exact observed source definitions/order in a supplied idle snapshot.

    The caller must obtain and pin a fresh snapshot independently. This helper
    performs no bridge calls, persists no checkpoint, and never enables cuts.
    Existing source-run restrictions (including repeated cuts) remain in force.
    """
    with _lock(path):
        run, _ = _load(path, source, target, journal)
        _adopt(run, journal)
        bindings=run["bindings"]
        matching=[f for f in run["plan"] if f["logical_id"]==logical_id]
        if (len(matching)!=1 or matching[0]["kind"]!="extrude"
                or matching[0]["stage"]["operation_type"]!="NEW" or logical_id not in bindings):
            raise Unsupported("One observed original source NEW target required")
        state=current_state
        nodes=state.get("tree",{}).get("children")
        if (state.get("target")!=target.to_dict() or state.get("connected") is not True
                or state.get("editingFeatureId","missing") is not None
                or state.get("h2Readback",{}).get("incompleteFeatureEdit")
                or not isinstance(nodes,list)
                or any(not re.fullmatch(r"[a-f0-9]{24}",str(state.get(k))) for k in ("microversion","element_microversion"))):
            raise Unsupported("Exact saved idle snapshot and both revisions required")
        ids=[]
        for feature in run["plan"]:
            if feature["logical_id"] not in bindings:continue
            binding=bindings[feature["logical_id"]]
            live=[n for n in nodes if n.get("featureId")==binding["feature_id"]]
            if (live!=[binding["node"]] or binding["node"].get("suppressed") is not False
                    or binding["node"].get("featureType")!=feature["kind"]):
                raise Unsupported("Observed source definition changed, suppressed, missing or ambiguous")
            ids.append(binding["feature_id"])
        native_order=[n.get("featureId") for n in nodes if n.get("featureId") in ids]
        if native_order!=ids or len(ids)!=len(set(ids)):
            raise Unsupported("Native feature order differs from observed source history")
        target_id=bindings[logical_id]["feature_id"]
        target_index=next(i for i,n in enumerate(nodes) if n.get("featureId")==target_id)
        for index, node in enumerate(nodes[target_index+1:], start=target_index+1):
            if node.get("featureId") in ids:continue
            if (node.get("$type")=="bsedit.GBTMRollback" and not node.get("featureId")
                    and index==len(nodes)-1 and isinstance(node.get("nodeId"),str) and node["nodeId"]):continue
            raise Unsupported("Unbound intervening feature or node after target NEW body")
        modifications=[]
        for feature in run["plan"]:
            name=feature["logical_id"]
            if name not in bindings or feature["kind"]!="extrude":continue
            stage=feature["stage"]
            if stage["operation_type"]=="REMOVE" and stage["target_body_logical_id"]==logical_id:
                binding=bindings[name]
                modifications.append({"logical_id":name,"op_id":binding["op_id"],"feature_id":binding["feature_id"]})
        snapshot={"target":target.to_dict(),"element_microversion":state["element_microversion"],
                  "document_microversion":state["microversion"],"tree":state["tree"]}
        return {"target":target.to_dict(),"source_sha256":run["source_sha256"],
                "target_logical_id":logical_id,"target_feature_id":target_id,
                "target_op_id":bindings[logical_id]["op_id"],"observed_removes":modifications,
                "ordered_bound_feature_ids":ids,"element_microversion":state["element_microversion"],
                "document_microversion":state["microversion"],
                "snapshot_sha256":hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest(),
                "source_definitions_observed":True,"write_ready":False,
                "missing_evidence":["fresh inventory joined to this exact snapshot and complete descendant set",
                                    "native write preflight and reconciliation integration"]}
