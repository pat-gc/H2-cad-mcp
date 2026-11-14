from copy import deepcopy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen, _semantic_native_body
from h2cad.model import Target
from h2cad.native_rectangles import stage_source_rectangle

SOURCE = Path(__file__).resolve().parents[1] / "fixtures/car/basic_car.fs"
TARGET = Target("1"*24, "2"*24, "3"*24)


def source(name="Chassis sketch", text=None):
    plan = compile_fsgen(SOURCE if text is None else text, TARGET)
    return (next(f for f in plan.features if f.logical_id == name),
            [f for f in plan.features if f.kind == "assignVariable"])


@pytest.mark.parametrize("name,xy,expressions", [
    ("Chassis sketch", [-.045, -.09, .045, .09],
     ["#width / 2 - (-#width / 2)", "#length / 2 - (-#length / 2)", "-(-#width / 2)", "-(-#length / 2)"]),
    ("Body sketch", [-.04, -.06, .04, .06], ["80 mm", "120 mm", "40 mm", "60 mm"])])
def test_source_rectangle_preserves_location_and_expression_dependencies(name, xy, expressions):
    feature, variables = source(name)
    original = deepcopy(feature)
    staged = stage_source_rectangle(feature, variables=variables)
    assert staged["rectangle_m"] == xy
    assert [d["expression"] for d in staged["dimensions"]] == expressions
    assert len(staged["source_constraints"]) == 12
    assert len(staged["line_fields"]) == 4
    assert staged["line_fields"][0]["geometry_fields"] == {"pntX": xy[0], "pntY": xy[1], "dirX": 1, "dirY": 0}
    assert not staged["write_ready"] and not staged["frame_verified"] and not staged["regeneration_verified"]
    assert staged["plane_logical_id"] == name.replace("sketch", "height")
    assert feature == original


def test_positive_nonzero_corner_and_new_source_variable_value():
    text = SOURCE.read_text().replace("vector(-40, -60)", "vector(10, 20)")
    body, variables = source("Body sketch", text)
    assert stage_source_rectangle(body, variables=variables)["rectangle_m"] == [.01, .02, .04, .06]
    text = SOURCE.read_text().replace('"width", 90 * millimeter', '"width", 100 * millimeter')
    chassis, variables = source(text=text)
    staged = stage_source_rectangle(chassis, variables=variables)
    assert staged["rectangle_m"] == [-.05, -.09, .05, .09]
    assert [d["value_mm"] for d in staged["dimensions"]] == [100, 180, 50, 90]
    assert staged["dimensions"][0]["expression"] == "#width / 2 - (-#width / 2)"


@pytest.mark.parametrize("fault", ["provenance", "summary", "geometry", "line_id", "construction", "parameter_schema",
    "plane_projection", "dimension_value", "origin_query", "constraint_ref", "constraint_type", "constraint_id",
    "dependencies", "missing_variable", "variable_changed", "zero_corner", "wrong_count", "nonlinear"])
def test_reject_source_mismatch_without_inventing_native_origin(fault):
    feature, variables = source()
    raw = feature.provenance["fsgen_feature_json"]
    if fault == "provenance": raw["name"] = "wrong"
    if fault == "summary": feature.structure["sketch"]["rectangle"]["x0"] = -.044
    if fault == "geometry": raw["entities"][0]["geometry"]["pntX"] = -.044
    if fault == "line_id": raw["entities"][0]["startPointId"] = "other"
    if fault == "construction": raw["entities"][0]["isConstruction"] = True
    if fault == "parameter_schema": feature.structure["parameter_schema"]["sketchPlane"]["btType"] = "wrong"
    if fault == "plane_projection": feature.parameters["sketchPlane"] = ["wrong"]
    if fault == "dimension_value": raw["constraints"][8]["parameters"][-1]["expression"] = "91 mm"
    if fault == "origin_query": raw["constraints"][10]["parameters"][1]["queries"][0]["queryString"] = "wrong"
    if fault == "constraint_ref": raw["constraints"][0]["parameters"][0]["value"] = "outline.right.start"
    if fault == "constraint_type": raw["constraints"][10]["constraintType"] = "FIX"
    if fault == "constraint_id": raw["constraints"][1]["entityId"] = raw["constraints"][0]["entityId"]
    if fault == "dependencies": feature.dependencies = ("Chassis height",)
    if fault == "missing_variable": variables = [v for v in variables if v.logical_id != "#width"]
    if fault == "variable_changed":
        other = SOURCE.read_text().replace('"width", 90 * millimeter', '"width", 91 * millimeter')
        _, variables = source(text=other)
    if fault == "zero_corner": feature.structure["sketch"]["rectangle"]["x0"] = 0
    if fault == "wrong_count": raw["constraints"].pop()
    if fault == "nonlinear": raw["constraints"][8]["parameters"][-1]["expression"] = "#width * #width"
    if fault != "provenance":
        # Re-project to exercise actual source schema/topology checks as well as provenance.
        feature.structure["fsgen_native"] = _semantic_native_body(raw)
    with pytest.raises(Unsupported):
        stage_source_rectangle(feature, variables=variables)
