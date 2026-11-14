"""Offline contract tests for the isolated source-driven sketch write."""

import copy
import json
from pathlib import Path

import pytest
import httpx

from h2cad.backend import UncertainWrite, Unsupported
from h2cad.journal import Journal
from h2cad.model import Target
from h2cad.native import NativeBackend, NativeBridge, PreDispatchRejected
from h2cad.cli import build_parser


TARGET = Target("4e078dec822b4e509616b1cb", "af0627de07264acf086e646a", "9a062f0eef8bb961f8c84f8e")


def test_explicit_checkpoint_target_binding_accepts_new_eid_and_rejects_preserved_car():
    from h2cad.native import _configured_create_target
    target = {"did": TARGET.did, "wid": TARGET.wid, "eid": "1926791d173990d5d45f70ef"}
    assert _configured_create_target(target) == target
    with pytest.raises(ValueError):
        _configured_create_target({**target, "eid": "45730d1931712e2c548fae00"})
    with pytest.raises(ValueError):
        _configured_create_target({**target, "did": "f5a8353dc826a9ec52106138"})
SOURCE = Path(__file__).resolve().parents[1] / "fixtures" / "native" / "minimal_plate.fs"


def state(*, populated=False, unrelated_changed=False):
    plane = {"$type": "bsedit.GBTMParameterQueryList", "parameterId": "sketchPlane",
             "queries": [{"$type": "bsedit.GBTMIndividualQuery", "deterministicIds": ["bound-top"]}]}
    sketch = {"featureId": "editorAllocated_0", "featureType": "newSketch", "nodeId": "fresh-node",
              "parameters": [plane], "entities": [], "constraints": []}
    if populated:
        spec = [("bottom", .02, 0, 1, 0, -.02, .02),
                ("right", .04, .01, 0, 1, -.01, .01),
                ("top", .02, .02, 1, 0, -.02, .02),
                ("left", 0, .01, 0, 1, -.01, .01)]
        sketch["entities"] = [{"$type": "bsedit.GBTMSketchCurveSegment", "entityId": "box." + side,
                               "isConstruction": False, "startParam": start, "endParam": end,
                               "geometry": {"$type": "bsedit.GBTCurveGeometryLine", "pntX": px,
                                            "pntY": py, "dirX": dx, "dirY": dy}}
                              for side, px, py, dx, dy, start, end in spec]
        def p(ident, value, type_name="String", **extra):
            return {"$type": "bsedit.GBTMParameter" + type_name, "parameterId": ident, "value": value, **extra}
        def c(ident, kind, first, second=None):
            params = [p("localFirst", "box." + first)]
            if second is not None:
                params.append(p("localSecond", "box." + second))
            return {"$type": "bsedit.GBTMSketchConstraint", "entityId": "box." + ident,
                    "constraintType": kind, "parameters": params}
        origin = c("fixedOrigin", 16, "bottom.start")
        def dim(ident, side, value):
            item = c(ident, 11, side)
            item["parameters"] += [p("direction", "MINIMUM", "Enum"),
                                   p("length", value, "Quantity", units="millimeter", expression=f"{value} mm"),
                                   p("alignment", "ALIGNED", "Enum"),
                                   p("labelRatio", .5, "Quantity"), p("labelDistance", .01, "Quantity")]
            return item
        sketch["constraints"] = [origin, c("perpendicular", 5, "top", "left"),
                                  c("parallel.1", 2, "bottom", "top"), c("parallel.2", 2, "left", "right"),
                                  c("horizontal", 4, "top"), c("corner0", 1, "bottom.start", "left.start"),
                                  c("corner1", 1, "bottom.end", "right.start"),
                                  c("corner2", 1, "top.start", "left.end"),
                                  c("corner3", 1, "top.end", "right.end"),
                                  dim("width", "top", 40), dim("height", "right", 20)]
    datum = {"featureId": "default-top", "featureType": "datum", "nodeId": "prior",
             "name": "changed" if unrelated_changed else "Top"}
    return {"target": {"did": TARGET.did, "wid": TARGET.wid, "eid": TARGET.eid},
            "element_microversion": "b" * 24 if populated else "a" * 24,
            "connected": True, "editingFeatureId": None if populated else "editorAllocated_0",
            "h2Readback": {"contract": "h2-readback-probe-v1", "complete": False},
            "tree": {"$type": "bsedit.GBTMModel", "children": [datum, sketch]}}


