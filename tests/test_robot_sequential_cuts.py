"""Independent local geometry expectations for future native sequential cuts."""
import math
from pathlib import Path

import pytest
from fsgen.native.local import build_local
from fsgen.native.script import trace
from fsgen.fslite import geom
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
from h2cad.backend import Unsupported
from h2cad.model import Target
from h2cad.source_run import _plan

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("variant", ["counterbore", "split"])
@pytest.mark.parametrize("thickness", [12, 14])
def test_sequential_cuts_preserve_exact_scope_and_depth(variant, thickness):
    source = (ROOT / f"fixtures/robot/carrier_sequential_{variant}.fs").read_text()
    source = source.replace('"carrierThickness", 12 * millimeter', f'"carrierThickness", {thickness} * millimeter')
    built = build_local(trace(source, variables_mode="studio"))
    assert built.ok and not built.partial
    shapes = [body.shape for body in built.run.solids]
    assert all(BRepCheck_Analyzer(shape).IsValid() for shape in shapes)
    volumes = sorted(geom.props(shape, "volume").Mass()*1e9 for shape in shapes)
    if variant == "counterbore":
        expected = (3600-math.pi*(14**2+4*2.75**2+2*1.65**2))*thickness - math.pi*(16**2-14**2)*3
        assert volumes == pytest.approx([10800, expected], abs=1e-5)
    else:
        expected = (27*60-math.pi*3**2)*thickness
        assert volumes == pytest.approx([10800, expected, expected], abs=1e-5)
    def occupied(x, y, z):
        states = [BRepClass3d_SolidClassifier(shape, gp_Pnt(x/1000,y/1000,z/1000),1e-9).State() for shape in shapes]
        assert all(state in (TopAbs_IN, TopAbs_OUT) for state in states)
        return states.count(TopAbs_IN)
    if variant == "counterbore":
        assert occupied(15,0,1) == 0  # shallow counterbore
        assert occupied(15,0,4) == 1  # shoulder remains below it
        assert occupied(0,0,6) == 0   # original through bore remains open
        assert occupied(0,0,21) == 1  # overlapping witness was not cut
    else:
        for x in (-15,15):
            assert occupied(x,0,6) == 0  # second cut reached both descendants
            assert occupied(x,0,21) == 1 # witness survived both cutting tools
        assert occupied(0,0,6) == 0      # first split remains open
        assert occupied(20,10,6) == occupied(-20,10,6) == 1
    # Local capability does not silently enable the native writer.
    with pytest.raises(Unsupported, match="Repeated REMOVE target"):
        _plan(source, Target("a"*24,"b"*24,"c"*24))
