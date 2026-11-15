"""Read-only resolution of saved body lineage during one fresh native draft."""
from __future__ import annotations
import copy
import re

from .backend import Unsupported
from .native_body_sets import _OBSERVED_INSERTABLE_FILTER, inspect_historical_server_body_inventory
from .native_body_history import inspect_source_body_history
from .native_geometry import _stable
from .source_run import _adopt, _load, _lock


def _draft_stable(before, after, target, baseline):
    _stable(baseline, baseline, target)
    fid = before.get("editingFeatureId")
    children = before.get("tree", {}).get("children", [])
    nodes = [node for node in children if node.get("featureId") == fid]
    if (not isinstance(fid,str) or not fid or len(nodes)!=1
            or nodes[0].get("$type")!="bsedit.GBTMFeature"
            or nodes[0].get("featureType")!="extrude" or nodes[0].get("suppressed") is not False
            or not nodes[0].get("nodeId")
            or before.get("target")!=target.to_dict() or before.get("connected") is not True
            or before.get("microversion")!=baseline["microversion"]
            or not re.fullmatch(r"[a-f0-9]{24}",str(before.get("element_microversion")))
            or any(s.get("h2Readback",{}).get("incompleteFeatureEdit") for s in (before,after))):
        raise Unsupported("One fresh unsuppressed native extrusion draft on the saved document required")
    index=children.index(nodes[0])
    tail=children[index+1:]
    if tail and not (len(tail)==1 and tail[0].get("$type")=="bsedit.GBTMRollback"
                    and tail[0].get("nodeId") and not tail[0].get("featureId")):
        raise Unsupported("Fresh draft must be appended at end of source model")
    reduced=copy.deepcopy(before["tree"])
    reduced["children"].pop(index)
    if (reduced!=baseline["tree"] or any(n.get("nodeId")==nodes[0]["nodeId"]
            for n in baseline["tree"]["children"]) or any(before.get(k)!=after.get(k)
            for k in ("target","connected","editingFeatureId","microversion","element_microversion","tree","tab_id"))):
        raise Unsupported("Draft changed or does not preserve the exact saved baseline")