def solved_graph():
    ids = ("fixedOrigin", "perpendicular", "parallel.1", "parallel.2", "horizontal",
           "corner0", "corner1", "corner2", "corner3", "width", "height")
    constraints = {"box." + name: {"status": 4, "displayStatus": 1} for name in ids}
    constraints["box.fixedOrigin"].update(isExternal=False, type=16, referenceIds=["box.bottom.start"])
    return {"result": {"$type": "ui.sketch.GBTUiSketchGetConstraintGraphResponse",
                       "constraints": constraints, "worstSolveStatus": 1,
                       "sketchError": {"statusEnum": 0},
                       "references": {"box.bottom.start": {"isSketchEntity": True, "worstSolveStatus": 1,
                                                           "anchorX": 0, "anchorY": 0, "anchorZ": 0}}}}


class Bridge:
    def __init__(self, *, changed=False, capabilities=True, old_page=False, unanchored=False, pre_dispatch=False):
        self.calls = []
        self.changed = changed
        self.capabilities = capabilities
        self.old_page = old_page
        self.unanchored = unanchored
        self.pre_dispatch = pre_dispatch

    async def health(self):
        return {"extension_connected": True,
                "capabilities": ["h2_native_sketch_populate_server_v1", "h2_native_completion_receipt_server_v1"] if self.capabilities else [],
                "extension": {"capabilities": ["h2_native_sketch_populate_page_v1"] +
                              ([] if self.old_page else ["h2_native_fixed_origin_page_v1", "h2_native_completion_receipt_page_v1"])}}

    async def command(self, job):
        self.calls.append(copy.deepcopy(job))
        if job["kind"] == "state":
            populated = sum(x["kind"] == "state" for x in self.calls) > 1
            return state(populated=populated, unrelated_changed=self.changed and populated)
        if job["kind"] == "native":
            assert job["command"] == "ui.sketch.GBTUiSketchGetConstraintGraphCall"
            assert job["body"]["sketchFeatureId"] == "editorAllocated_0"
            graph = solved_graph()
            if self.unanchored:
                graph["result"]["references"]["box.bottom.start"]["anchorX"] = .01
            return graph
        assert job["kind"] == "partstudio_populate_sketch"
        assert job["sketch_edit"] == {"feature_id": "editorAllocated_0", "entity_prefix": "box",
                                      "rectangle_m": [0.0, 0.0, 0.04, 0.02]}
        if self.pre_dispatch:
            raise PreDispatchRejected("Invalid native field.")
        graph = solved_graph()["result"]
        if self.unanchored:
            graph["references"]["box.bottom.start"]["anchorX"] = .01
        return {"op_id": job["op_id"], "definition_candidate": True, "active_constraint_graph": graph}

    async def reconcile_completed_source_sketch(self, op_id, tab_id):
        assert tab_id == 17 and self.journal.get(op_id)["state"] == "sent"
        evidence = {"op_id": op_id, "feature_id": "editorAllocated_0",
                    "definition_observed": True, "origin_verified": True, "geometry_verified": False}
        self.journal.transition(op_id, "observed", observation=evidence)
        return {"op_id": op_id, "evidence": evidence}


@pytest.mark.asyncio
async def test_source_pair_journals_one_write_and_verifies_native_definition(tmp_path):
    bridge = Bridge()
    journal = Journal(tmp_path / "intent.sqlite")
    bridge.journal = journal
    evidence = await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert evidence["definition_observed"] is True and evidence["origin_verified"] is True
    assert evidence["geometry_verified"] is False
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch", "state"]
    assert journal.get(evidence["op_id"])["state"] == "observed"
    journal.close()


