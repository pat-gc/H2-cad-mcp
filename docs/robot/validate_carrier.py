"""Offline geometry/identity fixture for centered holes and exact REMOVE scope."""
import hashlib
import json
import math
from pathlib import Path
from h2cad.validation import validate_fsgen
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from fsgen.native.script import trace
from fsgen.native.local import build_local
from OCP.BRepCheck import BRepCheck_Analyzer
from fsgen.fslite import geom as G

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'artifacts/robot/bearing_carrier_scope_fixture.fs'

def main():
    source=SOURCE.read_text()
    result=validate_fsgen(source)
    assert result.status=='passed',result.to_dict()
    run=build_local(trace(source,variables_mode='studio')).run
    assert len(run.solids)==2
    assert all(BRepCheck_Analyzer(b.shape).IsValid() for b in run.solids)
    hole_area=math.pi*(14**2+4*2.75**2+2*1.65**2)
    expected=(3600-hole_area)*12+3600*3
    # Public metrics are rounded to four decimal places in FSGen.
    assert abs(result.geometry['volume_mm3']-expected)<1e-4
    assert result.geometry['bbox_mm']==[-30.,-30.,0.,30.,30.,23.]
    body_volumes=[G.props(b.shape,'volume').Mass()*1e9 for b in run.solids]
    assert abs(sum(body_volumes)-expected)<1e-5
    assert any(abs(v-10800)<1e-5 for v in body_volumes),body_volumes
    variant=validate_fsgen(source.replace('"carrierThickness", 12 * millimeter','"carrierThickness", 14 * millimeter'))
    expected_delta=2*(3600-hole_area)
    assert variant.status=='passed' and variant.geometry['parts']==2
    assert abs(variant.geometry['volume_mm3']-result.geometry['volume_mm3']-expected_delta)<1e-4
    snapshot=compile_fsgen(source,Target('offline-robot','offline-workspace','offline-carrier'))
    output=dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                native_feature_count=len(snapshot.features),
                expected_volume_mm3=expected,expected_witness_volume_mm3=10800,
                expected_bounds_mm=[[-30,-30,0],[30,30,23]],
                actual_body_volumes_mm3=body_volumes,
                thickness_12_to_14_expected_volume_delta_mm3=expected_delta,
                thickness_12_to_14_actual_volume_delta_mm3=variant.geometry['volume_mm3']-result.geometry['volume_mm3'],
                kernel_valid_solids=2,validation=result.to_dict(),
                remote='not_run',native_editability='not_run')
    (ROOT/'artifacts/robot/carrier-local-validation.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
