import copy

import pytest

from h2cad.model import Feature, Plan, Snapshot, Target
from h2cad.planner import plan_changes


T = Target("d", "w", "e")


def snap(*features, revision="r1", complete=True):
    return Snapshot(T, revision, list(features), complete)


def feature(fid, value=1, *, owner="ai", dep=(), native_id=None):
    return Feature(fid, "extrude", {"depth": value}, dep, {}, native_id, owner)


def test_independent_parameter_merge_preserves_identity_and_human_feature():
    base = snap(Feature("a", "extrude", {"depth": 1, "offset": 2}, native_id="N1"),
                feature("human", owner="human", native_id="N2"))
    observed = snap(Feature("a", "extrude", {"depth": 1, "offset": 3}, native_id="N1"),
                    feature("human", owner="human", native_id="N2"), revision="r2")
    desired = snap(Feature("a", "extrude", {"depth": 4, "offset": 2}, native_id="N1"))
    before = copy.deepcopy((base, observed, desired))
    plan = plan_changes(base, observed, desired)
    assert not plan.conflicts
    assert len(plan.operations) == 1 and plan.operations[0].action == "update"
    assert plan.merged.features[0].parameters == {"depth": 4, "offset": 3}
    assert plan.merged.features[0].native_id == "N1"
    assert plan.merged.features[1].ownership == "human"
    assert (base, observed, desired) == before
    assert Plan.from_dict(plan.to_dict()).to_dict() == plan.to_dict()


def test_same_parameter_edit_conflicts():
    plan = plan_changes(snap(feature("a", 1)), snap(feature("a", 2), revision="r2"),
                        snap(feature("a", 3)))
    assert any(c.path == "parameters.depth" for c in plan.conflicts)


def test_incomplete_readback_and_structural_change_conflict():
    base = snap(feature("a"))
    obs = snap(feature("a"), complete=False)
    desired = snap(Feature("a", "fillet", {"depth": 1}))
    plan = plan_changes(base, obs, desired)
    assert {c.path for c in plan.conflicts} >= {"snapshot", "kind"}


def test_created_dependency_must_precede_feature():
    desired = snap(feature("b", dep=("a",)), feature("a"))
    plan = plan_changes(snap(), snap(), desired)
    assert any(c.path == "dependencies" for c in plan.conflicts)


def test_operation_id_scoped_to_target_revision():
    base = snap(feature("a"))
    desired = snap(feature("a", 2))
    p1 = plan_changes(base, snap(feature("a"), revision="r1"), desired)
    p2 = plan_changes(base, snap(feature("a"), revision="r2"), desired)
    assert p1.operations[0].op_id != p2.operations[0].op_id


def test_untrusted_snapshot_requires_explicit_ownership_and_completeness():
    data = snap(feature("a")).to_dict()
    del data["complete"]
    with pytest.raises(KeyError):
        Snapshot.from_dict(data)
    data = snap(feature("a")).to_dict()
    del data["features"][0]["ownership"]
    with pytest.raises(KeyError):
        Snapshot.from_dict(data)


def test_duplicate_ids_and_nonfinite_values_rejected():
    with pytest.raises(ValueError):
        snap(feature("a"), feature("a"))
    with pytest.raises(ValueError):
        feature("a", float("nan"))
    with pytest.raises(ValueError):
        Feature("a", "sketch", {"nested": {1: "bad"}})
    with pytest.raises(ValueError):
        Feature("a", "extrude", {}, dependencies="outline")
