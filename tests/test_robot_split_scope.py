"""A first-cut split fixture for the missing descendant-cardinality live gate."""
from pathlib import Path

import pytest
from OCP.BRepCheck import BRepCheck_Analyzer
from fsgen.native.local import build_local
from fsgen.native.script import trace
from fsgen.fslite import geom
from h2cad.model import Target
from h2cad.source_run import _plan
from h2cad.validation import validate_fsgen


def test_scoped_slot_splits_target_but_preserves_witness():
    source=(Path(__file__).resolve().parents[1]/"fixtures/native/carrier_split_scope_sample.fs").read_text()
    plan=_plan(source,Target("a"*24,"b"*24,"c"*24))
    assert len(plan)==9
    assert [f["stage"]["operation_type"] for f in plan if f["kind"]=="extrude"]==["NEW","NEW","REMOVE"]
    result=validate_fsgen(source)
    assert result.status=="passed" and result.geometry["parts"]==3
    assert result.geometry["volume_mm3"]==pytest.approx(49680)
    built=build_local(trace(source,variables_mode="studio"))
    assert all(BRepCheck_Analyzer(b.shape).IsValid() for b in built.run.solids)
    volumes=sorted(geom.props(b.shape,"volume").Mass()*1e9 for b in built.run.solids)
    assert volumes==pytest.approx([10800,19440,19440],abs=1e-5)
