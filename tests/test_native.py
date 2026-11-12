import json
import copy

import httpx
import pytest

from h2cad.backend import Unsupported, UncertainWrite
from h2cad.journal import Journal
from h2cad.model import Feature, Target
from h2cad.native import NativeBackend, NativeBridge, stage_extrusion, stage_rectangle


T = Target("a" * 24, "b" * 24, "c" * 24)
E = "d" * 24


@pytest.mark.asyncio
async def test_bridge_uses_only_native_command_channel_and_rejects_rest():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        assert request.url.host == "127.0.0.1"
        assert request.headers["authorization"] == "Bearer " + "x" * 32
        if request.url.path == "/health":
            return httpx.Response(200, json={"protocol": 1, "extension_connected": True,
                                             "extension": {"version": "test", "capabilities": ["element_revision_v1"]}})
        assert request.url.path == "/command"
        job = json.loads(request.content)
        assert job["kind"] in {"state", "schema", "native"}
        return httpx.Response(200, json={"target": job["target"], "element_microversion": E, "tree": {"children": []}})

    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(handler))
    backend = NativeBackend(bridge, tab_id=12)
    caps = await backend.capabilities()
    assert not caps.atomic_revision and not caps.supported_kinds
    state = await backend.read(T)
    assert state.revision == E and not state.complete
    assert seen[-1][2]["tab_id"] == 12
    with pytest.raises(Unsupported, match="only native"):
        await bridge.command({"kind": "rest", "method": "POST", "path": "/api/partstudios"})
    assert all(path != "/api/partstudios" for _, path, _ in seen)
    await bridge.close()


@pytest.mark.asyncio
async def test_modeling_probe_reads_runtime_evidence_without_writes():
    jobs = []

    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"protocol": 1, "extension_connected": True,
                                             "extension": {"capabilities": ["native_modeling_v1"]}})
        assert request.url.path == "/command"
        job = json.loads(request.content)
        jobs.append(job)
        if job["kind"] == "state":
            return httpx.Response(200, json={"target": job["target"], "element_microversion": E,
                                             "connected": True, "editingFeatureId": None,
                                             "tree": {"$type": "bsedit.GBTMModel"},
                                             "h2Readback": {"contract": "h2-readback-probe-v1", "complete": False}})
        if job["kind"] == "schema":
            return httpx.Response(200, json={"name": job["name"], "defaults": {"elementId": ""}})
        assert job["command"] == "ui.GBTUiGetFeatureSettingsCall"
        return httpx.Response(200, json={"result": {"featureKey": job["body"]["featureKey"]}})

    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(handler))
    probe = await NativeBackend(bridge).modeling_probe(T)
    assert probe["write_ready"] is False
    assert probe["tree_type"] == "bsedit.GBTMModel"
    assert len(jobs) == 7
    assert {job["kind"] for job in jobs} == {"state", "schema", "native"}
    assert all(job.get("command") == "ui.GBTUiGetFeatureSettingsCall" for job in jobs if job["kind"] == "native")
    await bridge.close()


def test_rectangle_compiles_only_with_runtime_schema_and_live_bindings():
    feature = Feature("s", "sketch", {}, structure={"sketch": {"rectangle":
                      {"x0": 0.0, "y0": 0.0, "x1": .04, "y1": .02}}})
    schema = {"name": "ui.sketch.GBTUiSketchAddRectangleCall", "defaults":
              dict.fromkeys(["firstX", "firstY", "oppositeX", "oppositeY", "sketchEntityId",
                             "inferenceSetId", "isConstruction"], None)}
    bindings = {"provenance": "live_editor", "sketch_feature_id": "fresh-sketch",
                "sketch_entity_id": "fresh-entity", "inference_set_id": "fresh-inference",
                "element_microversion": E}
    staged = stage_rectangle(feature, bindings=bindings, schema=schema)
    assert staged.command == schema["name"]
    assert staged.body["oppositeX"] == .04
    assert staged.body["sketchEntityId"] == "fresh-entity"
    with pytest.raises(Unsupported, match="live editor"):
        stage_rectangle(feature, bindings={**bindings, "provenance": "capture"}, schema=schema)
    with pytest.raises(Unsupported, match="serializer lacks"):
        stage_rectangle(feature, bindings=bindings, schema={**schema, "defaults": {}})


def test_extrusion_stage_reports_missing_runtime_bindings():
    feature = Feature("x", "extrude", {"depth": "12 mm"}, dependencies=("s",))
    stage = stage_extrusion(feature, bindings={}, schema={"name": "ui.GBTUiAddFeatureCall",
                                                   "defaults": dict.fromkeys(["newFeature", "editDescription", "rollbackState"])})
    assert stage["depth"] == "12 mm"
    assert "sketch_region_query" in stage["missing_live_bindings"]
    assert not stage["ready_to_submit"]