@pytest.mark.asyncio
async def test_unrelated_tree_change_remains_unknown_and_is_never_replayed(tmp_path):
    bridge = Bridge(changed=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(UncertainWrite, match="outcome unknown"):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch", "state"]
    assert journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_unbound_origin_graph_never_confirms_sketch(tmp_path):
    bridge = Bridge(unanchored=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(UncertainWrite, match="outcome unknown"):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch", "state"]
    assert journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_missing_loaded_capability_stops_before_journal_or_write(tmp_path):
    bridge = Bridge(capabilities=False)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(Unsupported, match="both advertise"):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert bridge.calls == [] and not journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_old_loaded_page_cannot_submit_fixed_origin_candidate(tmp_path):
    bridge = Bridge(old_page=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(Unsupported, match="both advertise"):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert bridge.calls == [] and not journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_attested_pre_dispatch_rejection_is_not_an_unknown_cad_write(tmp_path):
    bridge = Bridge(pre_dispatch=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(PreDispatchRejected, match="Invalid native field"):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert not journal.has_unresolved()
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch"]
    journal.close()


@pytest.mark.asyncio
async def test_uncertain_sketch_reconcile_reads_once_and_does_not_resubmit(tmp_path):
    bridge = Bridge(changed=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(UncertainWrite):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    op_id = journal.unresolved(f"{TARGET.did}/{TARGET.wid}/{TARGET.eid}")[0]["op_id"]
    before = len(bridge.calls)
    outcome = await NativeBackend(bridge, tab_id=17).reconcile_test_sketch(op_id, journal)
    assert outcome["status"] == "unknown"
    assert [x["kind"] for x in bridge.calls[before:]] == ["state"]
    journal.close()


def test_cli_exposes_explicit_temp_sketch_command():
    args = build_parser().parse_args(["experimental-sketch-populate", str(SOURCE),
                                      "--did", TARGET.did, "--wid", TARGET.wid, "--eid", TARGET.eid,
                                      "--bridge-config", "bridge.json", "--tab-id", "17", "--journal", "intent.sqlite"])
    assert args.command == "experimental-sketch-populate" and args.tab_id == 17


@pytest.mark.asyncio
@pytest.mark.parametrize("editing", ["editorAllocated_0", None, "otherFeature"])
async def test_known_applied_invalid_sketch_is_recorded_but_remains_blocking(tmp_path, editing):
    from h2cad.fsgen import compile_fsgen
    from h2cad.native import stage_minimal_pair
    before = state()
    before["element_microversion"] = "c" * 24
    before["tree"]["modelAnnotations"] = {"toleranceSchemaForParts": {"nodeId": "old-tab-node", "items": [1]}}
    after = state(populated=True)
    after["element_microversion"] = "97955554c86d659d57a74a68"
    after["editingFeatureId"] = editing
    after["tree"]["modelAnnotations"] = {"toleranceSchemaForParts": {"nodeId": "new-tab-node", "items": [1]}}
    class InvalidBridge:
        def __init__(self): self.calls = []
        async def command(self, job):
            self.calls.append(job["kind"])
            if job["kind"] == "state": return copy.deepcopy(after)
            assert job["command"] == "ui.sketch.GBTUiSketchGetConstraintGraphCall"
            return {"result": {"$type": ("ui.sketch.GBTUiSketchResponse" if editing is None
                                          else "ui.sketch.GBTUiSketchGetConstraintGraphResponse")}}
    journal = Journal(tmp_path / "intent.sqlite")
    op_id = "sketch-d9d02a9ba8b44bdea72b4bb67281c7e1"
    key = f"{TARGET.did}/{TARGET.wid}/{TARGET.eid}"
    blueprint = stage_minimal_pair(compile_fsgen(SOURCE, TARGET))
    journal.prepare(op_id=op_id, target=key, expected_revision="c" * 24,
                    action="experimental_sketch_populate", logical_id="Outline",
                    intent={"before_state": before, "feature_id": "editorAllocated_0",
                            "blueprint": blueprint.to_dict(), "entity_prefix": "box"})
    journal.transition(op_id, "unknown", error="Sketch command acknowledged but saved definition/idle state is unconfirmed; outcome unknown.")
    bridge = InvalidBridge()
    if editing == "otherFeature":
        with pytest.raises(Unsupported, match="Current failed sketch"):
            await NativeBackend(bridge, tab_id=17).classify_known_invalid_sketch(op_id, journal)
    else:
        outcome = await NativeBackend(bridge, tab_id=17).classify_known_invalid_sketch(op_id, journal)
        assert outcome["status"] == "applied_invalid_unresolved"
        assert outcome["evidence"]["saved_invalid_feature"] is (editing is None)
        assert outcome["evidence"]["constraint_graph_status"] == ("unavailable_saved" if editing is None else "empty_active")
    assert journal.has_unresolved() and journal.get(op_id)["state"] == "unknown"
    if editing != "otherFeature":
        assert json.loads(journal.get(op_id)["observation"])["classification"] == "applied_invalid"
        assert bridge.calls == ["state", "native"]
    else:
        assert journal.get(op_id)["observation"] is None
        assert bridge.calls == ["state"]
    journal.close()


class BeginBridge:
    def __init__(self, *, altered=False, old_page=False, outside_exact_dependencies=False,
                 query_feature="Top"):
        self.calls = []
        self.altered = altered
        self.old_page = old_page
        self.outside_exact_dependencies = outside_exact_dependencies
        self.query_feature = query_feature

    async def health(self):
        return {"extension_connected": True, "capabilities": ["h2_native_begin_top_sketch_server_v1",
                "h2_native_typed_top_plane_server_v1"],
                "extension": {"capabilities": ["h2_native_begin_top_sketch_page_v1"] +
                              ([] if self.old_page else ["h2_native_begin_top_ready_page_v1",
                                                        "h2_native_typed_top_plane_page_v1"])}}

    async def command(self, job):
        self.calls.append(copy.deepcopy(job))
        if job["kind"] == "partstudio_begin_top_sketch":
            return {"initiation_candidate": True, "feature_id": "newSketch_0", "feature_node_id": "fresh-node",
                    "plane_query_ids": ["bound-top"]}
        if job["kind"] == "native":
            return {"result": {"$type": "ui.GBTUiGetQueryDataResponse", "queryData": [{
                "deterministicIds": ["bound-top"], "featureId": self.query_feature, "selectionName": "Face",
                "evaluationDetails": {"fullOperationId": self.query_feature + ".planeOp", "entityType": 2, "status": 0,
                                      **({} if self.outside_exact_dependencies is None else
                                         {"outsideExactDependencies": self.outside_exact_dependencies})},
                "hasErrorEntity": False}]}}
        assert job["kind"] == "state"
        after = len(self.calls) > 1
        rollback = {"$type": "bsedit.GBTMRollback", "nodeId": "rollback-node"}
        sketch = {"$type": "bsedit.GBTMSketch", "featureId": "newSketch_0", "featureType": "newSketch",
                  "nodeId": "fresh-node", "entities": [], "constraints": [],
                  "parameters": [{"$type": "bsedit.GBTMParameterQueryList", "parameterId": "sketchPlane",
                                  "queries": [{"$type": "bsedit.GBTMIndividualQuery", "deterministicIds": ["bound-top"]}]}]}
        return {"target": {"did": TARGET.did, "wid": TARGET.wid, "eid": TARGET.eid},
                "connected": True, "editingFeatureId": "newSketch_0" if after else None,
                "element_microversion": ("b" if after else "a") * 24,
                "tree": {"$type": "bsedit.GBTMModel", "name": "changed" if after and self.altered else "Temp",
                         "children": [sketch, rollback] if after else [rollback]}}


@pytest.mark.asyncio
async def test_normal_top_sketch_initiation_has_durable_intent_and_fresh_id(tmp_path):
    bridge = BeginBridge()
    journal = Journal(tmp_path / "intent.sqlite")
    evidence = await NativeBackend(bridge, tab_id=17).begin_test_top_sketch(TARGET, journal)
    assert evidence["feature_id"] == "newSketch_0" and evidence["blank_sketch_observed"]
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_begin_top_sketch", "state", "native", "state"]
    assert journal.get(evidence["op_id"])["state"] == "observed"
    journal.close()


@pytest.mark.asyncio
async def test_top_sketch_initiation_unrelated_tree_change_stays_unknown(tmp_path):
    bridge = BeginBridge(altered=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(UncertainWrite, match="outcome unknown"):
        await NativeBackend(bridge, tab_id=17).begin_test_top_sketch(TARGET, journal)
    assert journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [{"outside_exact_dependencies": True},
                                    {"outside_exact_dependencies": None},
                                    {"query_feature": "Front"}])
async def test_top_sketch_independent_query_rejects_untrusted_face(tmp_path, kwargs):
    bridge = BeginBridge(**kwargs)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(UncertainWrite, match="outcome unknown"):
        await NativeBackend(bridge, tab_id=17).begin_test_top_sketch(TARGET, journal)
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_begin_top_sketch", "state", "native"]
    assert journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_old_loaded_page_cannot_start_top_sketch(tmp_path):
    bridge = BeginBridge(old_page=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(Unsupported, match="both advertise"):
        await NativeBackend(bridge, tab_id=17).begin_test_top_sketch(TARGET, journal)
    assert bridge.calls == [] and not journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_known_recovery_client_uses_one_authenticated_local_endpoint():
    seen = []
    def reply(request):
        seen.append((request.method, request.url.path, request.headers.get("authorization"), request.content))
        return httpx.Response(200, json={"status": "rejected_pre_dispatch", "op_id": "sketch-known"})
    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(reply))
    try:
        result = await bridge.reconcile_known_sketch_rejection("sketch-known", 17)
    finally:
        await bridge.close()
    assert result["status"] == "rejected_pre_dispatch"
    assert len(seen) == 1 and seen[0][0:2] == ("POST", "/local/reconcile_known_sketch_rejection")
    assert seen[0][2] == "Bearer " + "x" * 32


@pytest.mark.asyncio
async def test_manual_top_completion_client_uses_one_authenticated_local_endpoint():
    seen = []
    def reply(request):
        seen.append((request.method, request.url.path, request.headers.get("authorization"), json.loads(request.content)))
        return httpx.Response(200, json={"status": "observed_manual_top_completion", "op_id": "begin-sketch-" + "a" * 32})
    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(reply))
    try:
        result = await bridge.reconcile_completed_top_begin("begin-sketch-" + "a" * 32, 17)
    finally:
        await bridge.close()
    assert result["status"] == "observed_manual_top_completion"
    assert seen == [("POST", "/local/reconcile_completed_top_begin", "Bearer " + "x" * 32,
                     {"op_id": "begin-sketch-" + "a" * 32, "tab_id": 17})]


@pytest.mark.asyncio
async def test_partial_top_begin_client_reports_failure_without_another_modeling_send():
    seen = []
    def reply(request):
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"status": "observed_partial_top_begin",
                                         "evidence": {"outcome": "partial_failed",
                                                      "top_query_semantically_resolved": False}})
    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(reply))
    try:
        result = await bridge.reconcile_completed_top_begin("begin-sketch-" + "a" * 32, 17)
    finally:
        await bridge.close()
    assert result["evidence"]["outcome"] == "partial_failed"
    assert seen == [("POST", "/local/reconcile_completed_top_begin",
                     {"op_id": "begin-sketch-" + "a" * 32, "tab_id": 17})]


@pytest.mark.asyncio
async def test_manual_source_completion_client_uses_one_authenticated_local_endpoint():
    seen = []
    def reply(request):
        seen.append((request.method, request.url.path, request.headers.get("authorization"), json.loads(request.content)))
        return httpx.Response(200, json={"status": "observed_manual_source_completion", "op_id": "sketch-" + "a" * 32})
    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(reply))
    try:
        result = await bridge.reconcile_completed_source_sketch("sketch-" + "a" * 32, 17)
    finally:
        await bridge.close()
    assert result["status"] == "observed_manual_source_completion"
    assert seen == [("POST", "/local/reconcile_completed_source_sketch", "Bearer " + "x" * 32,
                     {"op_id": "sketch-" + "a" * 32, "tab_id": 17})]


