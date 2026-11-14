"""Validate the square-tube modeling primitive; this is not a T-slot rating."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from fsgen.native.local import build_local
from fsgen.native.script import trace
from fsgen.fslite import geom
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN, TopAbs_OUT

from h2cad.model import Target
from h2cad.source_run import _plan
from h2cad.validation import validate_fsgen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/robot/hollow_square_tube.fs"


def validate_tube(text: str) -> dict:
    plan = _plan(text, Target("a"*24, "b"*24, "c"*24))
    dimensions = {f["logical_id"]: float(f["stage"]["expression"][:-2])
                  for f in plan if f["kind"] == "assignVariable"}
    outer, wall, length = (dimensions[n] for n in ("#outerSize", "#wallThickness", "#tubeLength"))
    if not all(math.isfinite(v) for v in (outer, wall, length)) or not (0 < wall < outer/2 and 0 < length <= 1000):
        raise ValueError("Require positive wall below half outside size and bounded positive length")
    validation = validate_fsgen(text)
    if validation.status != "passed":
        raise ValueError(f"Complete local build failed: {validation.to_dict()}")
    built = build_local(trace(text, variables_mode="studio"))
    if not built.ok or built.partial or len(built.run.solids) != 1:
        raise ValueError("One complete solid required")
    shape = built.run.solids[0].shape
    if not BRepCheck_Analyzer(shape).IsValid():
        raise ValueError("Invalid OpenCascade solid")
    inner = outer - 2*wall
    volume = geom.props(shape, "volume").Mass()*1e9
    expected = (outer**2-inner**2)*length
    if not math.isclose(volume, expected, rel_tol=0, abs_tol=1e-5):
        raise ValueError("Tube analytical volume differs")
    bounds = [-outer/2,-outer/2,0,outer/2,outer/2,length]
    if validation.geometry["bbox_mm"] != bounds:
        raise ValueError("Tube bounds differ")
    def at(x,y,z):
        return BRepClass3d_SolidClassifier(shape, gp_Pnt(x/1000,y/1000,z/1000),1e-9).State()
    bore_points = [(0,0,z) for z in (0,length/2,length)]
    if any(at(*point) != TopAbs_OUT for point in bore_points):
        raise ValueError("Bore is blocked at an end or midspan")
    midpoint = outer/2-wall/2
    wall_points = [(midpoint,0,length/2),(-midpoint,0,length/2),
                   (0,midpoint,length/2),(0,-midpoint,length/2)]
    if any(at(*point) != TopAbs_IN for point in wall_points):
        raise ValueError("One or more tube walls are missing")
    cut = plan[-1]["stage"]
    if cut["operation_type"] != "REMOVE" or cut["target_body_logical_id"] != "Tube blank":
        raise ValueError("Explicit Tube blank REMOVE scope required")
    return {"source_sha256":hashlib.sha256(text.encode()).hexdigest(), "source_features":len(plan),
            "dimensions_mm":{"outer":outer,"wall":wall,"length":length,"inner":inner},
            "solid_count":1,"kernel_valid":True,"volume_mm3":volume,"expected_volume_mm3":expected,
            "bounds_mm":bounds,"through_bore_probes_mm":[list(p) for p in bore_points],
            "four_wall_probes_mm":[list(p) for p in wall_points],"source_plan_supported":True,
            "local_validation":validation.to_dict(),"native_verification":"not_run",
            "component_class":"hollow square tube modeling primitive, not 2020 T-slot extrusion"}


def main():
    report = validate_tube(SOURCE.read_text(encoding="utf-8"))
    path = ROOT / "artifacts/robot/hollow-tube-local-validation.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
