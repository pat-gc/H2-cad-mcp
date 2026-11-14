"""Offline source consistency for the car's variable definitions."""

from copy import deepcopy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native import stage_length_variable


SOURCE = Path(__file__).resolve().parents[1] / "fixtures" / "car" / "basic_car.fs"
TARGET = Target("d" * 24, "w" * 24, "e" * 24)


def _variables(text: str):
    return [feature for feature in compile_fsgen(text, TARGET).features
            if feature.kind == "assignVariable"]


def test_real_car_variable_stage_preserves_source_order_expressions_and_raw_template():
    original = SOURCE.read_text(encoding="utf-8")
    staged = [stage_length_variable(feature) for feature in _variables(original)]
    assert [(item["logical_id"], item["expression"]) for item in staged] == [
        ("#length", "180 mm"), ("#width", "90 mm"), ("#bodyHeight", "37 mm"),
        ("#wheelbase", "130 mm"), ("#wheelRadius", "14 mm"),
        ("#wheelThickness", "12 mm"), ("#axleRadius", "4 mm")]
    assert [item["source_line"] for item in staged] == sorted(item["source_line"] for item in staged)
    assert all(item["dependencies"] == [] and item["ready_to_submit"] is False for item in staged)
    assert all(len(item["source_template"]["parameters"]) == 42 for item in staged)

    changed = original.replace('variable(context, "wheelRadius", 14 * millimeter);',
                               'variable(context, "wheelRadius", 16 * millimeter);')
    assert [stage_length_variable(feature)["expression"] for feature in _variables(changed)][4] == "16 mm"


def test_variable_stage_rejects_semantic_raw_mismatch_and_unsupported_mode():
    feature = _variables(SOURCE.read_text(encoding="utf-8"))[0]
    changed = deepcopy(feature)
    changed.parameters["lengthValue"] = "181 mm"
    with pytest.raises(Unsupported, match="values differ"):
        stage_length_variable(changed)

    changed = deepcopy(feature)
    changed.provenance["fsgen_feature_json"]["parameters"][5]["expression"] = "181 mm"
    with pytest.raises(Unsupported, match="values differ"):
        stage_length_variable(changed)

    changed = deepcopy(feature)
    changed.dependencies = ("#width",)
    with pytest.raises(Unsupported, match="cannot have feature dependencies"):
        stage_length_variable(changed)

    changed = deepcopy(feature)
    changed.parameters["mode"] = "MEASURED"
    for parameter in changed.provenance["fsgen_feature_json"]["parameters"]:
        if parameter["parameterId"] == "mode":
            parameter["value"] = "MEASURED"
    with pytest.raises(Unsupported, match="ASSIGNED/LENGTH"):
        stage_length_variable(changed)