@pytest.mark.asyncio
async def test_saved_source_extrude_client_uses_one_authenticated_read_only_endpoint():
    seen = []
    def reply(request):
        seen.append((request.method, request.url.path, request.headers.get("authorization"), json.loads(request.content)))
        return httpx.Response(200, json={"status": "observed_delayed_source_extrusion",
                                         "op_id": "extrude-" + "a" * 32})
    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(reply))
    try:
        result = await bridge.reconcile_saved_source_extrude("extrude-" + "a" * 32, 17)
    finally:
        await bridge.close()
    assert result["status"] == "observed_delayed_source_extrusion"
    assert seen == [("POST", "/local/reconcile_saved_source_extrude", "Bearer " + "x" * 32,
                     {"op_id": "extrude-" + "a" * 32, "tab_id": 17})]


@pytest.mark.parametrize("fault", [None, "wrong_source", "wrong_form"])
def test_editor_sketch_region_query_requires_exact_source_and_form(fault):
    from h2cad.native import _verify_source_region_query
    query = {"$type": "bsedit.GBTMIndividualSketchRegionQuery", "featureId": "source_0",
             "filterInnerLoops": True, "deterministicIds": ["live"]}
    response = {"result": {"$type": "ui.GBTUiGetQueryDataResponse", "queryData": [{
        "deterministicIds": ["live"], "featureId": "source_0", "selectionName": "Faces",
        "evaluationDetails": {"fullOperationId": "", "entityType": 0, "status": 0},
        "hasErrorEntity": False}]}}
    if fault == "wrong_source": query["featureId"] = "other_0"
    if fault == "wrong_form": query["filterInnerLoops"] = False
    if fault is None:
        _verify_source_region_query(response, query, "source_0")
    else:
        with pytest.raises(Unsupported):
            _verify_source_region_query(response, query, "source_0")


