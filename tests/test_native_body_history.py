import copy
import json
from pathlib import Path

import pytest

from h2cad.backend import Unsupported, UncertainWrite
from h2cad.journal import Journal
from h2cad.model import Target
from h2cad import source_run
from h2cad.native_body_history import inspect_source_body_history

TARGET=Target("a"*24,"b"*24,"c"*24)
SOURCE=Path(__file__).resolve().parents[1]/"fixtures/native/carrier_split_scope_sample.fs"


@pytest.fixture
def history(tmp_path):
    journal=Journal(tmp_path/"journal.sqlite");path=tmp_path/"run.json"
    source_run.initialize_run(path,SOURCE,TARGET,journal)
    plan=source_run._plan(SOURCE.read_text(),TARGET);nodes=[];ops={}
    for index,feature in enumerate(plan):
        name=feature["logical_id"];kind=feature["kind"];op=f"op-{index}"
        node={"featureId":f"feature-{index}","nodeId":f"node-{index}","featureType":kind,"suppressed":False}
        nodes.append(node)
        intent={"source_feature":feature["source_feature"],"expected_tree":{"children":copy.deepcopy(nodes)}}
        if kind in ("assignVariable","cPlane"):
            stages=[f["stage"] for f in plan if f["kind"]==kind]
            intent.update(source_stages=stages,source_index=stages.index(feature["stage"]))
        if kind=="extrude" and feature["stage"]["operation_type"]=="REMOVE":
            intent["target_body_op_id"]=ops[feature["stage"]["target_body_logical_id"]]
        journal.prepare(op_id=op,target="/".join(TARGET.to_dict().values()),expected_revision="1"*24,
            action=source_run._ACTIONS[kind],logical_id=name,intent=intent)
        journal.transition(op,"sent")
        journal.transition(op,"observed",observation={"definition_observed":True,"feature_id":node["featureId"],
            "node_id":node["nodeId"],"saved_feature":copy.deepcopy(node),"constraint_graph_verified":True,"origin_verified":True})
        ops[name]=op
    state={"target":TARGET.to_dict(),"connected":True,"editingFeatureId":None,"microversion":"2"*24,
        "element_microversion":"3"*24,"tree":{"children":nodes+[{"$type":"bsedit.GBTMRollback","nodeId":"rollback"}]}}
    yield path,journal,state
    journal.close()


def test_ordered_observed_cut_history_does_not_write_checkpoint_or_journal(history):
    path,journal,state=history;before=path.read_bytes();count=journal._db.total_changes
    result=inspect_source_body_history(path,SOURCE,TARGET,journal,logical_id="Carrier blank",current_state=state)
    assert result["target_op_id"]=="op-3"
    assert result["observed_removes"]==[{"logical_id":"Carrier through bores","op_id":"op-8","feature_id":"feature-8"}]
    assert len(result["ordered_bound_feature_ids"])==9 and result["write_ready"] is False
    assert path.read_bytes()==before and journal._db.total_changes==count


@pytest.mark.parametrize("fault",["unknown","changed","suppressed","missing_latest","reordered","busy","source","unresolved","unknown_observation"])
def test_unknown_changed_or_stale_history_is_rejected(history,fault):
    path,journal,state=history;source=SOURCE
    if fault=="unknown":state["tree"]["children"].insert(-1,{"featureId":"unknown-cut","featureType":"extrude"})
    if fault=="changed":state["tree"]["children"][3]["name"]="changed"
    if fault=="suppressed":state["tree"]["children"][8]["suppressed"]=True
    if fault=="missing_latest":state["tree"]["children"].pop(8)
    if fault=="reordered":state["tree"]["children"][4:6]=reversed(state["tree"]["children"][4:6])
    if fault=="busy":state["editingFeatureId"]="active"
    if fault=="source":source=SOURCE.read_text()+"\n//changed"
    if fault=="unresolved":journal.prepare(op_id="pending",target="other",expected_revision="x",action="test",logical_id="x",intent={})
    if fault=="unknown_observation":journal._db.execute("UPDATE writes SET state='rejected' WHERE op_id='op-8'")
    with pytest.raises((Unsupported,UncertainWrite)):
        inspect_source_body_history(path,source,TARGET,journal,logical_id="Carrier blank",current_state=state)
