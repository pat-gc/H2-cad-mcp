"""Source plane population guards; no live writer or frame verification."""
import copy
import json

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.native import stage_length_variable
from h2cad.native_planes import plane_population_intent
from test_native_plane_mapping import SOURCE, TARGET, REV, native_draft


class Rows(dict):
    pass


def scenario(index=0):
    features = compile_fsgen(SOURCE, TARGET).features
    planes = [f for f in features if f.kind == "cPlane"]
    variables = [stage_length_variable(f) for f in features if f.kind == "assignVariable"]
    rows, previous, variable_ops = Rows(), [], {}
    _, saved, _ = native_draft()
    for i, stage in enumerate(variables):
        fid = "variable_" + str(i)
        node = {"featureId": fid, "nodeId": "node_" + fid, "featureType": "assignVariable",
                "parameters": [{"parameterId": "name", "value": stage["name"]},
                               {"parameterId": "mode", "value": "ASSIGNED"},
                               {"parameterId": "variableType", "value": "LENGTH"},
                               *[{"parameterId": k, "expression": stage["expression"],
                                  "units": "millimeter", "value": float(stage["expression"][:-2])}
                                 for k in ("value", "lengthValue")]]}
        saved["children"].insert(-1, node)
        op = "variable-" + str(i) * 32
        variable_ops[stage["logical_id"]] = op
        rows[op] = {"target": "/".join(TARGET.to_dict().values()), "state": "observed",
                    "action": "experimental_variable_populate", "logical_id": stage["logical_id"],
                    "intent": json.dumps({"source_stages": variables, "source_index": i,
                        "before_state": {"editingFeatureId": fid}, "expected_tree": copy.deepcopy(saved)}),
                    "observation": json.dumps({"definition_observed": True, "feature_id": fid})}
    for i, plane in enumerate(planes[:index+1]):
        before, _, binding = native_draft("Top" if i < 2 else "Right")
        draft = before["tree"]["children"][1]
        draft["featureId"] = "fresh_plane_" + str(i)
        draft["nodeId"] = "fresh_node_" + str(i)
        before["editingFeatureId"] = draft["featureId"]
        before["tree"] = copy.deepcopy(saved)
        before["tree"]["children"].insert(-1, draft)
        baseline = {"target": TARGET.to_dict(), "connected": True, "editingFeatureId": None,
                    "element_microversion": "5" * 24, "tree": copy.deepcopy(saved)}
        args = dict(logical_id=plane.logical_id, before=before, baseline=baseline, binding=binding,
                    target=TARGET, previous_op_ids=previous.copy(),
                    variable_op_ids={name: variable_ops[name] for name in plane.dependencies}, journal=rows)
        if i == index:
            return features, args
        intent = plane_population_intent(features, **args)
        op = "plane-" + str(i) * 32
        rows[op] = {"target": "/".join(TARGET.to_dict().values()), "state": "observed",
                    "action": "experimental_plane_populate", "logical_id": plane.logical_id,
                    "intent": json.dumps(intent), "observation": json.dumps({"definition_observed": True,
                                                               "feature_id": draft["featureId"]})}
        previous.append(op)
        saved = copy.deepcopy(intent["expected_tree"])
        saved["children"].insert(-1, {"featureId": "sketch_"+str(i), "featureType": "newSketch", "nodeId": "s"+str(i)})
        saved["children"].insert(-1, {"featureId": "extrude_"+str(i), "featureType": "extrude", "nodeId": "e"+str(i)})


@pytest.mark.parametrize("index", range(5))
def test_all_five_planes_preserve_interleaved_features(index):
    features, args = scenario(index)
    intent = plane_population_intent(features, **args)
    assert intent["source_index"] == index
    assert len(intent["identity_map"]) == index
    assert intent["expected_tree"]["children"][:-2] == args["baseline"]["tree"]["children"][:-1]
    assert intent["source_stages"][index]["frame_verified"] is False
    if index == 3:
        assert intent["source_stages"][index]["magnitude_expression"] == "-(-#width / 2 - #wheelThickness)"
        assert set(intent["variable_identity_map"]) == {"#width", "#wheelThickness"}


@pytest.mark.parametrize("fault", ["baseline_target", "baseline_busy", "baseline_revision", "baseline_tree",
    "missing_previous", "previous_unknown", "prior_plane_changed", "missing_variable", "variable_unknown",
    "variable_target", "variable_source", "variable_value", "variable_identity", "draft_not_default", "binding"])