def _prior_sketch_intent(journal):
    key = f"{TARGET.did}/{TARGET.wid}/{TARGET.eid}"
    journal.prepare(op_id="sketch-prior", target=key, expected_revision="a" * 24,
                    action="experimental_sketch_populate", logical_id="Outline", intent={"before_state": state()})
    journal.transition("sketch-prior", "sent", receipt={"definition_candidate": True})
    journal.transition("sketch-prior", "observed", observation={"feature_id": "editorAllocated_0",
        "origin_verified": True, "constraint_graph_verified": True})


class ExtrudeBridge:
    def __init__(self, *, change_unrelated=False, wrong_region=False, old_page=False):
        self.calls = []
        self.change_unrelated = change_unrelated
        self.wrong_region = wrong_region
        self.old_page = old_page

    async def health(self):
        return {"extension_connected": True,
                "capabilities": ["h2_native_extrude_populate_server_v1", "h2_native_completion_receipt_server_v1"],
                "extension": {"capabilities": ["h2_native_extrude_populate_page_v1"] +
                              ([] if self.old_page else ["h2_native_source_region_page_v1",
                                                         "h2_native_extrude_recheck_page_v1", "h2_native_completion_receipt_page_v1"])}}

    async def command(self, job):
        self.calls.append(copy.deepcopy(job))
        if job["kind"] == "partstudio_populate_extrude":
            assert job["extrude_edit"] == {"feature_id": "freshExtrude_0", "sketch_feature_id": "editorAllocated_0",
                                            "from_mm": 25, "to_mm": 5}
            return {"op_id": job["op_id"], "definition_candidate": True, "region_source_verified": True}

        if job["kind"] == "native":
            assert job["command"] == "ui.GBTUiGetQueryDataCall"
            assert job["body"]["queries"][0]["deterministicIds"] == ["fresh-region"]
            sketch_id = "wrongSketch_0" if self.wrong_region else "editorAllocated_0"
            return {"result": {"$type": "ui.GBTUiGetQueryDataResponse", "queryData": [{
                "deterministicIds": ["fresh-region"], "featureId": sketch_id, "selectionName": "Face",
                "evaluationDetails": {"fullOperationId": f"{sketch_id}.imprint", "entityType": 2, "status": 0},
                "hasErrorEntity": False}]}}
        assert job["kind"] == "state"
        after = sum(call["kind"] == "state" for call in self.calls) > 2
        result = state(populated=True, unrelated_changed=after and self.change_unrelated)
        result["editingFeatureId"] = None if after else "freshExtrude_0"
        result["element_microversion"] = ("d" if after else "c") * 24
        depth = 5 if after else 25
        result["tree"]["children"].append({"featureId": "freshExtrude_0", "featureType": "extrude",
            "nodeId": "editor-extrude-node", "parameters": [
                {"parameterId": "bodyType", "value": "SOLID"},
                {"parameterId": "operationType", "value": "NEW"},
                {"parameterId": "endBound", "value": "BLIND"},
                {"$type": "bsedit.GBTMParameterQueryList", "parameterId": "entities",
                 "queries": [{"$type": "bsedit.GBTMIndividualQuery", "deterministicIds": ["fresh-region"]}]},
                {"$type": "bsedit.GBTMParameterQuantity", "parameterId": "depth", "nodeId": "fresh-depth-node",
                 "value": depth, "units": "millimeter", "expression": f"{depth} mm"}]})
        return result

    async def reconcile_saved_source_extrude(self, op_id, tab_id):
        assert tab_id == 17 and self.journal.get(op_id)["state"] == "sent"
        evidence = {"op_id": op_id, "feature_id": "freshExtrude_0",
                    "definition_observed": True, "solid_geometry_verified": False}
        self.journal.transition(op_id, "observed", observation=evidence)
        return {"op_id": op_id, "evidence": evidence}


