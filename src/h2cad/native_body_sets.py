"""Read-only candidate body-set checks; never authorize a CAD write.

The viewer inventory enumerates cached body metadata, not a certified complete
kernel result. Query feature IDs are observed associations, not an ancestry
proof. This module deliberately exposes no caller-controlled completeness flag.
"""
from __future__ import annotations

import hashlib
import json
import re

from .backend import Unsupported
from .model import Target


def inspect_candidate_body_set(*, target: Target, creator_feature_id: str,
                               before: dict, after: dict, inventory: dict,
                               query_readbacks: list[dict], selected_queries: list[dict],
                               server_request: dict | None = None, server_response: dict | None = None) -> dict:
    """Cross-check one stable saved snapshot and coverage of its listed bodies.

    ``query_readbacks`` contains the exact observed query and response for every
    listed body. No query constructors or deterministic IDs are synthesized.
    Successful checks still return complete=False and write_ready=False.
    """
    td = target.to_dict()
    if any(not re.fullmatch(r"[a-f0-9]{24}", str(v)) for v in td.values()):
        raise Unsupported("Exact target required")
    revision = before.get("element_microversion")
    document_revision = before.get("microversion")
    if (not isinstance(creator_feature_id,str) or not creator_feature_id
            or not re.fullmatch(r"[a-f0-9]{24}",str(revision))
            or not re.fullmatch(r"[a-f0-9]{24}",str(document_revision))
            or before.get("target")!=td or before.get("connected") is not True
            or before.get("editingFeatureId","missing") is not None
            or not isinstance(before.get("tree",{}).get("children"),list)
            or any(after.get(k)!=before.get(k) for k in
                   ("target","connected","editingFeatureId","element_microversion","microversion","tree"))):
        raise Unsupported("Stable connected saved target, revision and whole tree required")
    for state in (before,after):
        if state.get("h2Readback",{}).get("incompleteFeatureEdit"):
            raise Unsupported("Unresolved feature marker blocks body-set inspection")
    if (inventory.get("target")!=td or inventory.get("microversion")!=revision
            or inventory.get("source")!="loaded-viewer-tessellation"
            or inventory.get("exact_cad") is not False or inventory.get("error")
            or not isinstance(inventory.get("parts"),list) or not inventory["parts"]):
        raise Unsupported("Same-revision Part Studio viewer inventory required")
    bodies = {}
    for part in inventory["parts"]:
        ident=part.get("body_id")
        if (not isinstance(ident,str) or not ident or ident in bodies
                or part.get("occurrence_path")!="" or part.get("composite") is not False
                or part.get("full_element_id")!=td["eid"]+"-"+revision):
            raise Unsupported("Distinct noncomposite bodies from this exact Part Studio revision required")
        bodies[ident]=part
    server_proof=None
    if server_request is not None or server_response is not None:
        if not isinstance(server_request,dict) or not isinstance(server_response,dict):
            raise Unsupported("Server request and response must be supplied together")
        server_proof=inspect_server_body_inventory(target=target,element_revision=revision,
                                                  request=server_request,response=server_response,document_revision=document_revision)
        if server_proof["body_ids"]!=sorted(bodies):
            raise Unsupported("Viewer body inventory differs from server enumeration")
    if not isinstance(query_readbacks,list) or len(query_readbacks)!=len(bodies):
        raise Unsupported("Every listed body requires one query readback, including unloaded bodies")

    def identity(query):
        ids=query.get("deterministicIds") if isinstance(query,dict) else None
        if (not isinstance(query,dict) or query.get("$type")!="bsedit.GBTMIndividualQuery"
                or query.get("queryString")!="" or not query.get("nodeId")
                or not isinstance(ids,list) or len(ids)!=1 or not isinstance(ids[0],str) or not ids[0]):
            raise Unsupported("One observed explicit body query required")
        return ids[0]

    associations = {}
    for item in query_readbacks:
        ident=identity(item.get("query"))
        response=item.get("response",{})
        if (response.get("microversion_before")!=document_revision
                or response.get("microversion_after")!=document_revision):
            raise Unsupported("Query document revision differs from stable snapshot")
        result=response.get("result",{})
        data=result.get("queryData")
        if (ident not in bodies or ident in associations
                or result.get("$type")!="ui.GBTUiGetQueryDataResponse"
                or not isinstance(data,list) or len(data)!=1):
            raise Unsupported("Body readback inventory coverage differs")
        row=data[0]; detail=row.get("evaluationDetails",{})
        fid=row.get("featureId"); operation=detail.get("fullOperationId")
        if (row.get("deterministicIds")!=[ident] or row.get("selectionName")!="Part"
                or row.get("hasErrorEntity") is not False or row.get("isTemporaryFakeDataForSelection") is not False
                or detail.get("entityType")!=3 or detail.get("status")!=0
                or detail.get("outsideExactDependencies") is not False
                or not isinstance(fid,str) or not fid or not isinstance(operation,str) or not operation.startswith(fid+".")):
            raise Unsupported("Unambiguous solid association required for every listed body")
        if fid==creator_feature_id and operation!=creator_feature_id+".opExtrude":
            raise Unsupported("Target creator operation does not match the observed NEW lineage guard")
        associations[ident]={"feature_id":fid,"full_operation_id":operation}
    candidates=sorted(ident for ident,row in associations.items() if row["feature_id"]==creator_feature_id)
    if not candidates or not isinstance(selected_queries,list):
        raise Unsupported("Target creator candidate bodies and explicit selected scope required")
    selected=[identity(query) for query in selected_queries]
    if len(selected)!=len(set(selected)) or sorted(selected)!=candidates:
        raise Unsupported("Selected scope omits or adds bodies relative to the observed creator candidates")
    digest=hashlib.sha256(json.dumps({"target":td,"revision":revision,"tree":before["tree"],
        "inventory":inventory,"query_readbacks":query_readbacks,"selected_queries":selected_queries,
        "server_request":server_request,"server_response":server_response},
        sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {"target":td,"element_microversion":revision,"document_microversion":document_revision,"creator_feature_id":creator_feature_id,
        "listed_body_ids":sorted(bodies),"creator_candidate_body_ids":candidates,
        "selected_body_ids":sorted(selected),"observed_associations":associations,
        "inventory_query_coverage_verified":True,"selected_scope_matches_candidates":True,
        "evidence_sha256":digest,"server_inventory":server_proof,"complete":False,"creator_lineage_complete":False,"write_ready":False,
        "missing_evidence":["authoritative complete current solid-body enumeration",
                            "complete creator-descendant semantics after modifying features",
                            "binding to observed source journal and modification chain"]}


_OBSERVED_INSERTABLE_FILTER = {'$type': 'bsedit.GBTInsertablesFilter', 'includeParts': True, 'includeSurfaces': True, 'includeSketches': True, 'includeReferenceFeatures': False, 'includeAssemblies': False, 'includeFeatureStudios': False, 'includeBlobs': False, 'allowedBlobMimeTypes': [], 'excludeNewerFSVersions': False, 'maxFeatureScriptVersion': 0, 'includePartStudios': True, 'includeFeatures': False, 'includeMeshes': True, 'includeWires': False, 'includeFlattenedBodies': True, 'includeApplications': False, 'allowedApplicationMimeTypes': [], 'includeCompositeParts': True, 'includeFSTables': False, 'includeFSComputedPartPropertyFunctions': False, 'includeVariables': False, 'includeVariableStudios': False, 'allowedBlobExtensions': [], 'includeSketchesOnFlat': True, 'isObsoletion': False, 'onlyCustomStandardContent': False}


def inspect_server_body_inventory(*, target: Target, element_revision: str,
                                  request: dict, response: dict, document_revision: str) -> dict:
    """Validate the captured server enumeration shape; no CAD/query execution.

    Hidden-body and split-body live coverage remains pending. No supplied
    `complete` flag can upgrade this result to write authorization.
    """
    td=target.to_dict()
    if (not re.fullmatch(r"[a-f0-9]{24}",str(element_revision))
            or not re.fullmatch(r"[a-f0-9]{24}",str(document_revision))
            or response.get("microversion_before")!=document_revision
            or response.get("microversion_after")!=document_revision
            or any(not re.fullmatch(r"[a-f0-9]{24}",str(v)) for v in td.values())
            or set(request)!={"targetElementId","sourceElementId","documentMicroversionId","filter"}
            or request["sourceElementId"]!=td["eid"]
            or (request["targetElementId"]!="" and not re.fullmatch(r"[a-f0-9]{24}",str(request["targetElementId"])))
            or request["documentMicroversionId"] is not None
            or request["filter"]!=_OBSERVED_INSERTABLE_FILTER):
        raise Unsupported("Exact observed include-parts server inventory request required")
    result=response.get("result",{})
    if (set(result)!={"$type","configuration","configurationKey","contents","updatedThumbnailUri"}
            or result["$type"]!="ui.document.GBTUiQueryAssemblyInsertableElementsResponse"
            or result["configuration"]!={} or result["configurationKey"]!=""
            or not isinstance(result["contents"],list) or len(result["contents"])!=1
            or response.get("error")):
        raise Unsupported("One unconfigured exact server inventory response required")
    studio=result["contents"][0]
    def exact_element(row):
        element=row.get("element",{})
        return (row.get("documentId")==td["did"] and row.get("documentVersionId")==""
            and row.get("configurationId")=="" and row.get("configurationParameterValues")==[]
            and type(row.get("disableReason")) is int and row["disableReason"]==0
            and element.get("$type")=="document.GBTDocumentElement"
            and element.get("dataType")=="onshape/partstudio" and element.get("elementId")==td["eid"]
            and element.get("microversion")=={"$type":"document.GBTMicroversionId","theId":element_revision})
    if (studio.get("$type")!="ui.document.GBTUiInsertablePartStudio" or not exact_element(studio)
            or studio.get("asParametricPartStudio") is not False or studio.get("configurationParameters")!=[]
            or not isinstance(studio.get("children"),list)
            or studio.get("insertableQuery")!="query = qUnion([ qEverything(EntityType.BODY)]);"):
        raise Unsupported("Exact current Part Studio enumeration required")
    parts={}
    for child in studio["children"]:
        if not exact_element(child) or child.get("children")!=[]:
            raise Unsupported("Foreign, stale, nested or disabled inventory row")
        if child.get("$type")=="ui.document.GBTUiInsertableFeatureGeometry":
            if child.get("featureType")!="newSketch" or child.get("isOnFlat") is not False:
                raise Unsupported("Unsupported inventory feature geometry")
            continue
        ident=child.get("deterministicId")
        if (child.get("$type")!="ui.document.GBTUiInsertablePart"
                or not isinstance(ident,str) or not ident or ident in parts
                or type(child.get("bodyType")) is not int or child["bodyType"]!=0
                or child.get("hasFaults") is not False or child.get("areFaultsIgnored") is not False
                or child.get("isMesh") is not False or child.get("isFlattenedBody") is not False):
            raise Unsupported("Distinct fault-free solid part rows required")
        parts[ident]={"body_id":ident,"body_type":0}
    if not parts:
        raise Unsupported("No current solid bodies in server inventory")
    return {"target":td,"element_microversion":element_revision,"document_microversion":document_revision,"body_ids":sorted(parts),
            "source":"observed_query_insertables_response","server_enumeration_verified":True,
            "complete":False,"write_ready":False,
            "missing_evidence":["hidden-body and split-body live enumeration coverage",
                                "creator-descendant semantics and source journal binding"]}
