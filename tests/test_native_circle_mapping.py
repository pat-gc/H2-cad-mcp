import copy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native_circles import stage_source_circles

SOURCE = Path(__file__).resolve().parents[1] / "fixtures/car/basic_car.fs"
TARGET = Target("a" * 24, "b" * 24, "c" * 24)


def features(text=None):
    fs = compile_fsgen(text or SOURCE, TARGET).features
    return ([f for f in fs if f.logical_id in {"Axle sketch", "Left wheel sketch", "Right wheel sketch"}],
            [f for f in fs if f.kind == "assignVariable"])


def test_three_car_circle_sketches_keep_source_planes_expressions_and_signs():
    sketches, variables = features()
    plans = [stage_source_circles(s, variables=variables) for s in sketches]
    assert [p["plane_logical_id"] for p in plans] == ["Axle left plane", "Wheel left plane", "Wheel right plane"]
    for plan in plans:
        front, rear = plan["circles"]
        assert front["seed_geometry"]["xCenter"] == .065
        assert rear["seed_geometry"]["xCenter"] == -.065
        assert [d["source_expression"] for d in front["dimensions"]][1:] == ["#wheelbase / 2", "15 mm"]
        assert [d["source_expression"] for d in rear["dimensions"]][1:] == ["-(-#wheelbase / 2)", "15 mm"]
        assert rear["dimensions"][1]["native_mapping"]["alignment"] == "ALIGNED"
        assert rear["dimensions"][2]["native_mapping"]["alignment"] == "ANTI_ALIGNED"
        assert front["dimensions"][1]["native_mapping"]["alignment"] is None
        assert not front["dimensions"][1]["native_mapping"]["mapping_observed"]
        assert not plan["write_ready"] and not plan["regeneration_verified"]
        assert not plan["anchor_evidence"]["independent_fix_without_snap_verified"]
        assert plan["anchor_evidence"]["external_snap_constraint_type"] == 1
        assert plan["source_constraints"] == next(s for s in sketches if s.logical_id == plan["logical_id"]).provenance["fsgen_feature_json"]["constraints"]


def test_source_variable_edits_restage_seeds_without_erasing_symbolic_constraints():
    text = SOURCE.read_text().replace('variable(context, "wheelRadius", 14 * millimeter)',
                                     'variable(context, "wheelRadius", 16 * millimeter)')
    sketches, variables = features(text)
    plan = stage_source_circles(sketches[1], variables=variables)
    assert plan["circles"][0]["seed_geometry"]["radius"] == .016
    assert plan["circles"][0]["dimensions"][0]["source_expression"] == "2 * #wheelRadius"
    assert plan["circles"][0]["dimensions"][0]["source_value_mm"] == 32
    assert not plan["regeneration_verified"]


@pytest.mark.parametrize("fault", ["radius", "center", "direction", "raw_expression", "plane_projection", "dependencies", "missing_variable", "late_variable"])
def test_inconsistent_or_unbound_circle_source_is_rejected(fault):
    sketches, variables = features()
    sketch = copy.deepcopy(sketches[1])
    raw = sketch.provenance["fsgen_feature_json"]
    if fault == "radius": raw["entities"][0]["geometry"]["radius"] = .02
    if fault == "center": raw["entities"][0]["geometry"]["xCenter"] = .1
    if fault == "direction": raw["entities"][0]["geometry"]["xDir"] = -1
    if fault == "raw_expression": raw["constraints"][0]["parameters"][1]["expression"] = "40 mm"
    if fault == "plane_projection": sketch.parameters["sketchPlane"] = ["wrong"]
    if fault == "dependencies": sketch.dependencies = (*sketch.dependencies, "unknown")
    if fault == "missing_variable": variables = [v for v in variables if v.logical_id != "#wheelRadius"]
    if fault == "late_variable":
        variables = copy.deepcopy(variables)
        next(v for v in variables if v.logical_id == "#wheelRadius").provenance["source_line"] = 100000
    with pytest.raises(Unsupported):
        stage_source_circles(sketch, variables=variables)
