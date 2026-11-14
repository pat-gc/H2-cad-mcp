"""Candidate evidence checks, not live cardinality or ancestry certification."""
import copy
import json
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.model import Target
from h2cad.native_body_sets import inspect_candidate_body_set, inspect_server_body_inventory

FIXTURE=Path(__file__).parent/"fixtures/native_body_inventory.json"


def case():
    f=json.loads(FIXTURE.read_text())
    target=Target(**f["target"])
    state={"target":f["target"],"connected":True,"editingFeatureId":None,
           "element_microversion":f["element_revision"],"tree":{"children":[]}}
    state["microversion"]=f["document_revision"]
    reads=copy.deepcopy(f["query_readbacks"])
    return dict(target=target,creator_feature_id=f["creator_feature_id"],before=state,after=copy.deepcopy(state),
                inventory=f["viewer"],query_readbacks=reads,selected_queries=copy.deepcopy(f["selected_queries"]),
                server_request=f["request"],server_response=f["response"])


def test_captured_server_inventory_and_viewer_agree_but_never_authorize_writes():
    args=case();proof=inspect_candidate_body_set(**args)
    assert proof["listed_body_ids"]==["JID","JMD"]
    assert proof["creator_candidate_body_ids"]==["JID"]
    assert proof["server_inventory"]["server_enumeration_verified"]
    assert proof["inventory_query_coverage_verified"] and proof["selected_scope_matches_candidates"]
    assert not proof["write_ready"] and not proof["complete"] and not proof["creator_lineage_complete"]
    args["inventory"].update(complete=True,write_ready=True)
    args["query_readbacks"][0]["response"].update(complete=True)
    assert inspect_candidate_body_set(**args)["write_ready"] is False


def test_unloaded_body_is_not_dropped_and_viewer_only_remains_partial():
    args=case();args["inventory"]["parts"][1]["loaded"]=False
    args.pop("server_request");args.pop("server_response")
    proof=inspect_candidate_body_set(**args)
    assert proof["listed_body_ids"]==["JID","JMD"] and proof["server_inventory"] is None
    assert proof["write_ready"] is False


@pytest.mark.parametrize("fault",["revision","tree","busy","viewer_stale","assembly","composite",
    "duplicate","missing_query","wrong_id","query_error","face","creator_op","scope_witness","scope_empty"])
def test_candidate_rejects_inconsistent_snapshot_coverage_and_scope(fault):
    a=case();read=a["query_readbacks"][0];q=read["response"]["result"]["queryData"][0]
    if fault=="revision":a["after"]["element_microversion"]="f"*24
    if fault=="tree":a["after"]["tree"]["children"].append({"featureId":"changed"})
    if fault=="busy":a["before"]["editingFeatureId"]="active"
    if fault=="viewer_stale":a["inventory"]["microversion"]="f"*24
    if fault=="assembly":a["inventory"]["parts"][0]["occurrence_path"]="occurrence"
    if fault=="composite":a["inventory"]["parts"][0]["composite"]=True
    if fault=="duplicate":a["inventory"]["parts"].append(a["inventory"]["parts"][0])
    if fault=="missing_query":a["query_readbacks"].pop()
    if fault=="wrong_id":q["deterministicIds"]=["foreign"]
    if fault=="query_error":q["evaluationDetails"]["status"]=1
    if fault=="face":q["evaluationDetails"]["entityType"]=2
    if fault=="creator_op":q["evaluationDetails"]["fullOperationId"]=a["creator_feature_id"]+".opBoolean"
    if fault=="scope_witness":a["selected_queries"].append(a["query_readbacks"][1]["query"])
    if fault=="scope_empty":a["selected_queries"]=[]
    with pytest.raises(Unsupported):inspect_candidate_body_set(**a)


@pytest.mark.parametrize("fault",["filter","source","version","multiple_studios","foreign_part","stale_part",
    "disabled","faulted","mesh","nested","duplicate","unknown_type","pagination","viewer_missing"])
def test_server_inventory_supported_shape_is_strict(fault):
    a=case();result=a["server_response"]["result"];studio=result["contents"][0];part=studio["children"][0]
    if fault=="filter":a["server_request"]["filter"]["includeParts"]=False
    if fault=="source":a["server_request"]["sourceElementId"]="f"*24
    if fault=="version":a["server_request"]["documentMicroversionId"]={"theId":"f"*24}
    if fault=="multiple_studios":result["contents"].append(copy.deepcopy(studio))
    if fault=="foreign_part":part["documentId"]="f"*24
    if fault=="stale_part":part["element"]["microversion"]["theId"]="f"*24
    if fault=="disabled":part["disableReason"]=1
    if fault=="faulted":part["hasFaults"]=True
    if fault=="mesh":part["isMesh"]=True
    if fault=="nested":part["children"]=[{}]
    if fault=="duplicate":studio["children"].append(copy.deepcopy(part))
    if fault=="unknown_type":part["$type"]="unreviewed"
    if fault=="pagination":result["nextPageToken"]="not-finished"
    if fault=="viewer_missing":a["inventory"]["parts"].pop()
    with pytest.raises(Unsupported):inspect_candidate_body_set(**a)


def test_simulated_split_selection_must_cover_every_candidate_but_still_not_write_ready():
    a=case();other=copy.deepcopy(a["inventory"]["parts"][0]);other["body_id"]="split-child"
    a["inventory"]["parts"].append(other)
    raw=copy.deepcopy(a["server_response"]["result"]["contents"][0]["children"][0]);raw["deterministicId"]="split-child"
    a["server_response"]["result"]["contents"][0]["children"].append(raw)
    read=copy.deepcopy(a["query_readbacks"][0]);read["query"]["nodeId"]="split-query"
    read["query"]["deterministicIds"]=["split-child"]
    read["response"]["result"]["queryData"][0]["deterministicIds"]=["split-child"]
    a["query_readbacks"].append(read)
    with pytest.raises(Unsupported,match="omits or adds"):
        inspect_candidate_body_set(**a)
    a["selected_queries"].append(copy.deepcopy(read["query"]))
    proof=inspect_candidate_body_set(**a)
    assert proof["creator_candidate_body_ids"]==["JID","split-child"]
    assert proof["write_ready"] is False and proof["complete"] is False


@pytest.mark.parametrize("fixture",["native_body_inventory.json","native_body_inventory_hidden.json"])
@pytest.mark.parametrize("target_element",[None,""])
def test_actual_server_inventory_includes_witness_even_when_hidden(fixture,target_element):
    f=json.loads((FIXTURE.parent/fixture).read_text())
    if target_element is not None:f["request"]["targetElementId"]=target_element
    proof=inspect_server_body_inventory(target=Target(**f["target"]),element_revision=f["element_revision"],
        document_revision=f["document_revision"],request=f["request"],response=f["response"])
    assert proof["body_ids"]==["JID","JMD"]
    assert proof["server_enumeration_verified"] and not proof["write_ready"]


@pytest.mark.parametrize("fault",["state_doc","query_doc","server_doc","confuse_doc_element"])
def test_document_and_element_revision_namespaces_are_not_interchangeable(fault):
    a=case()
    if fault=="state_doc":a["after"]["microversion"]="f"*24
    if fault=="query_doc":a["query_readbacks"][0]["response"]["microversion_before"]="f"*24
    if fault=="server_doc":a["server_response"]["microversion_after"]="f"*24
    if fault=="confuse_doc_element":a["query_readbacks"][0]["response"]["microversion_before"]=a["before"]["element_microversion"]
    with pytest.raises(Unsupported):inspect_candidate_body_set(**a)
