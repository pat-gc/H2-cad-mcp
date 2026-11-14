"""Offline mapping against observed plane parameter/query shapes, not live proof."""

import copy
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.native_planes import expected_offset_plane_tree, stage_offset_plane


SOURCE = Path(__file__).resolve().parents[1] / "fixtures/car/basic_car.fs"
TARGET = Target("1" * 24, "2" * 24, "3" * 24)
REV = "4" * 24


def source_features(text=None):
    snapshot = compile_fsgen(SOURCE if text is None else text, TARGET)
    return ({f.logical_id: f for f in snapshot.features if f.kind == "cPlane"},
            [f for f in snapshot.features if f.kind == "assignVariable"])


def native_draft(reference="Top"):
    # Sanitized observed nine-parameter native draft. IDs intentionally differ
    # from the live samples; the mapper must preserve caller-provided identities.
    query = {"$type": "bsedit.GBTMIndividualQuery", "nodeId": "bound-query",
             "deterministicIds": ["observed-reference"], "queryString": "", "hasUserCode": False}
    specs = [("entities", "QueryList", {"queries": [query], "filter": {"preserve": True}}),
             ("cplaneType", "Enum", {"enumName": "CPlaneType", "value": "OFFSET"}),
             ("offset", "Quantity", {"expression": "25 mm", "value": 25, "units": "millimeter"}),
             ("angle", "Quantity", {"expression": "0 deg", "value": 0, "units": "degree"}),
             ("oppositeDirection", "Boolean", {"value": False}),
             ("flipAlignment", "Boolean", {"value": False}),
             ("flipNormal", "Boolean", {"value": False}),
             ("width", "Quantity", {"expression": "150 mm", "value": 150, "units": "millimeter"}),
             ("height", "Quantity", {"expression": "150 mm", "value": 150, "units": "millimeter"})]
    draft = {"$type": "bsedit.GBTMFeature", "featureId": "fresh-plane", "nodeId": "fresh-node",
             "featureType": "cPlane", "name": "Plane 3", "hasUserCode": False, "namespace": "",
             "subFeatures": [], "parameterLibraries": [], "suppressed": False,
             "parameters": [{"$type": "bsedit.GBTMParameter" + kind, "parameterId": name,
                             "nodeId": "fresh-" + name, "hasUserCode": False, **fields}
                            for name, kind, fields in specs]}
    saved = {"$type": "bsedit.GBTMModel", "nodeId": "root", "children": [
        {"featureId": "unrelated", "nodeId": "keep", "parameters": [{"value": "preserve"}]},
        {"$type": "bsedit.GBTMRollback", "nodeId": "rollback"}]}
    tree = copy.deepcopy(saved)
    tree["children"].insert(1, draft)
    before = {"target": TARGET.to_dict(), "element_microversion": REV, "connected": True,
              "editingFeatureId": "fresh-plane", "tree": tree}
    binding = {"target": TARGET.to_dict(), "element_microversion": REV, "query": copy.deepcopy(query),
               "query_data": {"$type": "display.GBTQueryData", "featureId": reference,
                              "deterministicIds": ["observed-reference"], "selectionName": "Face",
                              "hasErrorEntity": False, "isTemporaryFakeDataForSelection": False,
                              "evaluationDetails": {"fullOperationId": reference + ".planeOp",
                                                    "entityType": 2, "status": 0,
                                                    "outsideExactDependencies": False}}}
    return before, saved, binding


def mapping(feature, *, variables=(), before=None, saved=None, binding=None):
    if before is None:
        before, saved, binding = native_draft("Right" if "left" in feature.logical_id or "right" in feature.logical_id else "Top")
    return expected_offset_plane_tree(feature, before, target=TARGET, expected_revision=REV,
                                      saved_tree=saved, reference_binding=binding, variables=variables)


@pytest.mark.parametrize("name,magnitude,opposite,expression", [
    ("Chassis height", 20, False, "20 mm"), ("Body height", 28, False, "28 mm"),
    ("Axle left plane", 55, True, "55 mm"),
    ("Wheel left plane", 57, True, "-(-#width / 2 - #wheelThickness)"),
    ("Wheel right plane", 45, False, "#width / 2")])
def test_all_car_offsets_preserve_symbolic_direction_mapping(name, magnitude, opposite, expression):
    planes, variables = source_features()
    result = mapping(planes[name], variables=variables)
    output = result["expected_tree"]["children"][1]
    params = {p["parameterId"]: p for p in output["parameters"]}
    assert params["offset"]["value"] == magnitude
    assert params["offset"]["expression"] == expression
    assert params["oppositeDirection"]["value"] is opposite
    assert not result["write_ready"] and not result["frame_verified"]
    assert output["featureId"] == "fresh-plane" and output["nodeId"] == "fresh-node"
    assert output["name"] == "Plane 3"  # Renaming is not implicit mutation.


