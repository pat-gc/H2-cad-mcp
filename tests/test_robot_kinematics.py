import importlib.util
import math
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("robot_kinematics", Path(__file__).resolve().parents[1] / "docs/robot/kinematics.py")
robot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(robot)


def test_side_coverage_across_lift_and_singular_reach_are_distinguished():
    report = robot.coverage_report()
    assert report["coverage"]["sample_count"] == 802
    assert report["max_forward_error_mm"] < 1e-10
    assert report["minimum_abs_planar_jacobian_determinant_mm2"] > 30000
    assert report["maximum_reach_mm"] == 400
    assert report["maximum_reach_is_singular"]
    assert report["collision_verified"] is False


@pytest.mark.parametrize("point", [(401, 0, 0), (0, 0, 0), (300, 0, -1),
                                   (300, 0, 201), (float("nan"), 0, 0),
                                   (float("inf"), 0, 0), (-300, 0, 0), (50, 0, 0)])
def test_unreachable_or_out_of_limit_targets_are_not_silently_clamped(point):
    with pytest.raises(ValueError):
        robot.inverse_aligned(*point)


def test_wrist_changes_tool_position_and_yaw_without_changing_lift():
    a = robot.forward(0, 100, math.pi/2, 0)
    b = robot.forward(0, 100, math.pi/2, -math.pi/2)
    assert a[:3] == pytest.approx((220, 180, 100))
    assert b[:3] == pytest.approx((240, 160, 100))
    assert b[3] == pytest.approx(0)
