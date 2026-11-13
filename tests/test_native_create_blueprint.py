"""The first native target is compiled from the same FSGen semantic plan."""

import copy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.cli import main
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native import stage_minimal_pair


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


def test_blueprint_cli_uses_same_fsgen_source_without_browser(capsys):
    assert main(["native-blueprint", str(SOURCE), "--did", "d", "--wid", "w", "--eid", "e"]) == 0
    import json
    output = json.loads(capsys.readouterr().out)
    assert output["depth_mm"] == 5
    assert output["rectangle_m"] == [0, 0, .04, .02]
    assert not output["write_ready"]


@pytest.mark.parametrize("mutation", [
    lambda x: x.features[0].structure["sketch"].update(plane_name="Front"),
    lambda x: x.features[1].parameters.update(depth="#thickness"),
    lambda x: x.features[1].parameters.update(operationType="REMOVE"),
    lambda x: x.features[1].parameters.update(entities=["query=qSketchRegion(makeId(\"Other\"));"]),
    lambda x: x.features[0].structure["sketch"]["rectangle"].update(construction=True),
])
def test_unsupported_or_diverged_plan_stops_before_native_compilation(mutation):
    snapshot = copy.deepcopy(compile_fsgen(SOURCE, Target("d", "w", "e")))
    mutation(snapshot)
    with pytest.raises(Unsupported):
        stage_minimal_pair(snapshot)
