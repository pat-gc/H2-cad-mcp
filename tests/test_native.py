import json

import httpx
import pytest

from h2cad.backend import Unsupported
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
