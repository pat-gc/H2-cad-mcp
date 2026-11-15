"""Real native measurement fixtures joined to a simulated observed source journal."""
import copy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported, UncertainWrite
from h2cad.journal import Journal
from h2cad import source_run
from h2cad.native_body_scope import inspect_current_body_scope
from test_native_geometry import setup as geometry_setup

ROOT=Path(__file__).resolve().parents[1]


def scenario(tmp_path,prefix="split",fault=None):
    backend,target,calls,records=geometry_setup(prefix=prefix)
    source=(ROOT/"fixtures/native/carrier_split_scope_sample.fs" if prefix=="split"
            else ROOT/"artifacts/robot/bearing_carrier_scope_fixture.fs")
    journal=Journal(tmp_path/"journal.sqlite");runpath=tmp_path/"run.json"
    source_run.initialize_run(runpath,source,target,journal)
    plan=source_run._plan(source.read_text(),target);nodes=[];ops={}
    target_record=next(r for r in records if r["body_id"]==("JQD" if prefix=="split" else "JID"))
    target_creator=target_record["response"]["result"]["queryData"][0]["featureId"]
    witness_creator=next(r for r in records if r["body_id"]=="JMD")["response"]["result"]["queryData"][0]["featureId"]
    cut_id=(target_record["response"]["result"]["queryData"][0]["evaluationDetails"]["fullOperationId"].removesuffix(".boolean.opBoolean")
            if prefix=="split" else "FsEO7A67vk0acIN_2")
    for index,feature in enumerate(plan):
        name=feature["logical_id"];kind=feature["kind"];op=f"op-{index}"
        fid={3:target_creator,6:witness_creator,8:cut_id}.get(index,f"feature-{index}")
        node={"featureId":fid,"nodeId":f"node-{index}","featureType":kind,"suppressed":False}
        nodes.append(node)
        intent={"source_feature":feature["source_feature"],"expected_tree":{"children":copy.deepcopy(nodes)}}
        if kind in ("assignVariable","cPlane"):
            stages=[f["stage"] for f in plan if f["kind"]==kind]
            intent.update(source_stages=stages,source_index=stages.index(feature["stage"]))
        if kind=="extrude" and feature["stage"]["operation_type"]=="REMOVE":intent["target_body_op_id"]=ops[feature["stage"]["target_body_logical_id"]]
        journal.prepare(op_id=op,target="/".join(target.to_dict().values()),expected_revision="1"*24,
            action=source_run._ACTIONS[kind],logical_id=name,intent=intent)
        journal.transition(op,"sent")
        journal.transition(op,"observed",observation={"definition_observed":True,"feature_id":fid,"node_id":node["nodeId"],
            "saved_feature":copy.deepcopy(node),"constraint_graph_verified":True,"origin_verified":True})
        ops[name]=op
    original_state=backend.raw_state
    reads=0
    async def state(given):
        nonlocal reads
        reads+=1
        value=await original_state(given)
        value["tree"]={"children":copy.deepcopy(nodes)+[{"$type":"bsedit.GBTMRollback","nodeId":"end"}]}
        if fault=="foreign_feature":value["tree"]["children"].insert(-1,{"featureId":"foreign-cut","featureType":"extrude"})
        if fault=="changed_witness":value["tree"]["children"][6]["name"]="human edit"
        if reads==2*len(records)+4:
            if fault=="final_revision":value["element_microversion"]="f"*24
            if fault=="final_journal":journal._db.execute("UPDATE writes SET state='rejected' WHERE op_id='op-8'")
        return value
    backend.raw_state=state
    original_command=backend.bridge.command
    async def command(job):
        result=await original_command(job)
        if job.get("command")=="ui.GBTUiGetQueryDataCall":
            row=result["result"]["queryData"][0]
            if row["featureId"]==target_creator:
                if fault=="unknown_creator":row["featureId"]="unknown"
                if fault=="unknown_operation":row["evaluationDetails"]["fullOperationId"]="unknown.boolean.opBoolean"
                if fault=="foreign_boolean":row["evaluationDetails"]["fullOperationId"]=witness_creator+".boolean.opBoolean"
        return result
    backend.bridge.command=command
    if fault=="unresolved":journal.prepare(op_id="pending",target="other",expected_revision="x",action="test",logical_id="x",intent={})
    return runpath,backend,source,target,journal,calls


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix,expected",[("native",["JID"]),("split",["JQD","JQH"])])
async def test_current_scope_joins_real_inventory_operations_and_observed_history(tmp_path,prefix,expected):
    path,backend,source,target,journal,calls=scenario(tmp_path,prefix)
    checkpoint=path.read_bytes();changes=journal._db.total_changes
    try:
        result=await inspect_current_body_scope(path,backend,source,target,journal,"Carrier blank")
        assert result["scope_body_ids"]==expected and result["single_survivor"]==(len(expected)==1)
        assert result["selected_scope_requirement"]=={"match":"exact_set","body_ids":expected,"defaultScope":False}
        assert result["body_partitions"]["Untouched witness"]==["JMD"]
        assert result["independently_verified"] is True and result["write_ready"] is False
        assert result["target_op_id"]=="op-3" and result["observed_removes"][0]["op_id"]=="op-8"
        assert len(result["allowed_operation_ids"])==2
        assert all(c["kind"] in ("schema","native") for c in calls)
        assert path.read_bytes()==checkpoint and journal._db.total_changes==changes
    finally:journal.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault",["foreign_feature","changed_witness","unknown_creator","unknown_operation",
    "foreign_boolean","final_revision","final_journal","unresolved"])
async def test_scope_rejects_unknown_lineage_foreign_changes_and_late_races(tmp_path,fault):
    path,backend,source,target,journal,calls=scenario(tmp_path,fault=fault)
    try:
        with pytest.raises((Unsupported,UncertainWrite)):
            await inspect_current_body_scope(path,backend,source,target,journal,"Carrier blank")
        assert all(c["kind"] in ("schema","native") for c in calls)
    finally:journal.close()