def test_writer_rejects_unproven_baseline_order_dependency_or_draft(fault):
    features, args = scenario(3)
    if fault == "baseline_target": args["baseline"]["target"] = {}
    if fault == "baseline_busy": args["baseline"]["editingFeatureId"] = "busy"
    if fault == "baseline_revision": args["baseline"]["element_microversion"] = REV
    if fault == "baseline_tree": args["baseline"]["tree"]["children"][0]["nodeId"] = "changed"
    if fault == "missing_previous": args["previous_op_ids"].pop()
    if fault == "previous_unknown": args["journal"][args["previous_op_ids"][0]]["state"] = "unknown"
    if fault == "missing_variable": args["variable_op_ids"].pop("#width")
    if fault.startswith("variable_"):
        row = args["journal"][args["variable_op_ids"]["#width"]]
        if fault == "variable_unknown": row["state"] = "unknown"
        if fault == "variable_target": row["target"] = "other"
        if fault == "variable_source":
            intent = json.loads(row["intent"]); intent["source_stages"][1]["expression"] = "91 mm"
            row["intent"] = json.dumps(intent)
        if fault == "variable_identity": row["observation"] = json.dumps({"definition_observed": True, "feature_id": "wrong"})
    if fault in {"variable_value", "prior_plane_changed"}:
        for tree in (args["baseline"]["tree"], args["before"]["tree"]):
            fid = "variable_1" if fault == "variable_value" else "fresh_plane_0"
            node = next(n for n in tree["children"] if n.get("featureId") == fid)
            node["parameters"][-1]["value"] = 99
    if fault == "draft_not_default":
        args["before"]["tree"]["children"][-2]["parameters"][2]["expression"] = "24 mm"
    if fault == "binding": args["binding"]["query_data"]["featureId"] = "Top"
    with pytest.raises(Unsupported):
        plane_population_intent(features, **args)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "capability", "pending", "predispatch", "timeout", "wrong_receipt"])
async def test_population_prepares_before_dispatch_and_never_replays(tmp_path, fault):
    from types import SimpleNamespace
    from h2cad.backend import UncertainWrite
    from h2cad.journal import Journal
    from h2cad.native import PreDispatchRejected
    from h2cad.native_planes import populate_test_plane
    _, args = scenario(0)
    journal = Journal(tmp_path / "journal.sqlite")
    calls = []
    if fault == "pending":
        journal.prepare(op_id="prior", target="other/target/studio", expected_revision=REV,
                        action="other", logical_id="other", intent={})
    async def health():
        return {"extension_connected": True,
                "capabilities": [] if fault == "capability" else ["h2_native_plane_populate_server_v1"],
                "extension": {"capabilities": ["h2_native_plane_populate_page_v1", "h2_native_completion_receipt_page_v1"]}}
    async def raw_state(target): return copy.deepcopy(args["before"])
    async def command(job):
        calls.append(job)
        assert journal.get(job["op_id"])["state"] == "prepared"
        if fault == "predispatch": raise PreDispatchRejected("not sent")
        if fault == "timeout": raise TimeoutError("unknown")
        return {"op_id": "wrong" if fault == "wrong_receipt" else job["op_id"]}
    async def reconcile(op_id, tab_id):
        assert len(calls) == 1 and journal.get(op_id)["state"] == "sent"
        journal.transition(op_id, "observed", observation={"definition_observed": True})
        return {"op_id": op_id, "evidence": {"definition_observed": True, "frame_verified": False}}
    backend = SimpleNamespace(create_target=TARGET.to_dict(), tab_id=7, raw_state=raw_state,
        bridge=SimpleNamespace(health=health, command=command, reconcile_saved_source_plane=reconcile))
    kwargs = {"logical_id": args["logical_id"], "previous_op_ids": [], "baseline": args["baseline"],
              "reference_binding": args["binding"], "variable_op_ids": {}, "journal": journal}
    try:
        if fault:
            with pytest.raises((Unsupported, UncertainWrite, PreDispatchRejected)):
                await populate_test_plane(backend, TARGET, SOURCE, **kwargs)
        else:
            result = await populate_test_plane(backend, TARGET, SOURCE, **kwargs)
            assert result == {"definition_observed": True, "frame_verified": False}
        assert len(calls) == (0 if fault in {"capability", "pending"} else 1)
        if calls:
            assert journal.get(calls[0]["op_id"])["state"] == (
                "rejected" if fault == "predispatch" else "unknown" if fault in {"timeout", "wrong_receipt"} else "observed")
    finally:
        journal.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["receipt", "pre_dispatch", "post_dispatch", "transport"])