def test_mapping_only_changes_offset_and_direction_and_does_not_mutate_inputs():
    planes, variables = source_features()
    before, saved, binding = native_draft("Right")
    original = copy.deepcopy(before)
    result = mapping(planes["Wheel left plane"], variables=variables, before=before, saved=saved, binding=binding)
    expected = copy.deepcopy(before["tree"])
    for p in expected["children"][1]["parameters"]:
        if p["parameterId"] == "offset":
            p.update(value=57, expression="-(-#width / 2 - #wheelThickness)")
        elif p["parameterId"] == "oppositeDirection":
            p["value"] = True
    assert result["expected_tree"] == expected
    assert before == original
    assert result["positive_variable_assumptions"]["#width"]["required_domain"] == "positive"
    assert result["dependencies"] == ["#width", "#wheelThickness"]


def test_variable_edit_updates_numeric_cache_without_baking_expression():
    planes, variables = source_features(SOURCE.read_text().replace('"width", 90', '"width", 100'))
    stage = stage_offset_plane(planes["Wheel left plane"], variables=variables)
    assert stage["magnitude_mm"] == 62
    assert stage["magnitude_expression"] == "-(-#width / 2 - #wheelThickness)"


@pytest.mark.parametrize("width", [0, -90])
def test_crossing_positive_domain_requires_replanning_and_rejects(width):
    text = '''FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");
export function build(context is Context, id is Id) {
    variable(context, "width", WIDTH * millimeter);
    variable(context, "wheelThickness", 12 * millimeter);
    cPlane(context, id + "Wheel left plane", {
        "entities" : qCreatedBy(makeId("Right"), EntityType.FACE),
        "offset" : -#width / 2 - #wheelThickness });
}'''.replace("WIDTH", str(width))
    planes, variables = source_features(text)
    with pytest.raises(Unsupported, match="strictly positive"):
        stage_offset_plane(planes["Wheel left plane"], variables=variables)


def test_mixed_sign_symbolic_expression_rejected_even_if_current_value_has_known_sign():
    text = SOURCE.read_text().replace('"offset" : -#width / 2 - #wheelThickness',
                                     '"offset" : #width / 2 - #wheelThickness')
    planes, variables = source_features(text)
    with pytest.raises(Unsupported, match="not invariant"):
        stage_offset_plane(planes["Wheel left plane"], variables=variables)


@pytest.mark.parametrize("mutate", [
    lambda f: f.parameters.update(offset="21 mm"),
    lambda f: f.provenance["fsgen_feature_json"]["parameters"][2].update(expression="21 mm"),
    lambda f: f.structure["parameter_schema"]["offset"].update(btType="BTMParameterString-149"),
    lambda f: setattr(f, "dependencies", ("#width",)),
    lambda f: f.provenance.update(source_line=0),
])
def test_divergent_source_projection_or_dependencies_rejected(mutate):
    planes, _ = source_features()
    feature = planes["Chassis height"]
    mutate(feature)
    with pytest.raises(Unsupported):
        stage_offset_plane(feature)


@pytest.mark.parametrize("mutate", [
    lambda b, s, q: b["target"].update(eid="9" * 24),
    lambda b, s, q: b.update(element_microversion="9" * 24),
    lambda b, s, q: b.update(connected=False),
    lambda b, s, q: b.update(editingFeatureId=None),
    lambda b, s, q: b["tree"]["children"][0].update(nodeId="changed"),
    lambda b, s, q: s["children"].insert(1, copy.deepcopy(b["tree"]["children"][1])),
    lambda b, s, q: b["tree"]["children"][1].update(featureType="extrude"),
    lambda b, s, q: b["tree"]["children"][1]["parameters"][2].update(expression="28 mm", value=28),
    lambda b, s, q: b["tree"]["children"][1]["parameters"][2].update(**{"$type": "wrong"}),
    lambda b, s, q: q["target"].update(eid="8" * 24),
    lambda b, s, q: q.update(element_microversion="8" * 24),
    lambda b, s, q: q["query_data"].update(featureId="Right"),
    lambda b, s, q: q["query_data"].update(deterministicIds=["different"]),
    lambda b, s, q: q["query_data"]["evaluationDetails"].update(status=1),
    lambda b, s, q: q["query_data"]["evaluationDetails"].update(outsideExactDependencies=True),
])
def test_wrong_target_draft_or_query_evidence_rejected(mutate):
    planes, _ = source_features()
    before, saved, binding = native_draft()
    mutate(before, saved, binding)
    with pytest.raises(Unsupported):
        mapping(planes["Chassis height"], before=before, saved=saved, binding=binding)


def test_literal_zero_offset_preserves_forward_direction():
    planes, variables = source_features(SOURCE.read_text().replace('"offset" : 20 * millimeter','"offset" : 0 * millimeter'))
    stage = stage_offset_plane(planes["Chassis height"], variables=variables)
    assert stage["magnitude_mm"] == 0 and stage["opposite_direction"] is False
    mapped = mapping(planes["Chassis height"],variables=variables)
    ps={p["parameterId"]:p for p in mapped["expected_tree"]["children"][1]["parameters"]}
    assert ps["offset"]["expression"]=="0 mm"
    assert ps["offset"]["value"]==0 and ps["oppositeDirection"]["value"] is False