@pytest.mark.asyncio
async def test_disposable_depth_edit_journals_and_verifies_exact_tree(tmp_path):
    target = Target("f5a8353dc826a9ec52106138", "a3baadfcc7e36a50134951d6", "a2761fa52794bee99354ae96")
    tree = {"$type": "bsedit.GBTMModel", "children": [
        {"featureId": "sketch-id", "featureType": "newSketch", "nodeId": "sketch-node", "name": "Sketch 1"},
        {"featureId": "extrude-id", "featureType": "extrude", "nodeId": "extrude-node", "name": "Extrude 1",
         "parameters": [{"parameterId": "bodyType", "value": "SOLID"},
                        {"parameterId": "operationType", "value": "NEW"},
                        {"parameterId": "endBound", "value": "BLIND"},
                        {"parameterId": "entities", "queries": [{"deterministicIds": ["opaque"]}]},
                        {"$type": "bsedit.GBTMParameterQuantity", "parameterId": "depth", "nodeId": "depth-node",
                         "expression": "25 mm", "value": 25, "units": "millimeter"}]},
        {"nodeId": "rollback", "name": "Rollback bar"}]}
    current = copy.deepcopy(tree)
    jobs = []

    def handler(request):
        job = json.loads(request.content)
        jobs.append(job)
        if job["kind"] == "state":
            return httpx.Response(200, json={"target": target.to_dict(), "tree": copy.deepcopy(current),
                "connected": True, "editingFeatureId": None, "element_microversion": "b" * 24 if len(jobs) > 2 else "a" * 24,
                "h2Readback": {"contract": "h2-readback-probe-v1", "complete": False}})
        assert job["kind"] == "partstudio_depth_edit"
        assert job["expected_element_microversion"] == "a" * 24
        assert job["depth_edit"] == {"feature_id": "extrude-id", "from_mm": 25, "to_mm": 5}
        current["children"][1]["parameters"][-1].update(expression="5 mm", value=5)
        return httpx.Response(200, json={"definition_verified": True})

    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(handler))
    journal = Journal(tmp_path / "journal.sqlite")
    result = await NativeBackend(bridge, tab_id=7).edit_disposable_extrude_depth(
        target, feature_id="extrude-id", from_mm=25, to_mm=5, journal=journal)
    assert result["definition_verified"] and not result["geometry_verified"]
    assert len(jobs) == 3 and all(job["tab_id"] == 7 for job in jobs)
    rows = journal._db.execute("SELECT state FROM writes").fetchall()
    assert [row[0] for row in rows] == ["observed"]
    journal.close()
    await bridge.close()


@pytest.mark.asyncio
async def test_depth_edit_marks_unrelated_change_unknown_and_never_retries(tmp_path):
    target = Target("f5a8353dc826a9ec52106138", "a3baadfcc7e36a50134951d6", "a2761fa52794bee99354ae96")
    tree = {"$type": "bsedit.GBTMModel", "children": [
        {"featureId": "extrude-id", "featureType": "extrude", "nodeId": "extrude-node", "parameters": [
            {"parameterId": "bodyType", "value": "SOLID"}, {"parameterId": "operationType", "value": "NEW"},
            {"parameterId": "endBound", "value": "BLIND"},
            {"$type": "bsedit.GBTMParameterQuantity", "parameterId": "depth", "nodeId": "depth-node",
             "expression": "25 mm", "value": 25, "units": "millimeter"}]},
        {"featureId": "human-id", "featureType": "newSketch", "name": "Human sketch"}]}
    calls = []

    def handler(request):
        job = json.loads(request.content)
        calls.append(job["kind"])
        if job["kind"] == "partstudio_depth_edit":
            tree["children"][0]["parameters"][-1].update(expression="5 mm", value=5)
            tree["children"][1]["name"] = "Unexpected edit"
            return httpx.Response(200, json={"definition_verified": True})
        return httpx.Response(200, json={"target": target.to_dict(), "tree": tree,
            "connected": True, "editingFeatureId": None,
            "element_microversion": ("b" if len(calls) > 2 else "a") * 24,
            "h2Readback": {"contract": "h2-readback-probe-v1"}})

    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(handler))
    journal = Journal(tmp_path / "journal.sqlite")
    backend = NativeBackend(bridge)
    with pytest.raises(UncertainWrite, match="outcome unknown"):
        await backend.edit_disposable_extrude_depth(target, feature_id="extrude-id", from_mm=25, to_mm=5, journal=journal)
    assert journal.unresolved(f"{target.did}/{target.wid}/{target.eid}")[0]["state"] == "unknown"
    with pytest.raises(UncertainWrite, match="Prior target write unresolved"):
        await backend.edit_disposable_extrude_depth(target, feature_id="extrude-id", from_mm=25, to_mm=5, journal=journal)
    assert calls == ["state", "partstudio_depth_edit", "state"]
    journal.close()
    await bridge.close()
