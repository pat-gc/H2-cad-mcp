"""Persistent source-order orchestration; Browser still allocates native drafts.

The run file is a checkpoint, never a substitute for the bridge's verified journal.
No CAD writes are implemented here: apply delegates to the existing guarded writers.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from contextlib import contextmanager

from .backend import Unsupported, UncertainWrite
from .fsgen import compile_fsgen
from .native import _native_model_metadata, stage_length_variable
from .native_planes import stage_offset_plane, populate_test_plane
from .native_sketches import source_sketch_plan, populate_source_sketch
from .native_extrusions import stage_source_extrusion
from .native_source_extrusions import populate_source_extrusion
from .validation import validate_fsgen

_ACTIONS = {"assignVariable": "experimental_variable_populate", "cPlane": "experimental_plane_populate",
            "newSketch": "experimental_source_sketch_populate", "extrude": "experimental_source_extrude_populate"}


def _text(source):
    return source.read_text(encoding="utf-8") if isinstance(source, Path) else source


def _plan(text, target):
    features = compile_fsgen(text, target).features
    variables = [f for f in features if f.kind == "assignVariable"]
    result, seen = [], set()
    for f in features:
        if f.logical_id in seen or not set(f.dependencies) <= seen:
            raise Unsupported("Unique source identities and preceding dependencies required")
        if f.kind == "assignVariable":
            stage = stage_length_variable(f)
        elif f.kind == "cPlane":
            stage = stage_offset_plane(f, variables=variables)
        elif f.kind == "newSketch":
            stage = source_sketch_plan(f, variables)
        elif f.kind == "extrude":
            if f.parameters.get("operationType") != "NEW":
                raise Unsupported("Source runs currently support only NEW extrusions")
            stage = stage_source_extrusion(f, variables)
        else:
            raise Unsupported(f"Unsupported source-run feature: {f.kind}")
        result.append({"logical_id": f.logical_id, "kind": f.kind, "stage": stage,
                       "source_feature": f.provenance["fsgen_feature_json"]})
        seen.add(f.logical_id)
    if not result:
        raise Unsupported("Nonempty supported source required")
    return result


@contextmanager
def _lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(path) + ".lock").open("a+b") as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _save(path, run):
    temp = Path(str(path) + ".tmp")
    with temp.open("w", encoding="utf-8") as out:
        json.dump(run, out, sort_keys=True)
        out.flush(); os.fsync(out.fileno())
    os.replace(temp, path)


def _rows(journal, key):
    # Public journal has no history-list API; read its existing durable schema only.
    with sqlite3.connect(journal.path) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute("SELECT * FROM writes WHERE target=? ORDER BY rowid", (key,))]


def initialize_run(path, source, target, journal):
    """Validate locally once and pin source, ordered semantics, target and journal."""
    with _lock(path):
        if Path(path).exists():
            raise Unsupported("Run exists; resume it instead of reinitializing")
        if journal.has_unresolved():
            raise UncertainWrite("Reconcile unresolved writes before initializing a run")
        if any(not re.fullmatch(r"[0-9a-f]{24}", v) for v in target.to_dict().values()):
            raise Unsupported("Exact native document/workspace/element required")
        text = _text(source)
        plan = _plan(text, target)
        validation = validate_fsgen(text)
        if validation.status != "passed":
            raise Unsupported("Complete local geometry validation must pass")
        key = "/".join(target.to_dict()[k] for k in ("did", "wid", "eid"))
        run = {"version": 1, "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
               "target": target.to_dict(), "journal": str(journal.path.resolve()), "plan": plan,
               "excluded_ops": [r["op_id"] for r in _rows(journal, key)], "bindings": {}, "staged": None,
               "local_validation": validation.to_dict()}
        _save(path, run)
        return {"action": "stage", "logical_id": plan[0]["logical_id"], "feature_count": len(plan)}


def _load(path, source, target, journal):
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    text = _text(source)
    if (run.get("version") != 1 or run.get("target") != target.to_dict()
            or run.get("journal") != str(journal.path.resolve())
            or run.get("source_sha256") != hashlib.sha256(text.encode()).hexdigest()
            or run.get("plan") != _plan(text, target)):
        raise Unsupported("Run source, target, journal or supported semantics changed")
    if journal.has_unresolved():
        raise UncertainWrite("Reconcile unresolved journal operation; never replay it")
    return run, text


def _match(row, feature, plan):
    intent, obs = json.loads(row["intent"]), json.loads(row["observation"] or "{}")
    if row["action"] != _ACTIONS[feature["kind"]] or obs.get("definition_observed") is not True:
        raise Unsupported("Journal action or independent saved definition proof differs")
    if feature["kind"] in ("assignVariable", "cPlane"):
        stages = [f["stage"] for f in plan if f["kind"] == feature["kind"]]
        index = stages.index(feature["stage"])
        if intent.get("source_stages") != stages or intent.get("source_index") != index:
            raise Unsupported("Journal source provenance differs")
    elif intent.get("source_feature") != feature["source_feature"]:
        raise Unsupported("Journal source provenance differs")
    if feature["kind"] == "newSketch":
        if not (obs.get("constraint_graph_verified") is True and obs.get("origin_verified") is True):
            raise Unsupported("Source sketch solver proof missing")
        node = obs.get("saved_feature")
    else:
        nodes = [n for n in intent.get("expected_tree", {}).get("children", [])
                 if n.get("featureId") == obs.get("feature_id")]
        node = nodes[0] if len(nodes) == 1 else None
    if (not isinstance(node, dict) or not obs.get("feature_id") or not node.get("nodeId")
            or node.get("featureId") != obs["feature_id"]
            or (obs.get("node_id") is not None and node["nodeId"] != obs["node_id"])):
        raise Unsupported("Journal saved native feature identity missing")
    return {"op_id": row["op_id"], "feature_id": obs["feature_id"], "node": node}


def _adopt(run, journal):
    key = "/".join(run["target"][k] for k in ("did", "wid", "eid"))
    rows = [r for r in _rows(journal, key) if r["op_id"] not in run["excluded_ops"] and r["state"] == "observed"]
    bindings, gap = {}, False
    for f in run["plan"]:
        matches = [r for r in rows if r["logical_id"] == f["logical_id"]]
        if not matches:
            gap = True
            continue
        if gap or len(matches) != 1:
            raise Unsupported("Duplicate or out-of-order observed source feature")
        bindings[f["logical_id"]] = _match(matches[0], f, run["plan"])
    if any(bindings.get(k) != v for k, v in run["bindings"].items()):
        raise Unsupported("Previously recorded binding no longer independently observed")
    run["bindings"] = bindings
    if run["staged"] and run["staged"]["logical_id"] in bindings:
        run["staged"] = None


def _state(run, state, target, backend):
    if (backend.create_target != target.to_dict() or backend.tab_id is None
            or state.get("target") != target.to_dict() or state.get("connected") is not True
            or not re.fullmatch(r"[0-9a-f]{24}", str(state.get("element_microversion", "")))
            or not isinstance(state.get("tree", {}).get("children"), list)):
        raise Unsupported("Authorized connected native target/tab and exact tree required")
    for binding in run["bindings"].values():
        if [n for n in state["tree"]["children"] if n.get("featureId") == binding["feature_id"]] != [binding["node"]]:
            raise Unsupported("Previously observed source feature changed in live tree")


def _same_snapshot(left, right):
    """Compare CAD state, excluding bounded inspection diagnostics."""
    return all(left.get(k) == right.get(k) for k in (
        "target", "connected", "editingFeatureId", "element_microversion", "tree")) and (
        left.get("h2Readback", {}).get("incompleteFeatureEdit")
        == right.get("h2Readback", {}).get("incompleteFeatureEdit"))


def _allocation(run, feature):
    kind, stage = feature["kind"], feature["stage"]
    action = {"action": "browser_allocate", "logical_id": feature["logical_id"], "feature_type": kind,
              "target": run["target"], "tab_id": run["staged"]["tab_id"]}
    if kind == "assignVariable":
        action["defaults"] = {"mode": "ASSIGNED", "variableType": "LENGTH", "name": ""}
    elif kind == "cPlane":
        action.update(reference={"default_plane": stage["reference_plane"]}, defaults={"cplaneType": "OFFSET", "offset": "25 mm"})
    else:
        name = stage["plane_logical_id"] if kind == "newSketch" else stage["sketch_logical_id"]
        action["reference"] = {"logical_id": name, "feature_id": run["bindings"][name]["feature_id"]}
        action["defaults"] = {"entities": [], "constraints": []} if kind == "newSketch" else {"operationType": "NEW", "bodyType": "SOLID", "endBound": "BLIND", "selection": "whole_sketch"}
    return action


async def next_action(path, backend, source, target, journal):
    with _lock(path):
        run, _ = _load(path, source, target, journal)
        _adopt(run, journal)
        state = await backend.raw_state(target)
        _state(run, state, target, backend)
        if state.get("editingFeatureId", "missing") is not None or state.get("h2Readback", {}).get("incompleteFeatureEdit"):
            raise Unsupported("Stage only from saved idle; apply an already allocated draft separately")
        if len(run["bindings"]) == len(run["plan"]):
            _save(path, run)
            return {"action": "verify_geometry", "source_features_observed": len(run["bindings"]), "geometry_verified": False}
        feature = run["plan"][len(run["bindings"])]
        if run["staged"]:
            old = run["staged"]
            if not _same_snapshot(old["baseline"], state) or old["tab_id"] != backend.tab_id:
                raise Unsupported("Staged baseline changed; inspect rather than silently restaging")
        else:
            run["staged"] = {"logical_id": feature["logical_id"], "baseline": state, "tab_id": backend.tab_id}
        _save(path, run)
        return _allocation(run, feature)


async def _plane_binding(backend, target, before):
    drafts = [n for n in before["tree"]["children"] if n.get("featureId") == before["editingFeatureId"]]
    params = [p for p in drafts[0].get("parameters", []) if p.get("parameterId") == "entities"]
    if len(params) != 1 or len(params[0].get("queries", [])) != 1:
        raise Unsupported("Exactly one UI-selected plane query required")
    query = params[0]["queries"][0]
    response = await backend.bridge.command({"kind": "native", "target": target.to_dict(), "tab_id": backend.tab_id,
        "command": "ui.GBTUiGetQueryDataCall", "body": {"elementId": target.eid, "queries": [query],
            "qFunction": "", "additionalArguments": [], "queryNodeIdToInContextNodeId": {}}})
    data = response.get("result", {}).get("queryData")
    if (response.get("result", {}).get("$type") != "ui.GBTUiGetQueryDataResponse" or not isinstance(data, list)
            or len(data) != 1 or not _same_snapshot(await backend.raw_state(target), before)):
        raise Unsupported("Plane query readback or draft revision changed")
    return {"target": target.to_dict(), "element_microversion": before["element_microversion"],
            "query": query, "query_data": data[0]}


async def apply_staged(path, backend, source, target, journal):
    with _lock(path):
        run, text = _load(path, source, target, journal)
        _adopt(run, journal)
        if not run["staged"]:
            current = await backend.raw_state(target)
            _state(run, current, target, backend)
            if current.get("editingFeatureId", "missing") is not None:
                raise Unsupported("Unexpected active draft after observed completion")
            _save(path, run)
            return {"action": "stage", "reason": "no_unapplied_stage"}
        staged = run["staged"]
        if staged["tab_id"] != backend.tab_id:
            raise Unsupported("Staged tab changed")
        feature = run["plan"][len(run["bindings"])]
        before = await backend.raw_state(target)
        _state(run, before, target, backend)
        baseline = staged["baseline"]
        fid = before.get("editingFeatureId")
        children = before["tree"]["children"]
        drafts = [n for n in children if n.get("featureId") == fid]
        if (len(drafts) != 1 or drafts[0].get("featureType") != feature["kind"]
                or any(n.get("featureId") == fid for n in baseline["tree"]["children"])
                or [n for n in children if n.get("featureId") != fid] != baseline["tree"]["children"]
                or _native_model_metadata(before["tree"]) != _native_model_metadata(baseline["tree"])
                or before["element_microversion"] == baseline["element_microversion"]):
            raise Unsupported("Stale baseline or wrong fresh draft; no population dispatched")
        def ops(kind):
            return [run["bindings"][f["logical_id"]]["op_id"] for f in run["plan"]
                    if f["kind"] == kind and f["logical_id"] in run["bindings"]]
        def op(name):
            return run["bindings"][name]["op_id"]
        kind, stage = feature["kind"], feature["stage"]
        common = {"logical_id": feature["logical_id"], "journal": journal}
        if kind == "assignVariable":
            await backend.populate_test_variable(target, text, previous_op_ids=ops(kind), **common)
        elif kind == "cPlane":
            binding = await _plane_binding(backend, target, before)
            await populate_test_plane(backend, target, text, baseline=baseline, reference_binding=binding,
                variable_op_ids={name: op(name) for name in stage["dependencies"]}, previous_op_ids=ops(kind), **common)
        elif kind == "newSketch":
            await populate_source_sketch(backend, target, text, baseline=baseline, plane_op_id=op(stage["plane_logical_id"]),
                variable_op_ids={name: op(name) for name in stage["source_stage"]["source_variable_definitions"]}, **common)
        else:
            await populate_source_extrusion(backend, target, text, baseline=baseline, sketch_op_id=op(stage["sketch_logical_id"]),
                variable_op_id=op(stage["depth_expression"]) if stage["variable"] else None, **common)
        _adopt(run, journal)
        _state(run, await backend.raw_state(target), target, backend)
        if feature["logical_id"] not in run["bindings"]:
            raise UncertainWrite("Writer returned without independently observed journal proof")
        _save(path, run)
        return {"action": "stage", "observed_logical_id": feature["logical_id"], "op_id": op(feature["logical_id"])}
