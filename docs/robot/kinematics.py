"""Rz-Pz-Rz-Rz concept workspace checks, millimetres and radians.

This is a kinematic calculation, not collision checking or a motion controller.
Z is carriage travel relative to its lower stop, not world tool height.
"""
import json
import math
from pathlib import Path

L1, L2, TOOL = 220.0, 160.0, 20.0
LIMITS = ((-120.0, 120.0), (0.0, 140.0), (-150.0, 150.0))


def forward(base, lift, elbow, wrist):
    if not all(math.isfinite(v) for v in (base, lift, elbow, wrist)):
        raise ValueError("Finite joint coordinates required")
    yaw = base + elbow + wrist
    return (L1 * math.cos(base) + L2 * math.cos(base + elbow) + TOOL * math.cos(yaw),
            L1 * math.sin(base) + L2 * math.sin(base + elbow) + TOOL * math.sin(yaw),
            lift, yaw)


def inverse_aligned(x, y, lift):
    """Positive elbow branch with wrist zero; tool yaw follows the distal link."""
    if not all(math.isfinite(v) for v in (x, y, lift)) or not 0 <= lift <= 200:
        raise ValueError("Finite XY and lift in [0, 200] mm required")
    distal = L2 + TOOL
    cosine = (x*x + y*y - L1*L1 - distal*distal) / (2*L1*distal)
    if not -1 - 1e-12 <= cosine <= 1 + 1e-12:
        raise ValueError("Position is outside geometric reach")
    elbow = math.acos(max(-1.0, min(1.0, cosine)))
    base = math.atan2(y, x) - math.atan2(distal*math.sin(elbow), L1 + distal*math.cos(elbow))
    joints = (base, lift, elbow, 0.0)
    for angle, (low, high) in zip((base, elbow, 0.0), LIMITS):
        if not low - 1e-9 <= math.degrees(angle) <= high + 1e-9:
            raise ValueError("Position exceeds configured joint limits")
    return joints


def coverage_report():
    samples = []
    max_error = 0.0
    for lift in (0.0, 200.0):
        for y in range(-200, 201):
            q = inverse_aligned(300.0, float(y), lift)
            actual = forward(*q)
            max_error = max(max_error, math.dist(actual[:3], (300.0, y, lift)))
            samples.append(q)
    angles = [(math.degrees(q[0]), math.degrees(q[2]), math.degrees(q[3])) for q in samples]
    reach = inverse_aligned(400.0, 0.0, 0.0)
    return {
        "status": "kinematics verified; collision and hardware checks outstanding",
        "coverage": {"x_mm": 300, "y_mm": [-200, 200], "lift_mm": [0, 200],
                     "sample_spacing_mm": 1, "sample_count": len(samples)},
        "angle_ranges_deg": {name: [min(q[i] for q in angles), max(q[i] for q in angles)]
                             for i, name in enumerate(("base", "elbow", "wrist"))},
        "max_forward_error_mm": max_error,
        "minimum_abs_planar_jacobian_determinant_mm2": min(
            abs(L1 * (L2 + TOOL) * math.sin(q[2])) for q in samples),
        "maximum_reach_mm": forward(*reach)[0],
        "maximum_reach_is_singular": abs(math.sin(reach[2])) < 1e-8,
        "tool_yaw_policy": "wrist zero; yaw varies with base plus elbow",
        "collision_verified": False,
        "native_assembly_verified": False,
    }


if __name__ == "__main__":
    report = coverage_report()
    path = Path(__file__).resolve().parents[2] / "artifacts/robot/workspace-validation.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
