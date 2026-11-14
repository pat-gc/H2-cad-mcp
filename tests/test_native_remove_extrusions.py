import copy
import json

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.native_source_extrusions import source_extrusion_intent
from test_native_source_extrusions import scenario, ROOT, TARGET, SKETCH_OP

BODY_OP = "extrude-" + "d"*32


def remove_scenario():
    _,args=scenario()
    features=compile_fsgen(ROOT/"fixtures/native/carrier_remove_scope_sample.fs",TARGET).features
    feature=next(f for f in features if f.logical_id=="Carrier through bores")
    source=next(f for f in features if f.logical_id=="Carrier holes")
    before=args["before"]
    draft=next(n for n in before["tree"]["children"] if n.get("featureId")==before["editingFeatureId"])
    body=copy.deepcopy(draft);body.update(featureId="sourceBody_0",nodeId="saved-body-node",name="Carrier blank")
    query={"$type":"bsedit.GBTMIndividualQuery","nodeId":"selected-body-query","deterministicIds":["body-id"],"queryString":"","hasUserCode":False,"sourceParseTreeNodes":{}}
    scope_response={"result":{"$type":"ui.GBTUiGetQueryDataResponse","queryData":[{
        "$type":"display.GBTQueryData","deterministicIds":["body-id"],"featureId":"sourceBody_0",
        "selectionName":"Part","hasErrorEntity":False,"isTemporaryFakeDataForSelection":False,
        "evaluationDetails":{"entityType":3,"status":0,"outsideExactDependencies":False,"fullOperationId":"sourceBody_0.opExtrude"}}]}}
    for p in draft["parameters"]:
        if p["parameterId"]=="operationType":p["value"]="REMOVE"
        if p["parameterId"]=="defaultScope":p["value"]=False
        if p["parameterId"]=="booleanScope":p["queries"]=[query]
    before["tree"]["children"].insert(0,body)
    # Both source and native sketch identity are proven by the observed sketch row.
    row=args["journal"][SKETCH_OP];si=json.loads(row["intent"])
    si["source_feature"]=source.provenance["fsgen_feature_json"]
    row.update(logical_id=source.logical_id,intent=json.dumps(si))
    target_source=next(f for f in features if f.logical_id=="Carrier blank")
    target_sketch=copy.deepcopy(next(n for n in before["tree"]["children"] if n.get("featureId")=="sourceSketch_0"))
    target_sketch.update(featureId="bodySketch_0",nodeId="body-sketch-node")
    before["tree"]["children"].insert(1,target_sketch)
    args["journal"][BODY_OP]={"op_id":BODY_OP,"target":"/".join(TARGET.to_dict().values()),"state":"observed",
        "action":"experimental_source_extrude_populate","logical_id":"Carrier blank",
        "intent":json.dumps({"before_state":{"editingFeatureId":"sourceBody_0"},"source_feature":target_source.provenance["fsgen_feature_json"],"sketch_feature_id":"bodySketch_0","saved_sketch_definition":target_sketch,"sketch_source_feature":next(f for f in features if f.logical_id=="Carrier outline").provenance["fsgen_feature_json"],"expected_tree":{"children":[body]}}),
        "observation":json.dumps({"definition_observed":True,"feature_id":"sourceBody_0"})}
    args["baseline"]["tree"]=copy.deepcopy(before["tree"])
    args["baseline"]["tree"]["children"]=[n for n in args["baseline"]["tree"]["children"] if n.get("featureId")!=before["editingFeatureId"]]
    args.update(logical_id=feature.logical_id,target_body_op_id=BODY_OP,scope_query_response=scope_response)
    return features,args


@pytest.mark.parametrize("fault",[None,"missing_op","pending_body","wrong_source","body_changed","wrong_body","scope_all","scope_multiple","scope_face","scope_error","reverse","missing_scope"])
def test_remove_requires_observed_exact_target_and_explicit_resolved_scope(fault):
    features,args=remove_scenario()
    draft=next(n for n in args["before"]["tree"]["children"] if n.get("featureId")==args["before"]["editingFeatureId"])
    ps={p["parameterId"]:p for p in draft["parameters"]}
    q=args["scope_query_response"]["result"]["queryData"][0]
    if fault=="missing_op":args["target_body_op_id"]=None
    if fault=="pending_body":args["journal"][BODY_OP]["state"]="unknown"
    if fault=="wrong_source":
        row=args["journal"][BODY_OP];i=json.loads(row["intent"]);i["source_feature"]["name"]="other";row["intent"]=json.dumps(i)
    if fault=="body_changed":
        args["before"]["tree"]["children"][0]["name"]="changed"
        args["baseline"]["tree"]["children"][0]["name"]="changed"
    if fault=="wrong_body":q["featureId"]="witness"
    if fault=="scope_all":ps["defaultScope"]["value"]=True
    if fault=="scope_multiple":ps["booleanScope"]["queries"]*=2
    if fault=="scope_face":q["evaluationDetails"]["entityType"]=2
    if fault=="scope_error":q["evaluationDetails"]["status"]=1
    if fault=="reverse":ps["oppositeDirection"]["value"]=True
    if fault=="missing_scope":args["scope_query_response"]=None
    if fault:
        with pytest.raises(Unsupported):source_extrusion_intent(features,**args)
    else:
        result=source_extrusion_intent(features,**args)
        expected=copy.deepcopy(args["before"]["tree"])
        node=next(n for n in expected["children"] if n.get("featureId")==args["before"]["editingFeatureId"])
        next(p for p in node["parameters"] if p["parameterId"]=="depth").update(value=24,expression="24 mm")
        assert result["expected_tree"]==expected
        assert result["target_body_op_id"]==BODY_OP
        assert result["saved_target_body_definition"]==expected["children"][0]


