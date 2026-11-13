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
        origin = c("firstSnap0", 1, "bottom.start")
        origin["parameters"].append({"$type": "bsedit.GBTMParameterQueryList", "parameterId": "externalSecond",
                                     "queries": [{"$type": "bsedit.GBTMIndividualQuery", "deterministicIds": []}]})
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
    ids = ("firstSnap0", "perpendicular", "parallel.1", "parallel.2", "horizontal",
           "corner0", "corner1", "corner2", "corner3", "width", "height")
    constraints = {"box." + name: {"status": 4, "displayStatus": 1} for name in ids}
    constraints["box.firstSnap0"].update(isExternal=True, type=1, referenceIds="box.bottom.start origin-ref")
    return {"result": {"$type": "ui.sketch.GBTUiSketchGetConstraintGraphResponse",
                       "constraints": constraints, "worstSolveStatus": 1,
                       "sketchError": {"statusEnum": 0},
                       "references": {"origin-ref": {"isSketchEntity": False,
                                                       "anchorX": 0, "anchorY": 0, "anchorZ": 0},
                                      "box.bottom.start": {"worstSolveStatus": 1,
                                                           "anchorX": 0, "anchorY": 0, "anchorZ": 0}}}}


class Bridge:
    def __init__(self, *, changed=False, capabilities=True, unanchored=False, pre_dispatch=False):
        self.calls = []
        self.changed = changed
        self.capabilities = capabilities
        self.unanchored = unanchored
        self.pre_dispatch = pre_dispatch

    async def health(self):
        return {"extension_connected": True,
                "capabilities": ["h2_native_sketch_populate_server_v1"] if self.capabilities else [],
                "extension": {"capabilities": ["h2_native_sketch_populate_page_v1"]}}

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
                graph["result"]["constraints"]["box.firstSnap0"]["referenceIds"] = "box.bottom.start unknown"
            return graph
        assert job["kind"] == "partstudio_populate_sketch"
        assert job["sketch_edit"] == {"feature_id": "editorAllocated_0", "entity_prefix": "box",
                                      "rectangle_m": [0.0, 0.0, 0.04, 0.02]}
        if self.pre_dispatch:
            raise PreDispatchRejected("Invalid native field.")
        return {"definition_candidate": True}


@pytest.mark.asyncio
async def test_source_pair_journals_one_write_and_verifies_native_definition(tmp_path):
    bridge = Bridge()
    journal = Journal(tmp_path / "intent.sqlite")
    evidence = await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert evidence["definition_observed"] is True and evidence["origin_verified"] is True
    assert evidence["geometry_verified"] is False
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch", "state", "native"]
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
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch", "state", "native"]
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
    after = state(populated=True)
    after["element_microversion"] = "97955554c86d659d57a74a68"
    after["editingFeatureId"] = editing
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
    def __init__(self, *, altered=False):
        self.calls = []
        self.altered = altered

    async def health(self):
        return {"extension_connected": True, "capabilities": ["h2_native_begin_top_sketch_server_v1"],
                "extension": {"capabilities": ["h2_native_begin_top_sketch_page_v1"]}}

    async def command(self, job):
        self.calls.append(copy.deepcopy(job))
        if job["kind"] == "partstudio_begin_top_sketch":
            return {"initiation_candidate": True, "feature_id": "newSketch_0", "feature_node_id": "fresh-node",
                    "plane_query_ids": ["bound-top"]}
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
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_begin_top_sketch", "state"]
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


def _prior_sketch_intent(journal):
    key = f"{TARGET.did}/{TARGET.wid}/{TARGET.eid}"
    journal.prepare(op_id="sketch-prior", target=key, expected_revision="a" * 24,
                    action="experimental_sketch_populate", logical_id="Outline", intent={"before_state": state()})
    journal.transition("sketch-prior", "sent", receipt={"definition_candidate": True})
    journal.transition("sketch-prior", "observed", observation={"feature_id": "editorAllocated_0",
        "origin_verified": True, "constraint_graph_verified": True})


class ExtrudeBridge:
    def __init__(self, *, change_unrelated=False):
        self.calls = []
        self.change_unrelated = change_unrelated

    async def health(self):
        return {"extension_connected": True,
                "capabilities": ["h2_native_extrude_populate_server_v1"],
                "extension": {"capabilities": ["h2_native_extrude_populate_page_v1"]}}

    async def command(self, job):
        self.calls.append(copy.deepcopy(job))
        if job["kind"] == "partstudio_populate_extrude":
            assert job["extrude_edit"] == {"feature_id": "freshExtrude_0", "sketch_feature_id": "editorAllocated_0",
                                            "from_mm": 25, "to_mm": 5}
            return {"definition_candidate": True}
        assert job["kind"] == "state"
        after = len(self.calls) > 1
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


@pytest.mark.asyncio
async def test_source_extrusion_journals_one_typed_depth_edit(tmp_path):
    journal = Journal(tmp_path / "intent.sqlite")
    _prior_sketch_intent(journal)
    bridge = ExtrudeBridge()
    evidence = await NativeBackend(bridge, tab_id=17).populate_test_extrude(
        TARGET, SOURCE, sketch_op_id="sketch-prior", journal=journal)
    assert evidence["definition_observed"] is True and evidence["solid_geometry_verified"] is False
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_extrude", "state"]
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
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_extrude", "state"]
    assert journal.has_unresolved()
    journal.close()
