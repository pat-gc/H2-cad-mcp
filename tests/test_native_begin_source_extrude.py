"""The editor must allocate an Extrude bound to the one saved FSGen rectangle."""

import copy
import json
from pathlib import Path

import pytest

from h2cad.journal import Journal
from h2cad.model import Target
from h2cad.native import NativeBackend
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