@pytest.mark.asyncio
async def test_source_extrusion_journals_one_typed_depth_edit(tmp_path):
    journal = Journal(tmp_path / "intent.sqlite")
    _prior_sketch_intent(journal)
    bridge = ExtrudeBridge()
    bridge.journal = journal
    evidence = await NativeBackend(bridge, tab_id=17).populate_test_extrude(
        TARGET, SOURCE, sketch_op_id="sketch-prior", journal=journal)
    assert evidence["definition_observed"] is True and evidence["solid_geometry_verified"] is False
    assert [x["kind"] for x in bridge.calls] == ["state", "native", "state", "partstudio_populate_extrude", "state"]
    assert journal.get(evidence["op_id"])["state"] == "observed"
    journal.close()


@pytest.mark.asyncio
async def test_source_extrusion_preserves_unrelated_feature_or_stays_unknown(tmp_path):
    journal = Journal(tmp_path / "intent.sqlite")
    _prior_sketch_intent(journal)
    bridge = ExtrudeBridge(change_unrelated=True)
    with pytest.raises(UncertainWrite, match="outcome unknown"):
        await NativeBackend(bridge, tab_id=17).populate_test_extrude(
            TARGET, SOURCE, sketch_op_id="sketch-prior", journal=journal)
    assert [x["kind"] for x in bridge.calls] == ["state", "native", "state", "partstudio_populate_extrude", "state"]
    assert journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_wrong_extrusion_region_stops_before_intent_and_write(tmp_path):
    journal = Journal(tmp_path / "intent.sqlite")
    _prior_sketch_intent(journal)
    bridge = ExtrudeBridge(wrong_region=True)
    with pytest.raises(Unsupported, match="does not resolve to the source sketch"):
        await NativeBackend(bridge, tab_id=17).populate_test_extrude(
            TARGET, SOURCE, sketch_op_id="sketch-prior", journal=journal)
    assert [x["kind"] for x in bridge.calls] == ["state", "native"]
    assert not journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_old_loaded_extrusion_page_stops_before_intent(tmp_path):
    journal = Journal(tmp_path / "intent.sqlite")
    _prior_sketch_intent(journal)
    bridge = ExtrudeBridge(old_page=True)
    with pytest.raises(Unsupported, match="both advertise"):
        await NativeBackend(bridge, tab_id=17).populate_test_extrude(
            TARGET, SOURCE, sketch_op_id="sketch-prior", journal=journal)
    assert bridge.calls == [] and not journal.has_unresolved()
    journal.close()
