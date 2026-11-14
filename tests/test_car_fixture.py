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


def test_wheel_radius_variable_edit_preserves_driven_circle_definitions():
    source = SOURCE.read_text(encoding="utf-8")
    variant = source.replace('"wheelRadius", 14 * millimeter',
                             '"wheelRadius", 16 * millimeter')
    assert variant != source
    target = Target("d", "w", "e")
    base = compile_fsgen(source, target, "r1")
    desired = compile_fsgen(variant, target, "r1")
    plan = plan_changes(base, base, desired)
    assert not plan.conflicts, [(conflict.logical_id, conflict.path) for conflict in plan.conflicts]
    assert [operation.logical_id for operation in plan.operations] == ["#wheelRadius"]
    for name in ("Left wheel sketch", "Right wheel sketch"):
        original = next(feature for feature in base.features if feature.logical_id == name)
        updated = next(feature for feature in desired.features if feature.logical_id == name)
        assert original.semantically_equal(updated)
        assert original.dependencies == updated.dependencies
        assert original.provenance["fsgen_feature_json"]["_driven"] == ["front", "rear"]
        assert original.provenance["fsgen_feature_json"]["entities"] != updated.provenance["fsgen_feature_json"]["entities"]
        assert all("geometry" not in entity for entity in original.structure["fsgen_native"]["entities"])
    for script in (source, variant):
        report = validate_fsgen(script)
        assert report.status == "passed", report.to_dict()
        assert report.geometry["parts"] == 8


def test_wheelbase_variable_edit_keeps_driven_center_constraints():
    source = SOURCE.read_text(encoding="utf-8")
    variant = source.replace('"wheelbase", 130 * millimeter',
                             '"wheelbase", 140 * millimeter')
    assert variant != source
    target = Target("d", "w", "e")
    base = compile_fsgen(source, target, "r1")
    desired = compile_fsgen(variant, target, "r1")
    plan = plan_changes(base, base, desired)
    assert not plan.conflicts, [(conflict.logical_id, conflict.path) for conflict in plan.conflicts]
    assert [operation.logical_id for operation in plan.operations] == ["#wheelbase"]


def test_car_offset_planes_preserve_variable_expressions_and_source_order():
    snapshot = compile_fsgen(SOURCE, Target("d", "w", "e"))
    features = {feature.logical_id: feature for feature in snapshot.features}
    ordered = [feature.logical_id for feature in snapshot.features]
    expected = {
        "Chassis height": ("20 mm", ()),
        "Wheel left plane": ("-#width / 2 - #wheelThickness", ("#width", "#wheelThickness")),
        "Wheel right plane": ("#width / 2", ("#width",)),
    }
    for name, (expression, dependencies) in expected.items():
        plane = features[name]
        assert plane.kind == "cPlane"
        assert plane.parameters["offset"] == expression
        assert plane.dependencies == dependencies
        offset = next(item for item in plane.provenance["fsgen_feature_json"]["parameters"]
                      if item["parameterId"] == "offset")
        assert offset["expression"] == expression
        assert all(ordered.index(dep) < ordered.index(name) for dep in dependencies)


def test_offset_plane_feature_reference_remains_a_dependency():
    source = SOURCE.read_text(encoding="utf-8")
    marker = 'cPlane(context, id + "Wheel right plane", {'
    assert marker in source
    prefix, suffix = source.split(marker, 1)
    old = 'qCreatedBy(makeId("Right"), EntityType.FACE)'
    new = 'qCreatedBy(id + "Wheel left plane", EntityType.FACE)'
    assert old in suffix
    variant = prefix + marker + suffix.replace(old, new, 1)
    snapshot = compile_fsgen(variant, Target("d", "w", "e"))
    right = next(feature for feature in snapshot.features if feature.logical_id == "Wheel right plane")
    assert right.dependencies == ("#width", "Wheel left plane")
    assert right.parameters["offset"] == "#width / 2"
