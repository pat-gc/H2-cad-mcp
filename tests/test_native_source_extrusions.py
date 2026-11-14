import copy
import json

import pytest

from h2cad.backend import Unsupported, UncertainWrite
from h2cad.fsgen import compile_fsgen
from h2cad.native import stage_length_variable
from h2cad.native_sketches import source_sketch_plan
from h2cad.native_source_extrusions import source_extrusion_intent, populate_source_extrusion
from test_native_extrusion_mapping import ROOT, TARGET, state

SOURCE = ROOT / "fixtures/car/basic_car.fs"
SKETCH_OP = "source-sketch-" + "a"*32
VARIABLE_OP = "variable-" + "b"*32


def scenario(index=0):
    features = compile_fsgen(SOURCE, TARGET).features
    extrusions = [f for f in features if f.kind == "extrude"]
    feature = extrusions[index]
    sketch_source = next(f for f in features if f.kind == "newSketch" and f.logical_id in feature.dependencies)
    variables = [f for f in features if f.kind == "assignVariable"]
    plan = source_sketch_plan(sketch_source, variables)
    before, sketch, query = state()
    sketch.update(entities=copy.deepcopy(plan["entities"]), constraints=copy.deepcopy(plan["constraints"]))
    key = "/".join(TARGET.to_dict().values())
    rows = {SKETCH_OP: {"op_id": SKETCH_OP, "target": key, "state": "observed",
        "action": "experimental_source_sketch_populate", "logical_id": sketch_source.logical_id,
        "intent": json.dumps({"before_state": {"editingFeatureId": sketch["featureId"]},
                              "plan": plan, "source_feature": sketch_source.provenance["fsgen_feature_json"]}),
        "observation": json.dumps({"feature_id": sketch["featureId"], "node_id": sketch["nodeId"],
            "definition_observed": True, "origin_verified": True, "constraint_graph_verified": True,
            "saved_feature": sketch})}}
    var_op = None
    depth = feature.parameters["depth"]
    if depth.startswith("#"):
        var_op = VARIABLE_OP
        stages = [stage_length_variable(v) for v in variables]
        vi = next(i for i,s in enumerate(stages) if s["logical_id"] == depth)
        variable = json.loads((ROOT / "tests/fixtures/native_variable_default.json").read_text())
        variable["featureId"] = "depthVariable_0"
        for p in variable["parameters"]:
            if p["parameterId"] == "name": p["value"] = stages[vi]["name"]
            if p["parameterId"] in ("lengthValue", "value"):
                p.update(expression=stages[vi]["expression"], value=float(stages[vi]["expression"][:-2]))
        before["tree"]["children"].insert(0, variable)
        rows[VARIABLE_OP] = {"op_id": VARIABLE_OP, "target": key, "state": "observed",
            "action": "experimental_variable_populate", "logical_id": depth,
            "intent": json.dumps({"before_state": {"editingFeatureId": variable["featureId"]},
                "source_stages": stages, "source_index": vi, "expected_tree": {"children": [variable]}}),
            "observation": json.dumps({"definition_observed": True, "feature_id": variable["featureId"]})}
    baseline = {**copy.deepcopy(before), "editingFeatureId": None, "element_microversion": "e"*24}
    baseline["tree"]["children"] = [n for n in baseline["tree"]["children"] if n.get("featureId") != before["editingFeatureId"]]
    return features, dict(logical_id=feature.logical_id, before=before, baseline=baseline,
        query_response=query, target=TARGET, sketch_op_id=SKETCH_OP, variable_op_id=var_op, journal=rows)


@pytest.mark.parametrize("index", range(5))
def test_source_depths_preserve_all_siblings_and_observed_sketch(index):
    features, args = scenario(index)
    intent = source_extrusion_intent(features, **args)
    assert intent["source_stage"]["depth_expression"] == ["8 mm", "#bodyHeight", "110 mm", "#wheelThickness", "#wheelThickness"][index]
    expected = copy.deepcopy(args["before"]["tree"])
    depth = next(p for n in expected["children"] if n.get("featureId") == "freshExtrude_0"
                 for p in n["parameters"] if p["parameterId"] == "depth")
    depth.update(expression=intent["source_stage"]["depth_expression"],value=intent["source_stage"]["depth_seed_mm"])
    assert intent["expected_tree"] == expected
    assert intent["saved_sketch_definition"] == next(n for n in expected["children"] if n.get("featureId") == "sourceSketch_0")


@pytest.mark.parametrize("fault", ["baseline", "baseline_busy", "baseline_target", "sketch_pending", "sketch_source",
    "sketch_graph", "sketch_origin", "sketch_saved", "sketch_identity", "variable_pending", "variable_source",
    "variable_live", "missing_variable", "region", "mode"])