async def test_real_native_bridge_transports_and_classifies_plane_commands(outcome):
    import httpx
    from h2cad.backend import UncertainWrite
    from h2cad.native import NativeBridge, PreDispatchRejected
    requests = []
    op_id = "plane-" + "a" * 32
    job = {"kind": "partstudio_populate_plane", "op_id": op_id, "target": TARGET.to_dict(),
           "plane_edit": {"feature_id": "allocated_plane", "expression": "20 mm"}}
    def handler(request):
        requests.append(request)
        assert request.method == "POST" and request.url.path == "/command"
        assert json.loads(request.content) == job
        if outcome == "transport":
            raise httpx.ReadTimeout("unknown after send", request=request)
        if outcome in {"pre_dispatch", "post_dispatch"}:
            return httpx.Response(409, json={"error": "test failure", "write_stage": outcome})
        return httpx.Response(200, json={"op_id": op_id, "completion_pending": True})
    bridge = NativeBridge("test-token-" + "a" * 32, transport=httpx.MockTransport(handler))
    try:
        if outcome == "receipt":
            assert await bridge.command(job) == {"op_id": op_id, "completion_pending": True}
        else:
            with pytest.raises(PreDispatchRejected if outcome == "pre_dispatch" else UncertainWrite):
                await bridge.command(job)
        assert len(requests) == 1
    finally:
        await bridge.close()


@pytest.mark.asyncio
async def test_unsupported_job_rejection_is_strictly_before_http():
    import httpx
    from h2cad.native import NativeBridge
    requests = []
    def handler(request):
        requests.append(request)
        raise AssertionError("Local unsupported jobs must not reach HTTP")
    bridge = NativeBridge("test-token-" + "a" * 32, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(Unsupported, match="Browser-mode adapter permits only native editor jobs"):
            await bridge.command({"kind": "unsupported"})
        assert requests == []
    finally:
        await bridge.close()


@pytest.mark.parametrize("fault", [None, "receipt", "error", "revision", "tree", "marker", "guard", "pending", "rpc"])
def test_one_off_local_rejection_proof_fails_closed(fault):
    import runpy
    recovery = runpy.run_path(str(SOURCE.parents[2] / "artifacts/recover-plane37-local-rejection.py"))
    op, target, revision, fid = (recovery[k] for k in ("OP", "TARGET", "REVISION", "FEATURE"))
    before = {"target": target, "connected": True, "element_microversion": revision,
              "editingFeatureId": fid, "tree": {"children": [{"featureId": "preserved_variable", "value": 180}]}}
    row = {"op_id": op, "state": "unknown", "action": "experimental_plane_populate",
           "target": "/".join(target.values()), "logical_id": "Chassis height", "expected_revision": revision,
           "error": recovery["ERROR"], "receipt": None, "observation": None,
           "intent": json.dumps({"before_state": before})}
    sample = {"state": before, "health": {"extension_connected": True, "pending": 0},
              "guard": {"schema": 1, "unknown_write": False, "reload": None},
              "editor": {"ready": True, "element_microversion": revision, "incomplete_feature_marker": None,
                         "busy_reasons": {"feature_edit": True, "pending_rpc": False, "motion": False,
                                          "incomplete_feature_edit": False, "incomplete_transform": False, "drag": False}}}
    samples = [copy.deepcopy(sample), copy.deepcopy(sample)]
    if fault == "receipt": row["receipt"] = "{}"
    if fault == "error": row["error"] = "transport timeout"
    if fault == "revision": samples[1]["state"]["element_microversion"] = "f"*24
    if fault == "tree": samples[1]["state"]["tree"]["children"][0]["value"] = 181
    if fault == "marker": samples[1]["editor"]["incomplete_feature_marker"] = {"op_id": op}
    if fault == "guard": samples[1]["guard"]["unknown_write"] = True
    if fault == "pending": samples[1]["health"]["pending"] = 1
    if fault == "rpc": samples[1]["editor"]["busy_reasons"]["pending_rpc"] = True
    if fault:
        with pytest.raises(ValueError): recovery["prove"](row, samples)
    else:
        proof = recovery["prove"](row, samples)
        assert proof["classification"] == "rejected_before_http"
        assert proof["modeling_dispatched"] is False and proof["definition_observed"] is False
