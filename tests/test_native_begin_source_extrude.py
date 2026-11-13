"""The editor must allocate an Extrude bound to the one saved FSGen rectangle."""

import copy
import json
from pathlib import Path

import pytest
import httpx

from h2cad.journal import Journal
from h2cad.model import Target
from h2cad.native import NativeBackend, NativeBridge, PreDispatchRejected
from h2cad.cli import build_parser


ROOT = next((parent for parent in Path(__file__).resolve().parents
             if (parent / "artifacts/native-fixed-origin-trial/patch16-post-ui-save.json").is_file()), None)
assert ROOT is not None, "Committed native evidence fixture is missing"
SOURCE = Path(__file__).resolve().parents[1] / "fixtures/native/minimal_plate.fs"
TARGET = Target("4e078dec822b4e509616b1cb", "af0627de07264acf086e646a",
                "1926791d173990d5d45f70ef")


def fixture(name):
    return json.loads((ROOT / name).read_text(encoding="cp1252"))


@pytest.mark.asyncio
async def test_begin_extrude_uses_saved_source_and_independent_active_tree(tmp_path):
    before = fixture("artifacts/native-fixed-origin-trial/patch16-post-ui-save.json")
    after = fixture("artifacts/native-source-edit-extrude/patch18-active-extrude.json")
    before["target"] = after["target"] = {"did": TARGET.did, "wid": TARGET.wid, "eid": TARGET.eid}
    after["tree"]["children"][0] = copy.deepcopy(before["tree"]["children"][0])
    source_query = {"$type": "bsedit.GBTMIndividualSketchRegionQuery", "featureId":
                    before["tree"]["children"][0]["featureId"], "filterInnerLoops": True,
                    "deterministicIds": ["editor-bound"]}
    feature = after["tree"]["children"][1]
    next(p for p in feature["parameters"] if p.get("parameterId") == "entities")["queries"] = [source_query]
    after["element_microversion"] = "b" * 24
    before["element_microversion"] = "a" * 24

    class Bridge:
        create_target = {"did": TARGET.did, "wid": TARGET.wid, "eid": TARGET.eid}
        def __init__(self): self.calls = []
        async def health(self):
            return {"extension_connected": True, "capabilities": ["h2_native_begin_source_extrude_server_v1"],
                    "extension": {"capabilities": ["h2_native_begin_source_extrude_page_v1"]}}
        async def command(self, job):
            self.calls.append(copy.deepcopy(job))
            if job["kind"] == "state":
                return copy.deepcopy(before if len(self.calls) == 1 else after)
            if job["kind"] == "native":
                assert job["body"]["queries"] == [source_query]
                return {"result": {"$type": "ui.GBTUiGetQueryDataResponse", "queryData": [{
                    "deterministicIds": ["editor-bound"], "featureId": sketch_id,
                    "selectionName": "Faces", "hasErrorEntity": False,
                    "evaluationDetails": {"status": 0, "entityType": 0, "fullOperationId": ""}}]}}
            assert job["kind"] == "partstudio_begin_source_extrude"
            assert job["sketch_feature_id"] == before["tree"]["children"][0]["featureId"]
            return {"op_id": job["op_id"], "initiation_candidate": True, "region_source_verified": True,
                    "feature_id": feature["featureId"], "feature_node_id": feature["nodeId"],
                    "region_query_ids": source_query["deterministicIds"]}

    bridge = Bridge()
    journal = Journal(tmp_path / "intent.sqlite")
    sketch_id = before["tree"]["children"][0]["featureId"]
    journal.prepare(op_id="sketch-" + "a" * 32, target=f"{TARGET.did}/{TARGET.wid}/{TARGET.eid}",
                    expected_revision="0" * 24, action="experimental_sketch_populate",
                    logical_id="Outline", intent={"feature_id": sketch_id})
    journal.transition("sketch-" + "a" * 32, "sent", receipt={"op_id": "sketch-" + "a" * 32})
    journal.transition("sketch-" + "a" * 32, "observed", observation={"feature_id": sketch_id,
                       "origin_verified": True, "constraint_graph_verified": True})
    result = await NativeBackend(bridge, tab_id=17).begin_test_source_extrude(
        TARGET, SOURCE, sketch_op_id="sketch-" + "a" * 32, journal=journal)
    assert result["region_source_verified"] is True
    assert result["feature_id"] == feature["featureId"]
    assert [call["kind"] for call in bridge.calls] == ["state", "partstudio_begin_source_extrude", "state", "native", "state"]
    assert journal.get(result["op_id"])["state"] == "observed"
    journal.close()