def test_source_extrusion_refuses_unverified_dependencies_and_changed_baseline(fault):
    features,args=scenario(1)
    row=args["journal"][SKETCH_OP]
    observation=json.loads(row["observation"])
    if fault=="baseline": args["baseline"]["tree"]["children"][1]["nodeId"]="changed"
    if fault=="baseline_busy": args["baseline"]["editingFeatureId"]="busy"
    if fault=="baseline_target": args["baseline"]["target"]={}
    if fault=="sketch_pending": row["state"]="unknown"
    if fault=="sketch_source":
        si=json.loads(row["intent"]);si["source_feature"]["name"]="other";row["intent"]=json.dumps(si)
    if fault=="sketch_graph": observation["constraint_graph_verified"]=False
    if fault=="sketch_origin": observation["origin_verified"]=False
    if fault=="sketch_saved": observation["saved_feature"]["name"]="different"
    if fault=="sketch_identity": observation["node_id"]="other"
    row["observation"]=json.dumps(observation)
    if fault=="variable_pending": args["journal"][VARIABLE_OP]["state"]="unknown"
    if fault=="variable_source":
        vr=args["journal"][VARIABLE_OP];vi=json.loads(vr["intent"]);vi["source_stages"][2]["expression"]="38 mm";vr["intent"]=json.dumps(vi)
    if fault=="variable_live":
        for tree in (args["before"]["tree"],args["baseline"]["tree"]):tree["children"][0]["name"]="changed"
    if fault=="missing_variable":args["variable_op_id"]=None
    if fault=="region":args["query_response"]["result"]["queryData"][0]["featureId"]="other"
    if fault=="mode":
        draft=next(n for n in args["before"]["tree"]["children"] if n.get("featureId")=="freshExtrude_0")
        next(p for p in draft["parameters"] if p["parameterId"]=="operationType")["value"]="ADD"
    with pytest.raises(Unsupported):source_extrusion_intent(features,**args)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault",[None,"pre_dispatch","timeout","receipt"])
async def test_real_bridge_path_journals_before_depth_population_and_never_replays(tmp_path,fault):
    import httpx
    from types import SimpleNamespace
    from h2cad.journal import Journal
    from h2cad.native import NativeBridge,PreDispatchRejected
    _,args=scenario()
    journal=Journal(tmp_path/"journal.sqlite")
    row=args["journal"][SKETCH_OP]
    journal.prepare(op_id=SKETCH_OP,target=row["target"],expected_revision="f"*24,
        action=row["action"],logical_id=row["logical_id"],intent=json.loads(row["intent"]))
    journal.transition(SKETCH_OP,"sent",receipt={})
    journal.transition(SKETCH_OP,"observed",observation=json.loads(row["observation"]))
    writes=[]
    def handler(request):
        if request.url.path=="/health":
            return httpx.Response(200,json={"protocol":1,"extension_connected":True,
                "capabilities":["h2_source_extrude_server_v1"],"extension":{"capabilities":[
                    "h2_source_extrude_page_v1","h2_native_completion_receipt_page_v1"]}})
        body=json.loads(request.content)
        if request.url.path=="/command":
            if body["kind"]=="native":return httpx.Response(200,json=args["query_response"])
            assert body["kind"]=="partstudio_populate_extrude"
            writes.append(body)
            assert journal.get(body["op_id"])["state"]=="prepared"
            assert body["source_extrusion"]["depth_expression"]=="8 mm"
            assert body["source_extrusion"]["before_tree"]==args["before"]["tree"]
            if fault=="pre_dispatch":return httpx.Response(409,json={"error":"preflight rejected","write_stage":"pre_dispatch"})
            if fault=="timeout":raise httpx.ReadTimeout("unknown",request=request)
            return httpx.Response(200,json={"op_id":"wrong" if fault=="receipt" else body["op_id"],"completion_pending":True})
        assert request.url.path=="/local/reconcile_saved_source_extrude"
        assert len(writes)==1 and journal.get(body["op_id"])["state"]=="sent"
        evidence={"definition_observed":True,"solid_geometry_verified":False,"depth_expression":"8 mm"}
        journal.transition(body["op_id"],"observed",observation=evidence)
        return httpx.Response(200,json={"status":"observed_source_extrusion","op_id":body["op_id"],"evidence":evidence})
    bridge=NativeBridge("test-source-extrusion-"+"a"*32,transport=httpx.MockTransport(handler))
    async def raw_state(target):return copy.deepcopy(args["before"])
    backend=SimpleNamespace(create_target=TARGET.to_dict(),tab_id=7,raw_state=raw_state,bridge=bridge)
    try:
        kwargs=dict(logical_id="Chassis",sketch_op_id=SKETCH_OP,baseline=args["baseline"],journal=journal)
        if fault:
            with pytest.raises((PreDispatchRejected,UncertainWrite)):
                await populate_source_extrusion(backend,TARGET,SOURCE,**kwargs)
        else:
            evidence=await populate_source_extrusion(backend,TARGET,SOURCE,**kwargs)
            assert evidence["definition_observed"] and not evidence["solid_geometry_verified"]
        assert len(writes)==1
        assert journal.get(writes[0]["op_id"])["state"]==("rejected" if fault=="pre_dispatch" else "unknown" if fault else "observed")
    finally:
        await bridge.close();journal.close()