async def inspect_draft_body_scope(runpath, backend, source, target, journal, logical_id, baseline, *, require_selected_scope=False):
    if type(require_selected_scope) is not bool:
        raise Unsupported("Selected-scope verification option must be boolean")
    if backend.create_target!=target.to_dict() or backend.tab_id is None:
        raise Unsupported("Exact configured native target and tab required")
    baseline=copy.deepcopy(baseline)
    before=await backend.raw_state(target)
    if before.get("tab_id")!=backend.tab_id or baseline.get("tab_id")!=backend.tab_id:
        raise Unsupported("Baseline and active draft must belong to the configured tab")
    _draft_stable(before,before,target,baseline)
    with _lock(runpath):
        run,_=_load(runpath,source,target,journal)
        _adopt(run,journal)
        originals=[f["logical_id"] for f in run["plan"] if f["kind"]=="extrude"
            and f["stage"]["operation_type"]=="NEW" and f["logical_id"] in run["bindings"]]
    if logical_id not in originals:
        raise Unsupported("Requested scope must be an observed original source NEW body")
    histories={name:inspect_source_body_history(runpath,source,target,journal,
        logical_id=name,current_state=baseline) for name in originals}
    by_creator={h["target_feature_id"]:name for name,h in histories.items()}
    if len(by_creator)!=len(histories):
        raise Unsupported("Original source creator identities are not unique")
    allowed={name:{h["target_feature_id"]+".opExtrude"} |
        {cut["feature_id"]+".boolean.opBoolean" for cut in h["observed_removes"]}
        for name,h in histories.items()}
    schemas=[];reads=[];query_nodes=set()
    async def schema(name, required):
        response=await backend.bridge.command({"kind":"schema","target":target.to_dict(),
                                               "tab_id":backend.tab_id,"name":name})
        defaults=response.get("defaults")
        if (response.get("name")!=name or not isinstance(defaults,dict) or defaults.get("$type")!=name
                or set(defaults)!={"$type"}|set(required)):
            raise Unsupported("Native measurement schema differs from observed fields: "+name)
        schemas.append(copy.deepcopy(response))
        return {k:copy.deepcopy(v) for k,v in defaults.items() if k!="$type"}
    async def native(name,body):
        response=await backend.bridge.command({"kind":"native","target":target.to_dict(),"tab_id":backend.tab_id,
                                               "command":name,"body":body})
        result=response.get("result")
        if (not isinstance(result,dict) or any(response.get(k) for k in ("error","errorCode","errorEnum"))
                or any(result.get(k) for k in ("error","errorCode","errorEnum"))
                or response.get("microversion_before")!=before["microversion"]
                or response.get("microversion_after")!=before["microversion"]):
            raise Unsupported("Native read failed or document revision changed")
        current=await backend.raw_state(target)
        _draft_stable(before,current,target,baseline)
        reads.append({"command":name,"body":copy.deepcopy(body),"response":copy.deepcopy(response)})
        return response

    request=await schema("ui.document.GBTUiQueryInsertables",
                         {"targetElementId","sourceElementId","documentMicroversionId","filter"})
    request.update(targetElementId="",sourceElementId=target.eid,documentMicroversionId={"$type":"document.GBTMicroversionId","theId":baseline["microversion"]},
                   filter=copy.deepcopy(_OBSERVED_INSERTABLE_FILTER))
    inventory_response=await native("ui.document.GBTUiQueryInsertables",request)
    inventory=inspect_historical_server_body_inventory(target=target,
        historical_element_revision=baseline["element_microversion"],
        historical_document_revision=baseline["microversion"],
        current_document_revision=before["microversion"],request=request,response=inventory_response)
    bodies=[]
    for ident in inventory["body_ids"]:
        query=await schema("bsedit.GBTMIndividualQuery",
                           {"deterministicIds","hasUserCode","nodeId","queryString","sourceParseTreeNodes"})
        if (not isinstance(query["nodeId"],str) or not query["nodeId"] or query["nodeId"] in query_nodes
                or query["deterministicIds"]!=[] or query["queryString"]!="" or query["hasUserCode"] is not False
                or query["sourceParseTreeNodes"]!={}):
            raise Unsupported("Fresh observed native query constructor defaults required")
        query_nodes.add(query["nodeId"])
        query.update({"$type":"bsedit.GBTMIndividualQuery","deterministicIds":[ident]})
        query_request=await schema("ui.GBTUiGetQueryDataCall",{"elementId","messageId","queries","qFunction",
            "additionalArguments","queryNodeIdToInContextNodeId"})
        if (query_request["queries"]!=[] or query_request["qFunction"]!=""
                or query_request["additionalArguments"]!=[] or query_request["queryNodeIdToInContextNodeId"]!={}):
            raise Unsupported("Default explicit query read required")
        query_request.update(elementId=target.eid,queries=[query])
        query_response=await native("ui.GBTUiGetQueryDataCall",query_request)
        rows=query_response["result"].get("queryData")
        if (query_response["result"].get("$type")!="ui.GBTUiGetQueryDataResponse"
                or not isinstance(rows,list) or len(rows)!=1):
            raise Unsupported("One exact body query response required")
        row=rows[0]; detail=row.get("evaluationDetails",{})
        creator=row.get("featureId"); operation=detail.get("fullOperationId")
        name=by_creator.get(creator)
        if (row.get("deterministicIds")!=[ident] or row.get("selectionName")!="Part"
                or row.get("hasErrorEntity") is not False or row.get("isTemporaryFakeDataForSelection") is not False
                or detail.get("entityType")!=3 or detail.get("status")!=0
                or detail.get("outsideExactDependencies") is not False
                or name is None or operation not in allowed[name]):
            raise Unsupported("Draft body does not resolve to its observed source operation lineage")
        bodies.append({"body_id":ident,"logical_id":name,"creator_feature_id":creator,"full_operation_id":operation})
    if require_selected_scope:
        draft=next(n for n in before["tree"]["children"] if n.get("featureId")==before["editingFeatureId"])
        def parameter(name, kind):
            rows=[p for p in draft.get("parameters",[]) if p.get("parameterId")==name]
            if len(rows)!=1 or rows[0].get("$type")!=kind:
                raise Unsupported("Exact typed scope parameter required: "+name)
            return rows[0]
        operation=parameter("operationType","bsedit.GBTMParameterEnum")
        body_type=parameter("bodyType","bsedit.GBTMParameterEnum")
        if (operation.get("value")!="REMOVE" or operation.get("enumName")!="NewBodyOperationType"
                or body_type.get("value")!="SOLID" or body_type.get("enumName")!="ExtendedToolBodyType"
                or parameter("defaultScope","bsedit.GBTMParameterBoolean").get("value") is not False):
            raise Unsupported("Explicit solid REMOVE scope required; automatic all-body scope is unsupported")
        selected=parameter("booleanScope","bsedit.GBTMParameterQueryList").get("queries")
        required=sorted(b["body_id"] for b in bodies if b["logical_id"]==logical_id)
        selected_ids=[]; selected_nodes=set()
        if not isinstance(selected,list) or not selected:
            raise Unsupported("Nonempty explicit selected body queries required")
        for query in selected:
            if not isinstance(query,dict):
                raise Unsupported("Typed selected query object required")
            ids=query.get("deterministicIds")
            if (query.get("$type")!="bsedit.GBTMIndividualQuery" or query.get("hasUserCode") is not False
                    or query.get("queryString")!="" or query.get("sourceParseTreeNodes")!={}
                    or not isinstance(ids,list) or len(ids)!=1 or not isinstance(ids[0],str)
                    or not isinstance(query.get("nodeId"),str) or not query["nodeId"]
                    or query["nodeId"] in selected_nodes):
                raise Unsupported("One explicit native body identity per selected query required")
            selected_ids.extend(ids);selected_nodes.add(query["nodeId"])
        if len(set(selected_ids))!=len(selected_ids) or sorted(selected_ids)!=required:
            raise Unsupported("UI-selected scope must equal the complete required body set")
        selected_request=await schema("ui.GBTUiGetQueryDataCall",{"elementId","messageId","queries","qFunction",
            "additionalArguments","queryNodeIdToInContextNodeId"})
        if (selected_request["queries"]!=[] or selected_request["qFunction"]!=""
                or selected_request["additionalArguments"]!=[] or selected_request["queryNodeIdToInContextNodeId"]!={}):
            raise Unsupported("Default explicit selected query read required")
        selected_request.update(elementId=target.eid,queries=copy.deepcopy(selected))
        selected_response=await native("ui.GBTUiGetQueryDataCall",selected_request)
        result=selected_response["result"];rows=result.get("queryData")
        if result.get("$type")!="ui.GBTUiGetQueryDataResponse" or not isinstance(rows,list) or len(rows)!=len(required):
            raise Unsupported("Every selected body requires its own fresh query result")
        observed=[]
        for row in rows:
            ids=row.get("deterministicIds");detail=row.get("evaluationDetails",{})
            if (not isinstance(ids,list) or len(ids)!=1 or ids[0] not in required
                    or row.get("featureId")!=histories[logical_id]["target_feature_id"]
                    or detail.get("fullOperationId") not in allowed[logical_id]
                    or row.get("selectionName")!="Part" or row.get("hasErrorEntity") is not False
                    or row.get("isTemporaryFakeDataForSelection") is not False
                    or detail.get("entityType")!=3 or detail.get("status")!=0
                    or detail.get("outsideExactDependencies") is not False):
                raise Unsupported("Selected scope readback does not resolve the required source bodies")
            observed.extend(ids)
        if sorted(observed)!=required:
            raise Unsupported("Selected scope readback omits or duplicates a required body")
    after=await backend.raw_state(target)
    _draft_stable(before,after,target,baseline)
    for name,history in histories.items():
        if inspect_source_body_history(runpath,source,target,journal,logical_id=name,current_state=baseline)!=history:
            raise Unsupported("Source history changed during draft inspection")
    partitions={name:sorted(b["body_id"] for b in bodies if b["logical_id"]==name) for name in histories}
    required=partitions[logical_id]
    if not required:
        raise Unsupported("Source body has no inventoried descendants in the draft")
    history=histories[logical_id]
    return {"target":target.to_dict(),"target_logical_id":logical_id,
        "target_op_id":history["target_op_id"],"target_feature_id":history["target_feature_id"],
        "source_sha256":history["source_sha256"],"snapshot_sha256":history["snapshot_sha256"],
        "draft_feature_id":before["editingFeatureId"],"draft_element_microversion":before["element_microversion"],
        "document_microversion":before["microversion"],"baseline_element_microversion":baseline["element_microversion"],
        "scope_body_ids":required,"single_survivor":len(required)==1,"body_partitions":partitions,
        "selected_scope_requirement":{"match":"exact_set","body_ids":list(required),"defaultScope":False},
        "independently_verified":True,"write_ready":False,"ui_scope_selection_verified":require_selected_scope,
        "allowed_operation_ids":sorted(allowed[logical_id]),"history_proofs":histories,"inventory_proof":inventory,
        "missing_evidence":(["native writer/reconciliation integration"] if require_selected_scope else
            ["actual UI-selected scope equality and native writer/reconciliation integration"]),
        "raw_provenance":{"baseline":baseline,"before_state":before,"after_state":after,"schemas":schemas,"reads":reads}}