def test_cli_exposes_one_source_driven_plate_command():
    args = build_parser().parse_args(["experimental-create-plate", str(SOURCE),
                                      "--did", TARGET.did, "--wid", TARGET.wid, "--eid", TARGET.eid,
                                      "--bridge-config", "bridge.json", "--tab-id", "17",
                                      "--journal", "intent.sqlite"])
    assert args.command == "experimental-create-plate"
    assert args.source == SOURCE and args.tab_id == 17


@pytest.mark.asyncio
async def test_create_plate_cli_validates_then_routes_each_editor_stage_once(tmp_path, monkeypatch):
    import h2cad.cli as cli
    calls = []
    class Bridge:
        async def close(self): pass
    class Backend:
        def __init__(self, bridge, *, tab_id):
            assert isinstance(bridge, Bridge) and tab_id == 17
        async def begin_test_top_sketch(self, target, journal):
            calls.append(("begin_top", target))
            return {"op_id": "begin-sketch-1"}
        async def populate_test_sketch(self, target, source, journal):
            calls.append(("populate_sketch", target))
            assert source == SOURCE.read_text(encoding="utf-8")
            return {"op_id": "sketch-1"}
        async def begin_test_source_extrude(self, target, source, *, sketch_op_id, journal):
            calls.append(("begin_extrude", target))
            assert sketch_op_id == "sketch-1" and source == SOURCE.read_text(encoding="utf-8")
            return {"op_id": "begin-extrude-1"}
        async def populate_test_extrude(self, target, source, *, sketch_op_id, journal):
            calls.append(("populate_extrude", target))
            assert sketch_op_id == "sketch-1" and source == SOURCE.read_text(encoding="utf-8")
            return {"op_id": "extrude-1", "definition_observed": True}
    monkeypatch.setattr(cli.NativeBridge, "from_config", classmethod(lambda cls, path: Bridge()))
    monkeypatch.setattr(cli, "NativeBackend", Backend)
    journal = tmp_path / "intent.sqlite"
    config = tmp_path / "bridge.json"
    config.write_text(json.dumps({"h2cad_journal": str(journal)}), encoding="utf-8")
    args = build_parser().parse_args(["experimental-create-plate", str(SOURCE),
                                      "--did", TARGET.did, "--wid", TARGET.wid, "--eid", TARGET.eid,
                                      "--bridge-config", str(config), "--tab-id", "17",
                                      "--journal", str(journal)])
    result, status = await cli._bridge_action(args)
    assert status == 0 and result["status"] == "native_definitions_observed"
    assert result["local_validation"]["status"] == "passed"
    assert result["solid_geometry_verified"] is False
    assert [step for step, target in calls] == ["begin_top", "populate_sketch", "begin_extrude", "populate_extrude"]
    assert all(target == TARGET for _, target in calls)


@pytest.mark.asyncio
async def test_begin_source_job_reaches_authenticated_bridge_and_preserves_pre_dispatch_rejection():
    sent = []
    def reply(request):
        sent.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"error": "Editor not ready", "write_stage": "pre_dispatch"})
    bridge = NativeBridge("x" * 32, transport=httpx.MockTransport(reply))
    job = {"kind": "partstudio_begin_source_extrude", "op_id": "begin-extrude-" + "a" * 32,
           "target": TARGET.to_dict(), "tab_id": 17,
           "expected_element_microversion": "a" * 24,
           "sketch_feature_id": "savedSketch_0"}
    try:
        with pytest.raises(PreDispatchRejected, match="Editor not ready"):
            await bridge.command(job)
    finally:
        await bridge.close()
    assert sent == [("/command", job)]
