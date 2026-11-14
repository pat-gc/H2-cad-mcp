from pathlib import Path

import pytest

from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.planner import plan_changes
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


def upstream_plate() -> Path | None:
    here = Path(__file__).resolve()
    return next((parent / "upstream" / "onshape-fsgen" / "examples" / "native" / "plate.fs"
                 for parent in here.parents
                 if (parent / "upstream" / "onshape-fsgen" / "examples" / "native" / "plate.fs").exists()), None)


def test_fsgen_rectangle_extrude_compiles_to_semantic_graph():
    snapshot = compile_fsgen(SOURCE, Target("d", "w", "e"))
    sketch, extrude = snapshot.features
    assert sketch.kind == "newSketch"
    assert sketch.structure["sketch"]["rectangle"] == {
        "x0": 0.0, "y0": 0.0, "x1": 0.04, "y1": 0.02, "construction": False}
    assert extrude.dependencies == ("Outline",)
    assert extrude.parameters["depth"] == "5 mm"
    assert "fsgen_feature_json" in sketch.provenance


def test_fsgen_local_occ_full_geometry():
    report = validate_fsgen(SOURCE)
    assert report.status == "passed", report.to_dict()
    assert report.geometry["parts"] == 1
    assert report.geometry["volume_mm3"] == pytest.approx(4000, rel=1e-6)
    assert report.remote == "not_run" and report.native_editability == "not_run"


def test_upstream_plate_local_occ_matches_recorded_volume():
    path = upstream_plate()
    if path is None:
        pytest.skip("separate pinned upstream checkout unavailable")
    report = validate_fsgen(path)
    assert report.status == "passed", report.to_dict()
    assert report.geometry["volume_mm3"] == pytest.approx(23244.385, rel=1e-5)


def test_real_plate_variable_edit_plans_parameter_update_without_structure_conflict():
    path = upstream_plate()
    if path is None:
        pytest.skip("separate pinned upstream checkout unavailable")
    source = path.read_text()
    base = compile_fsgen(source, Target("d", "w", "e"), "r1")
    desired = compile_fsgen(source.replace('"thickness", 6 * millimeter',
                                           '"thickness", 7 * millimeter'), Target("d", "w", "e"), "r1")
    assert [f.logical_id for f in base.features[:5]] == [
        "#width", "#depth", "#thickness", "#holeDiameter", "#holeInset"]
    assert "#thickness" in next(f for f in base.features if f.logical_id == "Plate").dependencies
    plan = plan_changes(base, base, desired)
    assert not plan.conflicts, [c.to_dict() for c in plan.conflicts]
    assert [op.logical_id for op in plan.operations] == ["#thickness"]
    assert plan.merged.features[2].parameters["lengthValue"] == "7 mm"


def test_circle_entity_and_constraint_changes_are_not_invisible():
    circle = SOURCE.replace('skRectangle(s, "box", { "firstCorner" : vector(0, 0) * millimeter,\n'
                            '                            "secondCorner" : vector(40, 20) * millimeter });',
                            'skCircle(s, "rim", { "center" : vector(0, 0) * millimeter, '
                            '"radius" : 4 * millimeter });')
    assert "skCircle" in circle and "skRectangle" not in circle
    base = compile_fsgen(circle, Target("d", "w", "e"), "r1")
    changed = compile_fsgen(circle.replace('"radius" : 4 * millimeter',
                                           '"radius" : 5 * millimeter'), Target("d", "w", "e"), "r1")
    before = base.features[0].structure["fsgen_native"]
    after = changed.features[0].structure["fsgen_native"]
    assert before["entities"] == after["entities"]  # both radii are dimension-driven
    assert (base.features[0].provenance["fsgen_feature_json"]["entities"]
            != changed.features[0].provenance["fsgen_feature_json"]["entities"])
    assert before["constraints"] != after["constraints"]
    plan = plan_changes(base, base, changed)
    assert any(c.path == "structure" and c.logical_id == "Outline" for c in plan.conflicts)

    renamed = compile_fsgen(circle.replace('skCircle(s, "rim",',
                                            'skCircle(s, "outer",'), Target("d", "w", "e"), "r1")
    assert renamed.features[0].structure["fsgen_native"]["entities"] != before["entities"]
    assert any(c.path == "structure" and c.logical_id == "Outline"
               for c in plan_changes(base, base, renamed).conflicts)

    moved = compile_fsgen(circle.replace('"center" : vector(0, 0) * millimeter',
                                          '"center" : vector(2, 0) * millimeter'), Target("d", "w", "e"), "r1")
    assert moved.features[0].structure["fsgen_native"]["constraints"] != before["constraints"]
    assert any(c.path == "structure" and c.logical_id == "Outline"
               for c in plan_changes(base, base, moved).conflicts)


def test_literal_extrusion_depth_edit_is_parameter_only():
    base = compile_fsgen(SOURCE, Target("d", "w", "e"), "r1")
    changed = compile_fsgen(SOURCE.replace('"depth" : 5 * millimeter',
                                           '"depth" : 7 * millimeter'), Target("d", "w", "e"), "r1")
    plan = plan_changes(base, base, changed)
    assert not plan.conflicts
    assert [op.logical_id for op in plan.operations] == ["Solid"]
