import copy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native_sketches import source_sketch_plan, sketch_population_intent

ROOT = Path(__file__).resolve().parents[1]
TARGET = Target("a" * 24, "b" * 24, "c" * 24)


def source():
    fs = compile_fsgen(ROOT / "fixtures/car/basic_car.fs", TARGET).features
    return fs, [f for f in fs if f.kind == "assignVariable"]


def test_actual_car_plans_preserve_expressions_and_use_only_fixed_local_origin():
    fs, variables = source()
    plans = [source_sketch_plan(f, variables) for f in fs if f.kind == "newSketch"]
    assert [(len(p["entities"]),len(p["constraints"])) for p in plans] == [(5,13),(5,13),(3,7),(3,7),(3,7)]
    for plan in plans:
        assert plan["entities"][0]["$type"] == "bsedit.GBTMSketchPoint"
        assert plan["entities"][0]["isConstruction"] is False
        assert plan["constraints"][0]["constraintType"] == 16
        assert not any(p["parameterId"].startswith("external") for c in plan["constraints"] for p in c["parameters"])
        assert len({n["entityId"] for n in plan["entities"]+plan["constraints"]}) == len(plan["entities"])+len(plan["constraints"])
        source_expressions = [p["expression"] for c in plan["source_stage"]["source_constraints"] for p in c["parameters"] if p["parameterId"]=="length"]
        native_expressions = [p["expression"] for c in plan["constraints"] for p in c["parameters"] if p["parameterId"]=="length"]
        assert sorted(source_expressions) == sorted(native_expressions)
    assert plans[0]["inferred_alignment_constraints"] == ["pos6y"]
    assert plans[1]["inferred_alignment_constraints"] == ["pos6y"]
    for plan in plans[2:]:
        assert not plan["inferred_alignment_constraints"]
        assert plan["graph_anchors"]["front.center"] == [.065,.015,0]
        assert plan["graph_anchors"]["rear.center"] == [-.065,.015,0]


def test_plan_never_supplies_native_node_ids_and_rejects_anchor_name_collision():
    fs, variables = source()
    feature = next(f for f in fs if f.logical_id == "Chassis sketch")
    plan = source_sketch_plan(feature, variables)
    def no_node_ids(value):
        if isinstance(value, dict):
            assert "nodeId" not in value
            for v in value.values(): no_node_ids(v)
        elif isinstance(value, list):
            for v in value:no_node_ids(v)
    no_node_ids(plan["entities"])
    no_node_ids(plan["constraints"])
    changed = copy.deepcopy(feature)
    changed.parameters["sketchPlane"] = ["wrong plane"]
    with pytest.raises(Unsupported):source_sketch_plan(changed,variables)


def test_new_draft_must_preserve_exact_saved_baseline_before_journal_binding():
    fs, _ = source()
    baseline = {"target": TARGET.to_dict(), "connected": True, "editingFeatureId": None,
                "tree": {"children": [{"featureId":"preserved", "nodeId":"old"}]}}
    before = {**baseline, "editingFeatureId":"draft", "tree": {"children": [
        {"featureId":"preserved", "nodeId":"changed"},
        {"featureId":"draft","nodeId":"fresh","featureType":"newSketch","entities":[],"constraints":[]}]}}
    with pytest.raises(Unsupported,match="unrelated"):
        sketch_population_intent(fs,"Chassis sketch",before,baseline,target=TARGET,
                                 plane_op_id="ignored",variable_op_ids={},journal=None)


@pytest.mark.parametrize("fault", [None,"plane_source","plane_identity","variable_source","variable_identity","variable_missing"])
def test_source_sketch_requires_observed_exact_plane_and_variable_bindings(tmp_path,fault):
    from h2cad.journal import Journal
    from h2cad.native import stage_length_variable
    from h2cad.native_planes import stage_offset_plane
    fs, variables = source()
    nodes = [{"featureId":"length_0","nodeId":"length-node","featureType":"assignVariable"},
             {"featureId":"width_0","nodeId":"width-node","featureType":"assignVariable"},
             {"featureId":"plane_0","nodeId":"plane-node","featureType":"cPlane"}]
    baseline={"target":TARGET.to_dict(),"connected":True,"editingFeatureId":None,
              "element_microversion":"a"*24,"tree":{"$type":"bsedit.GBTMModel","children":copy.deepcopy(nodes)}}
    before=copy.deepcopy(baseline);before.update(editingFeatureId="sketch_0",element_microversion="b"*24)
    before["tree"]["children"].append({"featureId":"sketch_0","nodeId":"sketch-node","featureType":"newSketch","entities":[],"constraints":[]})
    journal=Journal(tmp_path/"journal.sqlite")
    key="/".join(TARGET.to_dict().values())
    operations={}
    def observed(op,logical,action,stage,fid):
        journal.prepare(op_id=op,target=key,expected_revision="a"*24,action=action,logical_id=logical,
                        intent={"before_state":{"editingFeatureId":fid},"source_stages":[stage],"source_index":0,
                                "expected_tree":{"children":copy.deepcopy(nodes)}})
        journal.transition(op,"sent",receipt={})
        journal.transition(op,"observed",observation={"definition_observed":True,"feature_id":fid})
    try:
        for name,fid in [("#length","length_0"),("#width","width_0")]:
            stage=stage_length_variable(next(v for v in variables if v.logical_id==name))
            if fault=="variable_source" and name=="#width":stage["expression"]="91 mm"
            observed(name,name,"experimental_variable_populate",stage,fid);operations[name]=name
        plane=next(f for f in fs if f.logical_id=="Chassis height")
        stage=stage_offset_plane(plane,variables=variables)
        if fault=="plane_source":stage["magnitude_expression"]="99 mm"
        observed("plane-op","Chassis height","experimental_plane_populate",stage,"plane_0")
        if fault=="plane_identity":
            before["tree"]["children"][2]["nodeId"]="changed";baseline["tree"]["children"][2]["nodeId"]="changed"
        if fault=="variable_identity":
            before["tree"]["children"][1]["nodeId"]="changed";baseline["tree"]["children"][1]["nodeId"]="changed"
        if fault=="variable_missing":del operations["#width"]
        if fault:
            with pytest.raises(Unsupported):sketch_population_intent(fs,"Chassis sketch",before,baseline,target=TARGET,
                plane_op_id="plane-op",variable_op_ids=operations,journal=journal)
        else:
            intent=sketch_population_intent(fs,"Chassis sketch",before,baseline,target=TARGET,
                plane_op_id="plane-op",variable_op_ids=operations,journal=journal)
            assert intent["plane_feature_id"]=="plane_0"
            assert intent["plan"]["logical_id"]=="Chassis sketch"
    finally:journal.close()


@pytest.mark.parametrize("stage", [None,"pre_dispatch","after_dispatch"])
def test_native_bridge_routes_source_sketch_and_classifies_write_outcomes(stage):
    import asyncio
    import json
    import httpx
    from h2cad.native import NativeBridge, PreDispatchRejected
    from h2cad.backend import UncertainWrite
    async def run():
        calls=[]
        async def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200,json={"op_id":"test"} if stage is None else {"error":"test", "write_stage":stage})
        bridge=NativeBridge("a"*32,transport=httpx.MockTransport(handler))
        try:
            job={"kind":"partstudio_populate_source_sketch"}
            if stage is None:assert await bridge.command(job)=={"op_id":"test"}
            else:
                with pytest.raises(PreDispatchRejected if stage=="pre_dispatch" else UncertainWrite):await bridge.command(job)
            assert calls==[job]
        finally:await bridge.http.aclose()
    asyncio.run(run())
