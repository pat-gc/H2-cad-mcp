"""Local structural primitive proof; does not claim native or T-slot verification."""
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("validate_hollow_tube",ROOT/"scripts/validate_hollow_tube.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("length,wall,volume",[(220,2,31680),(160,2,23040),(220,3,44880)])
def test_valid_hollow_tube_and_dimension_changes(length,wall,volume):
    text=module.SOURCE.read_text().replace('"tubeLength", 220 * millimeter',f'"tubeLength", {length} * millimeter')
    text=text.replace('"wallThickness", 2 * millimeter',f'"wallThickness", {wall} * millimeter')
    proof=module.validate_tube(text)
    assert proof["source_features"]==8 and proof["solid_count"]==1 and proof["kernel_valid"]
    assert proof["volume_mm3"]==pytest.approx(volume,abs=1e-5)
    assert proof["bounds_mm"]==[-10,-10,0,10,10,length]
    assert len(proof["through_bore_probes_mm"])==3 and len(proof["four_wall_probes_mm"])==4
    assert proof["native_verification"]=="not_run"


def test_native_source_plan_keeps_wall_and_length_dependencies():
    from h2cad.source_run import _plan
    from h2cad.model import Target
    plan=_plan(module.SOURCE.read_text(),Target("a"*24,"b"*24,"c"*24))
    bore=next(f for f in plan if f["logical_id"]=="Tube bore")
    assert set(bore["stage"]["source_stage"]["source_variable_definitions"])=={"#outerSize","#wallThickness"}
    assert plan[-1]["stage"]["depth_expression"]=="#tubeLength"
    assert plan[-1]["stage"]["target_body_logical_id"]=="Tube blank"
    assert plan[-1]["stage"]["operation_type"]=="REMOVE"


def test_union_of_two_uncut_solids_is_not_accepted_as_tube():
    text=module.SOURCE.read_text().replace("NewBodyOperationType.REMOVE","NewBodyOperationType.NEW")
    # Remove scope from the NEW variant so rejection proves the geometric check.
    text=text.replace(',\n        "defaultScope" : false,\n        "booleanScope" : qCreatedBy(id + "Tube blank", EntityType.BODY)', '')
    with pytest.raises(ValueError,match="One complete solid"):
        module.validate_tube(text)
