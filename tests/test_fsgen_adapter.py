from pathlib import Path

import pytest

from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.validation import validate_fsgen


SOURCE = '''FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");
export function build(context is Context, id is Id)
{
    var s = newSketch(context, id + "Outline", { "sketchPlane" : qCreatedBy(makeId("Top"), EntityType.FACE) });
    skRectangle(s, "box", { "firstCorner" : vector(0, 0) * millimeter,
                            "secondCorner" : vector(40, 20) * millimeter });
    skSolve(s);
    extrude(context, id + "Solid", { "entities" : qSketchRegion(id + "Outline"),
        "endBound" : BoundingType.BLIND, "depth" : 5 * millimeter });
}
'''


def test_fsgen_rectangle_extrude_compiles_to_semantic_graph():
    snapshot = compile_fsgen(SOURCE, Target("d", "w", "e"))
    sketch, extrude = snapshot.features
    assert sketch.kind == "newSketch"
    assert sketch.structure["sketch"]["rectangle"] == {
        "x0": 0.0, "y0": 0.0, "x1": 0.04, "y1": 0.02, "construction": False}
    assert extrude.dependencies == ("Outline",)
    assert extrude.parameters["depth"] == "5 mm"
    assert "fsgen_feature_json" in sketch.structure


def test_fsgen_local_occ_full_geometry():
    report = validate_fsgen(SOURCE)
    assert report.status == "passed", report.to_dict()
    assert report.geometry["parts"] == 1
    assert report.geometry["volume_mm3"] == pytest.approx(4000, rel=1e-6)
    assert report.remote == "not_run" and report.native_editability == "not_run"


def test_upstream_plate_local_occ_matches_recorded_volume():
    path = Path(__file__).resolve().parents[3] / "upstream" / "onshape-fsgen" / "examples" / "native" / "plate.fs"
    if not path.exists():
        pytest.skip("separate pinned upstream checkout unavailable")
    report = validate_fsgen(path)
    assert report.status == "passed", report.to_dict()
    assert report.geometry["volume_mm3"] == pytest.approx(23244.385, rel=1e-5)