def test_two_circle_target_cannot_be_represented_by_one_native_body_selection():
    _,args=remove_scenario()
    text=(ROOT/"fixtures/native/carrier_remove_scope_sample.fs").read_text()
    start=text.index('    skRectangle(outline,')
    end=text.index('    skSolve(outline);',start)
    text=text[:start]+'''    skCircle(outline,"a",{"center":vector(10,5)*millimeter,"radius":3*millimeter});
    skCircle(outline,"b",{"center":vector(-10,5)*millimeter,"radius":3*millimeter});
'''+text[end:]
    features=compile_fsgen(text,TARGET).features
    row=args["journal"][BODY_OP];intent=json.loads(row["intent"])
    intent["source_feature"]=next(f for f in features if f.logical_id=="Carrier blank").provenance["fsgen_feature_json"]
    intent["sketch_source_feature"]=next(f for f in features if f.logical_id=="Carrier outline").provenance["fsgen_feature_json"]
    row["intent"]=json.dumps(intent)
    with pytest.raises(Unsupported,match="multi-body"):
        source_extrusion_intent(features,**args)


def test_remove_rejects_human_added_target_sketch_contour():
    features,args=remove_scenario()
    for state in (args["before"],args["baseline"]):
        sketch=next(n for n in state["tree"]["children"] if n.get("featureId")=="bodySketch_0")
        sketch["entities"].append({"entityId":"human-added-circle","nodeId":"new-contour"})
    with pytest.raises(Unsupported,match="source sketch changed"):
        source_extrusion_intent(features,**args)


@pytest.mark.asyncio
@pytest.mark.parametrize("split_first",[False,True])
async def test_direct_population_rejects_repeated_source_cut_before_any_bridge_or_journal_write(tmp_path,split_first):
    from types import SimpleNamespace
    from h2cad.journal import Journal
    from h2cad.native_source_extrusions import populate_source_extrusion
    text=(ROOT/"fixtures/native/carrier_remove_scope_sample.fs").read_text()
    if split_first:
        text=text.replace('skCircle(holes, "scopeProbe", {"center" : vector(10, 5) * millimeter, "radius" : 3 * millimeter});',
            'skRectangle(holes,"split",{"firstCorner":vector(-2,-40)*millimeter,"secondCorner":vector(2,40)*millimeter});')
    end=text.rfind('}')
    text=text[:end]+'''    extrude(context,id+"Second cut",{
        "entities":qSketchRegion(id+"Carrier holes"),"operationType":NewBodyOperationType.REMOVE,
        "endBound":BoundingType.BLIND,"depth":24*millimeter,"defaultScope":false,
        "booleanScope":qCreatedBy(id+"Carrier blank",EntityType.BODY)});
'''+text[end:]
    class NoBridge:
        async def health(self):pytest.fail("Repeated source cut reached bridge health")
        async def command(self,*args,**kwargs):pytest.fail("Repeated source cut reached browser")
    journal=Journal(tmp_path/"journal.sqlite")
    backend=SimpleNamespace(create_target=TARGET.to_dict(),tab_id=7,bridge=NoBridge())
    try:
        with pytest.raises(Unsupported,match="Repeated REMOVE target"):
            await populate_source_extrusion(backend,TARGET,text,logical_id="Second cut",
                sketch_op_id="not-read",target_body_op_id="not-read",baseline={},journal=journal)
        assert journal._db.execute("SELECT COUNT(*) FROM writes").fetchone()[0]==0
        features,args=remove_scenario()
        args["logical_id"]="Second cut"
        with pytest.raises(Unsupported,match="Repeated REMOVE target"):
            source_extrusion_intent(compile_fsgen(text,TARGET).features,**args)
    finally:journal.close()
