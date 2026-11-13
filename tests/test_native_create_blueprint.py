"""The first native target is compiled from the same FSGen semantic plan."""

import copy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.cli import main
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native import _live_rectangle_feature, stage_minimal_pair


SOURCE = Path(__file__).resolve().parents[1] / "fixtures" / "native" / "minimal_plate.fs"


def test_literal_plate_plan_normalizes_one_rectangle_and_extrusion():
    snapshot = compile_fsgen(SOURCE, Target("d", "w", "e"))
    assert [f.kind for f in snapshot.features] == ["newSketch", "extrude"]
    blueprint = stage_minimal_pair(snapshot)
    assert blueprint.sketch_logical_id == "Outline"
    assert blueprint.extrusion_logical_id == "Solid"
    assert blueprint.rectangle_m == (0.0, 0.0, 0.04, 0.02)
    assert blueprint.depth_mm == 5
    assert blueprint.to_dict()["write_ready"] is False


def test_different_plate_source_changes_native_dimensions_without_fixture_constants(tmp_path):
    source = SOURCE.read_text(encoding="utf-8")
    source = source.replace("vector(40, 20)", "vector(30, 15)").replace('"depth" : 5 * millimeter',
                                                                     '"depth" : 7 * millimeter')
    changed = tmp_path / "different_plate.fs"
    changed.write_text(source, encoding="utf-8")
    blueprint = stage_minimal_pair(compile_fsgen(changed, Target("d", "w", "e")))
    assert blueprint.rectangle_m == (0.0, 0.0, .03, .015)
    assert blueprint.depth_mm == 7


def test_blueprint_cli_uses_same_fsgen_source_without_browser(capsys):
    assert main(["native-blueprint", str(SOURCE), "--did", "d", "--wid", "w", "--eid", "e"]) == 0
    import json
    output = json.loads(capsys.readouterr().out)
    assert output["depth_mm"] == 5
    assert output["rectangle_m"] == [0, 0, .04, .02]
    assert not output["write_ready"]


def test_active_native_rectangle_endpoints_match_fsgen_plan():
    blueprint = stage_minimal_pair(compile_fsgen(SOURCE, Target("d", "w", "e")))
    lines = [("bottom", .02, 0, 1, 0, -.02, .02),
             ("right", .04, .01, 0, 1, -.01, .01),
             ("top", .02, .02, 1, 0, -.02, .02),
             ("left", 0, .01, 0, 1, -.01, .01)]
    entities = [{"$type": "bsedit.GBTMSketchCurveSegment", "entityId": "fresh." + side,
                 "isConstruction": False, "startParam": start, "endParam": end,
                 "geometry": {"$type": "bsedit.GBTCurveGeometryLine", "pntX": px,
                              "pntY": py, "dirX": dx, "dirY": dy}}
                for side, px, py, dx, dy, start, end in lines]
    feature = {"featureId": "fresh-sketch", "featureType": "newSketch", "nodeId": "fresh-node",
               "entities": entities, "parameters": [{"$type": "bsedit.GBTMParameterQueryList",
                 "parameterId": "sketchPlane", "queries": [{"$type": "bsedit.GBTMIndividualQuery",
                 "deterministicIds": ["live-top"]}]}]}
    state = {"connected": True, "editingFeatureId": "fresh-sketch",
             "tree": {"$type": "bsedit.GBTMModel", "children": [feature]}}
    assert _live_rectangle_feature(state, blueprint) is feature
    entities[1]["endParam"] = .0102
    with pytest.raises(Unsupported, match="endpoints"):
        _live_rectangle_feature(state, blueprint)


@pytest.mark.parametrize("mutation", [
    lambda x: x.features[0].structure["sketch"].update(plane_name="Front"),
    lambda x: x.features[1].parameters.update(depth="#thickness"),
    lambda x: x.features[1].parameters.update(operationType="REMOVE"),
    lambda x: x.features[1].parameters.update(entities=["query=qSketchRegion(makeId(\"Other\"));"]),
    lambda x: x.features[0].structure["sketch"]["rectangle"].update(construction=True),
    lambda x: x.features[0].structure.update(parameter_schema=None),
    lambda x: x.features[0].structure["fsgen_native"].update(entities="oops"),
    lambda x: x.features[0].structure["fsgen_native"]["entities"][0].update(endParam=.05),
    lambda x: x.features[0].structure["fsgen_native"]["entities"][1]["geometry"].update(dirY=-1),
    lambda x: x.features[0].structure["fsgen_native"]["constraints"][0]["parameters"][1].update(value="box.top.end"),
    lambda x: x.features[0].structure["fsgen_native"]["constraints"][-1]["parameters"][-1].update(expression="21 mm"),
    lambda x: x.features[0].structure["fsgen_native"]["constraints"].append({"constraintType": "TANGENT"}),
    lambda x: x.features[0].structure["fsgen_native"]["constraints"][1].update(entityId="co_box.bottom.start_box.left.end"),
])
def test_unsupported_or_diverged_plan_stops_before_native_compilation(mutation):
    snapshot = copy.deepcopy(compile_fsgen(SOURCE, Target("d", "w", "e")))
    mutation(snapshot)
    with pytest.raises(Unsupported):
        stage_minimal_pair(snapshot)
