"""Exact source scope staging, deliberately separate from native write support."""
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native_extrusions import stage_source_extrusion, map_source_extrusion

SOURCE = Path(__file__).resolve().parents[1] / "fixtures/native/carrier_remove_scope_sample.fs"
TARGET = Target("a" * 24, "b" * 24, "c" * 24)


def staged_source(text=None):
    features = compile_fsgen(SOURCE if text is None else text, TARGET).features
    cut = next(f for f in features if f.logical_id == "Carrier through bores")
    variables = [f for f in features if f.kind == "assignVariable"]
    return cut, variables


def test_remove_retains_exact_source_body_dependency():
    cut, variables = staged_source()
    stage = stage_source_extrusion(cut, variables)
    assert stage["operation_type"] == "REMOVE"
    assert stage["target_body_logical_id"] == "Carrier blank"
    assert set(cut.dependencies) == {"Carrier holes", "Carrier blank"}
    assert stage["depth_seed_mm"] == 24
    assert not stage["solid_geometry_verified"]


@pytest.mark.parametrize("old,new", [
    ('"defaultScope" : false', '"defaultScope" : true'),
    ('qCreatedBy(id + "Carrier blank", EntityType.BODY)', 'qCreatedBy(id + "Carrier blank", EntityType.FACE)'),
    ('NewBodyOperationType.REMOVE', 'NewBodyOperationType.ADD'),
])
def test_implicit_or_nonbody_remove_scope_rejected(old, new):
    cut, variables = staged_source(SOURCE.read_text().replace(old, new))
    with pytest.raises(Unsupported):
        stage_source_extrusion(cut, variables)


def test_remove_mapper_requires_explicit_target_binding():
    from test_native_remove_extrusions import remove_scenario
    features,args=remove_scenario()
    cut=next(f for f in features if f.logical_id==args["logical_id"])
    sketch=next(n for n in args["before"]["tree"]["children"] if n.get("featureId")=="sourceSketch_0")
    with pytest.raises(Unsupported, match="source NEW body definition"):
        map_source_extrusion(args["before"],cut,target=TARGET,sketch_feature_id="sourceSketch_0",
            sketch_definition=sketch,query_response=args["query_response"],
            variables=[f for f in features if f.kind=="assignVariable"])
