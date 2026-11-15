"""Read-only native solid inventory and mass-property measurements.

No CAD command, scope authorization, or shape equivalence is inferred from
these measurements. Document and element revision namespaces stay separate.
"""
from __future__ import annotations

import copy
import math
import re

from .backend import Unsupported
from .native_body_sets import _OBSERVED_INSERTABLE_FILTER, inspect_server_body_inventory


def _stable(before, after, target):
    fields=("target","connected","editingFeatureId","microversion","element_microversion","tree")
    if (before.get("target")!=target.to_dict() or before.get("connected") is not True
            or before.get("editingFeatureId","missing") is not None
            or not isinstance(before.get("tree",{}).get("children"),list)
            or any(not re.fullmatch(r"[a-f0-9]{24}",str(before.get(k))) for k in ("microversion","element_microversion"))
            or any(before.get(k)!=after.get(k) for k in fields)
            or any(s.get("h2Readback",{}).get("incompleteFeatureEdit") for s in (before,after))):
        raise Unsupported("Stable connected saved tree and both revision identities required for measurements")


def _quantity(values, factor):
    if (not isinstance(values,list) or len(values)!=3
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in values)):
        raise Unsupported("Native measurement requires finite nominal/min/max arrays")
    nominal, low, high=values
    if not (0 <= low <= nominal <= high) or nominal <= 0:
        raise Unsupported("Native measurement bounds are unordered or nonpositive")
    converted=[v*factor for v in values]
    if not all(math.isfinite(v) for v in converted):
        raise Unsupported("Converted native measurement is not finite")
    return dict(zip(("nominal","min","max"),converted))


def _body_measurement(body_id, query_response, mass_response):
    result=query_response.get("result",{});rows=result.get("queryData")
    if result.get("$type")!="ui.GBTUiGetQueryDataResponse" or not isinstance(rows,list) or len(rows)!=1:
        raise Unsupported("One exact body query response required")
    row=rows[0];detail=row.get("evaluationDetails",{})
    creator=row.get("featureId");operation=detail.get("fullOperationId")
    if (row.get("deterministicIds")!=[body_id] or row.get("selectionName")!="Part"
            or row.get("hasErrorEntity") is not False or row.get("isTemporaryFakeDataForSelection") is not False
            or detail.get("entityType")!=3 or detail.get("status")!=0
            or detail.get("outsideExactDependencies") is not False
            or not isinstance(creator,str) or not creator or not isinstance(operation,str) or not operation):
        raise Unsupported("Native query must resolve the exact inventoried solid body")
    result=mass_response.get("result",{})
    mass=result.get("massProp",{})
    if (result.get("$type")!="ui.GBTUiMassPropResponse" or type(result.get("error")) is not int
            or result["error"]!=0 or result.get("entitiesMissingMass")!=[]
            or result.get("entitiesWithOverrideMass")!=[] or mass.get("$type")!="math.GBTMassProperties"):
        raise Unsupported("Error-free native geometric mass-property response required")
    return {"body_id":body_id,"creator_feature_id":creator,"full_operation_id":operation,
            "volume_mm3":_quantity(mass.get("volume"),1e9),
            "surface_area_mm2":_quantity(mass.get("surfaceArea"),1e6)}


async def collect_native_geometry(backend, target):
    """Collect only supported schema/native reads; no viewer or mutation path."""
    if backend.create_target!=target.to_dict() or backend.tab_id is None:
        raise Unsupported("Exact configured native target and tab required")
    before=await backend.raw_state(target)
    _stable(before,before,target)
    from .native_read_session import NativeReadSession
    session = NativeReadSession(backend, target, before["microversion"], lambda current: _stable(before, current, target))
    schema, native = session.schema, session.native
    schemas, reads = session.schemas, session.reads
    query_nodes = set()

    request=await schema("ui.document.GBTUiQueryInsertables",
                         {"targetElementId","sourceElementId","documentMicroversionId","filter"})
    request.update(targetElementId="",sourceElementId=target.eid,documentMicroversionId=None,
                   filter=copy.deepcopy(_OBSERVED_INSERTABLE_FILTER))
    inventory_response=await native("ui.document.GBTUiQueryInsertables",request)
    inventory=inspect_server_body_inventory(target=target,element_revision=before["element_microversion"],
        document_revision=before["microversion"],request=request,response=inventory_response)
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
        mass_request=await schema("ui.GBTUiMassPropCall",{"computeCoplanarInputCSys","densities","elementId",
            "entityIds","geometryData","messageId","useDensities","userCentersOfMass","userInertia","userMassProperties"})
        if (mass_request["useDensities"] is not False or mass_request["computeCoplanarInputCSys"] is not False
                or any(mass_request[k]!=[] for k in ("densities","entityIds","geometryData","userCentersOfMass","userInertia","userMassProperties"))):
            raise Unsupported("Default geometry-only mass-property read required")
        mass_request.update(elementId=target.eid,entityIds=[ident])
        mass_response=await native("ui.GBTUiMassPropCall",mass_request)
        bodies.append(_body_measurement(ident,query_response,mass_response))
    after=await backend.raw_state(target)
    _stable(before,after,target)
    totals={metric:{bound:math.fsum(body[metric][bound] for body in bodies) for bound in ("nominal","min","max")}
            for metric in ("volume_mm3","surface_area_mm2")}
    return {"target":target.to_dict(),"element_microversion":before["element_microversion"],
            "document_microversion":before["microversion"],"body_count":len(bodies),"bodies":bodies,"totals":totals,
            "inventory_proof":inventory,"scope_write_ready":False,"shape_verified":False,
            "measurement_provenance":"native geometry-only mass properties; no material density or mass inference",
            "raw_provenance":{"before_state":before,"after_state":after,"schemas":schemas,"reads":reads}}
