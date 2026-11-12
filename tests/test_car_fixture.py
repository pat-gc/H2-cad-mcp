"""Offline, eight-body concept car acceptance fixture; no assembly claim."""

from pathlib import Path

import pytest

from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.planner import plan_changes
from h2cad.validation import validate_fsgen


SOURCE = Path(__file__).resolve().parents[1] / "fixtures" / "car" / "basic_car.fs"


def test_basic_car_and_body_height_variant_build_eight_local_bodies():
    source = SOURCE.read_text(encoding="utf-8")
    variant = source.replace('"bodyHeight", 37 * millimeter',
                             '"bodyHeight", 42 * millimeter')
    assert variant != source
    reports = [validate_fsgen(script) for script in (source, variant)]
    for report in reports:
        assert report.status == "passed", report.to_dict()
        assert report.geometry["parts"] == 8
        assert report.remote == "not_run"
        assert report.native_editability == "not_run"
    assert reports[1].geometry["volume_mm3"] - reports[0].geometry["volume_mm3"] == pytest.approx(48000)


def test_body_height_edit_preserves_unrelated_feature_definitions():
    source = SOURCE.read_text(encoding="utf-8")
    target = Target("d", "w", "e")
    base = compile_fsgen(source, target, "r1")
    desired = compile_fsgen(source.replace('"bodyHeight", 37 * millimeter',
                                           '"bodyHeight", 42 * millimeter'), target, "r1")
    plan = plan_changes(base, base, desired)
    assert not plan.conflicts, [conflict.to_dict() for conflict in plan.conflicts]
    assert [operation.logical_id for operation in plan.operations] == ["#bodyHeight"]
    assert [feature.logical_id for feature in plan.merged.features] == [
        feature.logical_id for feature in base.features]
    assert [feature for feature in plan.merged.features if feature.logical_id != "#bodyHeight"] == [
        feature for feature in base.features if feature.logical_id != "#bodyHeight"]
