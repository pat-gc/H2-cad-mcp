import copy
import json
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native_extrusions import map_source_extrusion, stage_source_extrusion

ROOT = Path(__file__).resolve().parents[1]
TARGET = Target("a" * 24, "b" * 24, "c" * 24)


def source():
    features = compile_fsgen(ROOT / "fixtures/car/basic_car.fs", TARGET).features
    return [f for f in features if f.kind == "extrude"], [f for f in features if f.kind == "assignVariable"]


def state():
    draft = json.loads((ROOT / "tests/fixtures/native_extrude_default.json").read_text())
    sketch = {"featureId": "sourceSketch_0", "featureType": "newSketch", "nodeId": "saved-sketch",
              "entities": [{"entityId": "front", "geometry": {"radius": .014}},
                           {"entityId": "rear", "geometry": {"radius": .014}}]}
    tree = {"$type": "bsedit.GBTMModel", "children": [
        {"featureId": "variable_0", "featureType": "assignVariable", "nodeId": "prior-variable"},
        {"featureId": "otherSketch_0", "featureType": "newSketch", "nodeId": "prior-sketch"},
        {"featureId": "otherExtrude_0", "featureType": "extrude", "nodeId": "prior-extrude"},
        sketch, draft, {"$type": "bsedit.GBTMRollback", "nodeId": "rollback"}]}
    query = next(p for p in draft["parameters"] if p["parameterId"] == "entities")["queries"][0]
    readback = {"result": {"$type": "ui.GBTUiGetQueryDataResponse", "queryData": [{
        "deterministicIds": query["deterministicIds"], "featureId": "sourceSketch_0", "selectionName": "Faces",
        "evaluationDetails": {"status": 0, "entityType": 0, "fullOperationId": ""}, "hasErrorEntity": False}]}}
    return {"target": dict(did=TARGET.did, wid=TARGET.wid, eid=TARGET.eid), "tree": tree,
            "editingFeatureId": "freshExtrude_0", "connected": True, "element_microversion": "d" * 24}, sketch, readback


def test_all_five_car_depths_keep_exact_source_expressions():
    extrudes, variables = source()
    plans = [stage_source_extrusion(f, variables) for f in extrudes]
    assert [p["depth_expression"] for p in plans] == ["8 mm", "#bodyHeight", "110 mm", "#wheelThickness", "#wheelThickness"]
    assert [p["depth_seed_mm"] for p in plans] == [8, 37, 110, 12, 12]
    assert all(not p["regeneration_verified"] for p in plans)


def test_expression_mapping_preserves_interleaved_features_and_multi_circle_source():
    extrudes, variables = source()
    before, sketch, query = state()
    original = copy.deepcopy(before)
    result = map_source_extrusion(before, extrudes[3], target=TARGET, sketch_feature_id="sourceSketch_0",
                                  sketch_definition=copy.deepcopy(sketch), query_response=query, variables=variables)
    assert before == original
    expected = copy.deepcopy(before["tree"])
    depth = next(p for p in expected["children"][-2]["parameters"] if p["parameterId"] == "depth")
    depth.update(expression="#wheelThickness", value=12)
    assert result["expected_tree"] == expected
    assert result["source_region_verified"] is True
    assert result["region_count_verified"] is False
    assert result["ready_to_submit"] is False


@pytest.mark.parametrize("fault", ["target", "source_sketch", "query_feature", "query_error", "single_face", "mode", "depth_unit", "duplicate_sketch"])
def test_wrong_binding_or_native_definition_fails_closed(fault):
    extrudes, variables = source()
    before, sketch, query = state()
    authoritative = copy.deepcopy(sketch)
    params = {p["parameterId"]: p for p in before["tree"]["children"][-2]["parameters"]}
    if fault == "target": before["target"]["eid"] = "f" * 24
    if fault == "source_sketch": sketch["nodeId"] = "changed"
    if fault == "query_feature": query["result"]["queryData"][0]["featureId"] = "otherSketch_0"
    if fault == "query_error": query["result"]["queryData"][0]["evaluationDetails"]["status"] = 1
    if fault == "single_face": params["entities"]["queries"][0]["$type"] = "bsedit.GBTMIndividualQuery"
    if fault == "mode": params["operationType"]["value"] = "ADD"
    if fault == "depth_unit": params["depth"]["units"] = "meter"
    if fault == "duplicate_sketch": before["tree"]["children"].append(copy.deepcopy(sketch))
    with pytest.raises(Unsupported):
        map_source_extrusion(before, extrudes[3], target=TARGET, sketch_feature_id="sourceSketch_0",
                             sketch_definition=authoritative, query_response=query, variables=variables)


def test_source_tampering_missing_variable_and_extra_dependency_rejected():
    extrudes, variables = source()
    modified = copy.deepcopy(extrudes[1])
    modified.parameters["depth"] = "999 mm"
    with pytest.raises(Unsupported, match="projection"):
        stage_source_extrusion(modified, variables)
    with pytest.raises(Unsupported, match="source length variable"):
        stage_source_extrusion(extrudes[1])
    modified = copy.deepcopy(extrudes[1])
    modified.dependencies = (*modified.dependencies, "unrelated")
    with pytest.raises(Unsupported, match="dependency"):
        stage_source_extrusion(modified, variables)
