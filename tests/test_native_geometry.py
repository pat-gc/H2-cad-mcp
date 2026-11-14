"""Read-only collection through mocked native transport, replaying captured reads."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2cad.backend import Unsupported
from h2cad.model import Target
from h2cad.native_geometry import collect_native_geometry

FIXTURES=Path(__file__).parent/"fixtures"


def setup(fault=None, prefix="native"):
    inventory=json.loads((FIXTURES/(prefix+"_body_inventory.json")).read_text())
    records=json.loads((FIXTURES/(prefix+"_geometry_reads.json")).read_text())["records"]
    target=Target(**inventory["target"])
    state={"target":target.to_dict(),"connected":True,"editingFeatureId":None,"tree":{"children":[]},
           "element_microversion":inventory["element_revision"],"microversion":inventory["document_revision"]}
    calls=[]
    class Bridge:
        async def command(self,job):
            assert job["kind"] in {"schema","native"}
            assert job["target"]==target.to_dict() and job["tab_id"]==7
            calls.append(copy.deepcopy(job))
            if job["kind"]=="schema":
                name=job["name"]
                if name=="ui.document.GBTUiQueryInsertables":
                    defaults={"targetElementId":"","sourceElementId":"","documentMicroversionId":None,"filter":{}}
                elif name=="bsedit.GBTMIndividualQuery":
                    i=sum(c.get("name")==name for c in calls)-1
                    defaults=copy.deepcopy(records[0 if fault=="reused_query_node" else i]["query_schema"]["defaults"])
                elif name=="ui.GBTUiGetQueryDataCall":
                    defaults={"elementId":"","messageId":"","queries":[],"qFunction":"","additionalArguments":[],"queryNodeIdToInContextNodeId":{}}
                elif name=="ui.GBTUiMassPropCall":
                    defaults=copy.deepcopy(records[0]["mass_request"]);defaults.update(elementId="",entityIds=[])
                    if fault=="density":defaults["useDensities"]=True
                else:pytest.fail("Unexpected native schema")
                if fault=="schema_extra":defaults["newUnreviewedOption"]=True
                return {"name":name,"classId":1,"defaults":{"$type":name,**defaults}}
            name=job["command"]
            if name=="ui.document.GBTUiQueryInsertables":
                assert job["body"]["targetElementId"]=="" and job["body"]["sourceElementId"]==target.eid
                assert job["body"]["filter"]["includeParts"] is True
                response=copy.deepcopy(inventory["response"])
            elif name in ("ui.GBTUiGetQueryDataCall","ui.GBTUiMassPropCall"):
                body_id=(job["body"]["queries"][0]["deterministicIds"][0] if name=="ui.GBTUiGetQueryDataCall" else job["body"]["entityIds"][0])
                record=next(r for r in records if r["body_id"]==body_id)
                response=copy.deepcopy(record["response" if name=="ui.GBTUiGetQueryDataCall" else "mass_response"])
                if name=="ui.GBTUiGetQueryDataCall" and fault=="query_wrong_body":response["result"]["queryData"][0]["deterministicIds"]=["wrong"]
                if name=="ui.GBTUiMassPropCall":
                    assert job["body"]["useDensities"] is False
                    mass=response["result"]["massProp"]
                    if fault=="error":response["result"]["error"]=1
                    if fault=="nan":mass["volume"][0]=float("nan")
                    if fault=="order":mass["surfaceArea"]=[2,3,4]
                    if fault=="short":mass["volume"]=[1,1]
                    if fault=="negative":mass["volume"]=[-1,-2,0]
                    if fault=="bool":mass["volume"]=[True,0,2]
            else:pytest.fail("Mutation or unsupported read dispatched")
            if fault=="error_code":response["result"]["errorCode"]=1
            if fault=="document_revision":response["microversion_after"]="f"*24
            if fault=="element_revision":state["element_microversion"]="f"*24
            if fault=="tree":state["tree"]["children"].append({"featureId":"changed"})
            return response
    async def raw_state(given):
        assert given==target
        return copy.deepcopy(state)
    backend=SimpleNamespace(create_target=target.to_dict(),tab_id=7,bridge=Bridge(),raw_state=raw_state)
    return backend,target,calls,records


@pytest.mark.asyncio
async def test_actual_per_body_volume_area_conversion_and_read_only_provenance():
    backend,target,calls,records=setup()
    result=await collect_native_geometry(backend,target)
    assert result["body_count"]==2
    assert [b["body_id"] for b in result["bodies"]]==["JID","JMD"]
    assert result["bodies"][0]["volume_mm3"]["nominal"]==pytest.approx(34465.30428151816)
    assert result["bodies"][1]["volume_mm3"]["nominal"]==pytest.approx(10800)
    assert result["totals"]["volume_mm3"]["nominal"]==pytest.approx(45265.30428151816)
    for body,record in zip(result["bodies"],records):
        assert body["surface_area_mm2"]["nominal"]==pytest.approx(record["mass_response"]["result"]["massProp"]["surfaceArea"][0]*1e6)
        for quantity in ("volume_mm3","surface_area_mm2"):
            assert body[quantity]["min"] <= body[quantity]["nominal"] <= body[quantity]["max"]
    assert len([c for c in calls if c["kind"]=="native"])==5
    assert len(result["raw_provenance"]["reads"])==5
    assert not result["scope_write_ready"] and not result["shape_verified"]
    assert result["element_microversion"]!=result["document_microversion"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault",["schema_extra","reused_query_node","density","query_wrong_body","error",
    "nan","order","short","negative","bool","error_code","document_revision","element_revision","tree"])
async def test_changed_or_unproven_measurement_fails_without_mutation(fault):
    backend,target,calls,_=setup(fault)
    with pytest.raises(Unsupported):await collect_native_geometry(backend,target)
    assert all(c["kind"] in {"schema","native"} for c in calls)
    assert not any("op_id" in c for c in calls)


@pytest.mark.asyncio
async def test_actual_split_bodies_read_boolean_operations_without_scope_authority():
    backend,target,calls,_=setup(prefix="split")
    result=await collect_native_geometry(backend,target)
    assert result["body_count"]==3
    assert [b["volume_mm3"]["nominal"] for b in result["bodies"]]==pytest.approx([10800,19440,19440])
    assert result["totals"]["volume_mm3"]["nominal"]==pytest.approx(49680)
    descendants=result["bodies"][1:]
    assert descendants[0]["creator_feature_id"]==descendants[1]["creator_feature_id"]
    assert all(b["full_operation_id"].endswith(".boolean.opBoolean") for b in descendants)
    assert not result["scope_write_ready"] and not result["shape_verified"]
