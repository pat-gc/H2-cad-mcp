"""Offline OFFSET-plane mapping; no allocation, transport or frame verification.

Symbolic offsets are supported only while their source length variables remain
strictly positive. Re-stage after edits: crossing zero invalidates this mapping.
The expression remains symbolic; its numeric value is only an expected cache.
"""

from __future__ import annotations

import ast
import copy
import math
import re
from fractions import Fraction
from typing import Any, Sequence

from .backend import Unsupported
from .model import Feature, Target, canonical


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_REFERENCE = re.compile(r'query=qCreatedBy\(makeId\("(Top|Right)"\), EntityType\.FACE\);\Z')
_TYPES = {"entities": "QueryList", "cplaneType": "Enum", "offset": "Quantity",
          "angle": "Quantity", "oppositeDirection": "Boolean", "flipAlignment": "Boolean",
          "flipNormal": "Boolean", "width": "Quantity", "height": "Quantity"}
_SOURCE_TYPES = {"QueryList": "148", "Enum": "145", "Quantity": "147", "Boolean": "144"}


def _source_plane(feature: Feature) -> tuple[str, str]:
    raw = feature.provenance.get("fsgen_feature_json")
    if (feature.kind != "cPlane" or not isinstance(raw, dict)
            or raw.get("btType") != "BTMFeature-134" or raw.get("featureType") != "cPlane"
            or raw.get("name") != feature.logical_id):
        raise Unsupported("Expected an original FSGen cPlane template")
    params = raw.get("parameters")
    if not isinstance(params, list) or any(not isinstance(p, dict) for p in params):
        raise Unsupported("Invalid plane source parameters")
    by_id = {p.get("parameterId"): p for p in params}
    if len(by_id) != len(params) or set(by_id) != set(_TYPES):
        raise Unsupported("Unsupported plane source parameter set")
    projection, schema = {}, {}
    for name, p in by_id.items():
        kind = _TYPES[name]
        if p.get("btType") != f"BTMParameter{kind}-{_SOURCE_TYPES[kind]}":
            raise Unsupported("Plane source parameter type mismatch")
        if kind == "QueryList":
            qs = p.get("queries")
            if (not isinstance(qs, list) or len(qs) != 1 or not isinstance(qs[0], dict)
                    or qs[0].get("btType") != "BTMIndividualQuery-138"):
                raise Unsupported("One source reference plane required")
            projection[name] = [qs[0].get("queryString")]
        else:
            key = "expression" if kind == "Quantity" else "value"
            if key not in p:
                raise Unsupported("Missing plane source parameter value")
            projection[name] = p[key]
        schema[name] = {k: v for k, v in p.items() if k not in {"expression", "value", "queries"}}
    if (canonical(projection) != canonical(feature.parameters)
            or canonical(schema) != canonical(feature.structure.get("parameter_schema"))
            or canonical({k: v for k, v in raw.items() if k != "parameters"})
            != canonical(feature.structure.get("fsgen_native"))):
        raise Unsupported("Plane source and semantic projection differ")
    if (projection["cplaneType"] != "OFFSET" or by_id["cplaneType"].get("enumName") != "CPlaneType"
            or any(projection[k] is not False for k in ("oppositeDirection", "flipAlignment", "flipNormal"))
            or projection["angle"] != "0 deg" or projection["width"] != "150 mm"
            or projection["height"] != "150 mm"):
        raise Unsupported("Only observed OFFSET plane defaults are supported")
    query = projection["entities"][0]
    match = _REFERENCE.fullmatch(query) if isinstance(query, str) else None
    expression = projection["offset"]
    if not match or not isinstance(expression, str) or not expression.strip() or len(expression) > 300:
        raise Unsupported("Unsupported reference plane or offset expression")
    if type(feature.provenance.get("source_line")) is not int or feature.provenance["source_line"] < 1:
        raise Unsupported("Plane source order is unavailable")
    return match[1], expression.strip()


def _linear_expression(expression: str) -> dict[str, Fraction]:
    """Length variables combined linearly with dimensionless numeric scalars."""
    if re.search(r"[A-Za-z_]", re.sub(r"#[A-Za-z][A-Za-z0-9_]*", "0", expression)):
        raise Unsupported("Only explicit source variables and numeric scalars are supported")
    translated = re.sub(r"#([A-Za-z][A-Za-z0-9_]*)", r"v_\1", expression)
    try:
        tree = ast.parse(translated, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise Unsupported("Unsupported symbolic plane offset") from exc
    if len(list(ast.walk(tree))) > 80:
        raise Unsupported("Plane expression is too complex")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not -1e12 <= node.value <= 1e12:
                raise Unsupported("Finite plane scalar required")
            return 0, {"": Fraction(str(node.value))}
        if isinstance(node, ast.Name) and re.fullmatch(r"v_[A-Za-z][A-Za-z0-9_]*", node.id):
            # Bare identifiers are not accepted as alternate variable syntax.
            if "#" + node.id[2:] not in expression:
                raise Unsupported("Explicit source variable reference required")
            return 1, {"#" + node.id[2:]: Fraction(1)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            dim, terms = visit(node.operand)
            sign = -1 if isinstance(node.op, ast.USub) else 1
            return dim, {k: sign * v for k, v in terms.items()}
        if isinstance(node, ast.BinOp):
            ld, left = visit(node.left)
            rd, right = visit(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)) and ld == rd:
                result = dict(left)
                for key, value in right.items():
                    result[key] = result.get(key, Fraction(0)) + (-value if isinstance(node.op, ast.Sub) else value)
                return ld, result
            if isinstance(node.op, ast.Mult) and ld + rd <= 1:
                if rd == 0:
                    return ld, {k: v * right[""] for k, v in left.items()}
                return rd, {k: v * left[""] for k, v in right.items()}
            if isinstance(node.op, ast.Div) and rd == 0 and right[""] != 0:
                return ld, {k: v / right[""] for k, v in left.items()}
        raise Unsupported("Only linear length-variable offsets with scalar arithmetic are supported")

    dim, terms = visit(tree.body)
    if dim != 1 or not terms or any(value == 0 for value in terms.values()):
        raise Unsupported("Offset requires nonzero length-variable coefficients")
    return terms


def stage_offset_plane(feature: Feature, *, variables: Sequence[Feature] = ()) -> dict[str, Any]:
    """Retain source expressions and state the positive-domain sign assumption."""
    reference, expression = _source_plane(feature)
    literal = re.fullmatch(rf"({_NUMBER})\s*mm", expression)
    assumptions = {}
    if literal:
        if feature.dependencies:
            raise Unsupported("Literal offset cannot have variable dependencies")
        signed_value = float(literal[1])
    else:
        terms = _linear_expression(expression)
        if set(terms) != set(feature.dependencies):
            raise Unsupported("Plane dependency list differs from offset expression")
        signs = {1 if value > 0 else -1 for value in terms.values()}
        if len(signs) != 1:
            raise Unsupported("Offset sign is not invariant over positive source variables")
        from .native import stage_length_variable
        supplied = {}
        for variable in variables:
            if variable.logical_id in supplied:
                raise Unsupported("Duplicate source variable")
            supplied[variable.logical_id] = variable
        for name in terms:
            if name not in supplied:
                raise Unsupported("Missing validated source variable")
            staged = stage_length_variable(supplied[name])
            value = float(staged["expression"].strip()[:-2])
            if not math.isfinite(value) or value <= 0:
                raise Unsupported("Symbolic plane offsets require strictly positive source variables")
            if staged["source_line"] >= feature.provenance["source_line"]:
                raise Unsupported("Plane variable must precede its use")
            assumptions[name] = {"expression": staged["expression"], "value_mm": value, "required_domain": "positive"}
        try:
            signed_value = sum(float(coef) * assumptions[name]["value_mm"] for name, coef in terms.items())
        except OverflowError as exc:
            raise Unsupported("Offset magnitude is outside the observed native range") from exc
    if not math.isfinite(signed_value) or abs(signed_value) > 500000:
        raise Unsupported("Offset magnitude is outside the observed native range")
    opposite = signed_value < 0
    magnitude = (f"{abs(signed_value):g} mm" if literal and opposite else
                 f"-({expression})" if opposite else expression)
    return {"logical_id": feature.logical_id, "reference_plane": reference,
            "source_expression": expression, "magnitude_expression": magnitude,
            "magnitude_mm": abs(signed_value), "opposite_direction": opposite,
            "dependencies": list(feature.dependencies), "positive_variable_assumptions": assumptions,
            "write_ready": False, "frame_verified": False}


def expected_offset_plane_tree(feature: Feature, before: dict, *, target: Target,
                               expected_revision: str, saved_tree: dict,
                               reference_binding: dict, variables: Sequence[Feature] = ()) -> dict:
    """Map into an explicitly fresh, UI-bound draft using same-revision query proof.

    ``reference_binding`` carries target, element_microversion, query and query_data
    from the caller's exact readback. No deterministic IDs are synthesized here.
    Caller must validate dependencies against live variables before any submission.
    """
    staged = stage_offset_plane(feature, variables=variables)
    if (any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{24}", value) for value in target.to_dict().values())
            or not isinstance(expected_revision, str) or not re.fullmatch(r"[a-f0-9]{24}", expected_revision)
            or before.get("target") != target.to_dict()
            or before.get("element_microversion") != expected_revision or before.get("connected") is not True):
        raise Unsupported("Exact connected plane target and revision required")
    tree = before.get("tree", {})
    children = tree.get("children")
    fid = before.get("editingFeatureId")
    if tree.get("$type") != "bsedit.GBTMModel" or not isinstance(children, list) or not fid:
        raise Unsupported("Fresh active plane draft required")
    matches = [n for n in children if n.get("featureId") == fid]
    if len(matches) != 1:
        raise Unsupported("Active plane identity is ambiguous")
    draft = matches[0]
    stripped = copy.deepcopy(tree)
    stripped["children"] = [n for n in stripped["children"] if n.get("featureId") != fid]
    if (stripped != saved_tree or any(n.get("featureId") == fid for n in saved_tree.get("children", []))
            or draft.get("$type") != "bsedit.GBTMFeature" or draft.get("featureType") != "cPlane"
            or not draft.get("nodeId") or draft.get("suppressed") is not False
            or draft.get("hasUserCode") is not False or draft.get("namespace") != ""
            or draft.get("subFeatures") != [] or draft.get("parameterLibraries") != []):
        raise Unsupported("Fresh plane draft or unchanged saved baseline required")
    params = draft.get("parameters", [])
    by_id = {p.get("parameterId"): p for p in params}
    if len(by_id) != len(params) or set(by_id) != set(_TYPES):
        raise Unsupported("Unexpected native plane parameter schema")
    for name, p in by_id.items():
        if (p.get("$type") != "bsedit.GBTMParameter" + _TYPES[name] or not p.get("nodeId")
                or p.get("hasUserCode") is not False):
            raise Unsupported("Native plane parameter type/identity differs")
    if by_id["cplaneType"].get("enumName") != "CPlaneType" or by_id["cplaneType"].get("value") != "OFFSET":
        raise Unsupported("Native OFFSET plane draft required")
    for name, expression, value, units in (("offset", "25 mm", 25, "millimeter"),
                                         ("angle", "0 deg", 0, "degree"),
                                         ("width", "150 mm", 150, "millimeter"),
                                         ("height", "150 mm", 150, "millimeter")):
        if any(by_id[name].get(k) != v for k, v in {"expression": expression, "value": value, "units": units}.items()):
            raise Unsupported("Plane draft must retain observed native defaults")
    if any(by_id[k].get("value") is not False for k in ("oppositeDirection", "flipAlignment", "flipNormal")):
        raise Unsupported("Plane draft direction differs from observed defaults")
    queries = by_id["entities"].get("queries")
    if not isinstance(queries, list) or len(queries) != 1:
        raise Unsupported("One UI-bound reference plane required")
    query = queries[0]
    qdata = reference_binding.get("query_data", {})
    details = qdata.get("evaluationDetails", {})
    ids = query.get("deterministicIds")
    if (reference_binding.get("target") != target.to_dict()
            or reference_binding.get("element_microversion") != expected_revision
            or reference_binding.get("query") != query
            or query.get("$type") != "bsedit.GBTMIndividualQuery" or not query.get("nodeId")
            or query.get("queryString") != "" or query.get("hasUserCode") is not False
            or not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or not ids[0]
            or qdata.get("$type") != "display.GBTQueryData" or qdata.get("deterministicIds") != ids
            or qdata.get("featureId") != staged["reference_plane"] or qdata.get("selectionName") != "Face"
            or qdata.get("hasErrorEntity") is not False or qdata.get("isTemporaryFakeDataForSelection") is not False
            or details.get("fullOperationId") != staged["reference_plane"] + ".planeOp"
            or details.get("entityType") != 2 or details.get("status") != 0
            or details.get("outsideExactDependencies") is not False):
        raise Unsupported("Exact same-revision reference-plane query proof required")
    result = copy.deepcopy(tree)
    output = next(n for n in result["children"] if n.get("featureId") == fid)
    for p in output["parameters"]:
        if p["parameterId"] == "offset":
            p.update(expression=staged["magnitude_expression"], value=staged["magnitude_mm"])
        elif p["parameterId"] == "oppositeDirection":
            p["value"] = staged["opposite_direction"]
    return {**staged, "feature_id": fid, "feature_node_id": draft["nodeId"], "expected_tree": result,
            "target": target.to_dict(), "expected_revision": expected_revision,
            "requires_live_dependency_verification": bool(staged["dependencies"])}


def _observed_row(journal, op_id, target_key, action):
    import json
    row = journal.get(op_id)
    if not row or row["target"] != target_key or row["action"] != action or row["state"] != "observed":
        raise Unsupported("Matching observed source journal operation required")
    intent, observation = json.loads(row["intent"]), json.loads(row["observation"] or "{}")
    if (observation.get("definition_observed") is not True
            or observation.get("feature_id") != intent.get("before_state", {}).get("editingFeatureId")):
        raise Unsupported("Saved source feature identity unverified")
    return row, intent, observation


def plane_population_intent(features, logical_id, before, baseline, binding, *, target,
                            previous_op_ids, variable_op_ids, journal):
    """Validate source order and journal-backed live identities before dispatch.

    Baseline is a connected saved-idle state captured BEFORE normal UI allocation.
    It may include arbitrary intervening sketches/extrudes; none are allocated here.
    """
    from .native import stage_length_variable
    variables = [f for f in features if f.kind == "assignVariable"]
    planes = [f for f in features if f.kind == "cPlane"]
    stages = [stage_offset_plane(f, variables=variables) for f in planes]
    variable_stages = [stage_length_variable(f) for f in variables]
    indices = [i for i, s in enumerate(stages) if s["logical_id"] == logical_id]
    if (len(indices) != 1 or len(previous_op_ids) != indices[0]
            or len(set(previous_op_ids)) != len(previous_op_ids)):
        raise Unsupported("Every preceding source plane operation required in order")
    index = indices[0]
    if (baseline.get("target") != target.to_dict() or baseline.get("connected") is not True
            or baseline.get("editingFeatureId", "missing") is not None
            or not re.fullmatch(r"[a-f0-9]{24}", str(baseline.get("element_microversion", "")))
            or baseline["element_microversion"] == before.get("element_microversion")
            or baseline.get("h2Readback", {}).get("incompleteFeatureEdit")):
        raise Unsupported("Pre-allocation saved idle baseline and target required")
    result = expected_offset_plane_tree(planes[index], before, target=target,
        expected_revision=before.get("element_microversion"), saved_tree=baseline.get("tree"),
        reference_binding=binding, variables=variables)
    children = baseline["tree"]["children"]
    key = "/".join(target.to_dict().values())
    identity_map = {}
    for i, op_id in enumerate(previous_op_ids):
        row, intent, observation = _observed_row(journal, op_id, key, "experimental_plane_populate")
        if (row["logical_id"] != stages[i]["logical_id"] or intent.get("source_stages") != stages
                or intent.get("source_index") != i):
            raise Unsupported("Preceding plane source provenance differs")
        fid = observation["feature_id"]
        expected = [n for n in intent["expected_tree"]["children"] if n.get("featureId") == fid]
        if len(expected) != 1 or [n for n in children if n.get("featureId") == fid] != expected:
            raise Unsupported("Previously saved plane definition changed")
        identity_map[row["logical_id"]] = fid
    dependencies = stages[index]["dependencies"]
    if set(variable_op_ids) != set(dependencies):
        raise Unsupported("Exact journal operation for every symbolic dependency required")
    variable_map = {}
    for name in dependencies:
        row, intent, observation = _observed_row(journal, variable_op_ids[name], key, "experimental_variable_populate")
        vi = next((i for i, s in enumerate(variable_stages) if s["logical_id"] == name), None)
        if (vi is None or row["logical_id"] != name or intent.get("source_stages") != variable_stages
                or intent.get("source_index") != vi):
            raise Unsupported("Dependency source definitions or journal provenance differ")
        fid = observation["feature_id"]
        expected = [n for n in intent["expected_tree"]["children"] if n.get("featureId") == fid]
        live = [n for n in children if n.get("featureId") == fid]
        if len(expected) != 1 or live != expected or live[0].get("featureType") != "assignVariable":
            raise Unsupported("Live dependency no longer matches verified source variable")
        p = {p["parameterId"]: p for p in live[0]["parameters"]}
        assumption = stages[index]["positive_variable_assumptions"][name]
        if (p.get("name", {}).get("value") != name[1:]
                or p.get("mode", {}).get("value") != "ASSIGNED"
                or p.get("variableType", {}).get("value") != "LENGTH"
                or any(p.get(k, {}).get("expression") != assumption["expression"]
                       or p[k].get("value") != assumption["value_mm"]
                       or p[k].get("units") != "millimeter" for k in ("value", "lengthValue"))):
            raise Unsupported("Live variable literal definition differs from positive source domain")
        variable_map[name] = fid
    if len(set([*identity_map.values(), *variable_map.values(), result["feature_id"]])) != len(identity_map) + len(variable_map) + 1:
        raise Unsupported("Source feature identities collide")
    return {"before_state": before, "baseline": baseline, "reference_binding": binding,
            "expected_tree": result["expected_tree"], "source_stages": stages, "source_index": index,
            "previous_op_ids": previous_op_ids, "identity_map": identity_map,
            "variable_op_ids": variable_op_ids, "variable_identity_map": variable_map,
            "variable_stages": variable_stages}


async def populate_test_plane(backend, target, source, *, logical_id, previous_op_ids,
                              baseline, reference_binding, variable_op_ids, journal):
    """Populate one normal-browser-allocated draft; never allocate or replay it."""
    from uuid import uuid4
    from .backend import UncertainWrite
    from .native import PreDispatchRejected, _confirm_pending_readback
    from .fsgen import compile_fsgen
    if target.to_dict() != backend.create_target or backend.tab_id is None:
        raise Unsupported("Plane population requires authorized temporary tab")
    features = compile_fsgen(source, target).features
    key = "/".join(target.to_dict().values())
    with journal.target_lock(key):
        if journal.has_unresolved():
            raise UncertainWrite("Prior write unresolved; reconcile before plane population")
        health = await backend.bridge.health()
        if (health.get("extension_connected") is not True
                or "h2_native_plane_populate_server_v1" not in health.get("capabilities", [])
                or "h2_native_plane_populate_page_v1" not in (health.get("extension") or {}).get("capabilities", [])
                or "h2_native_completion_receipt_page_v1" not in (health.get("extension") or {}).get("capabilities", [])):
            raise Unsupported("Paired plane population capability unavailable")
        before = await backend.raw_state(target)
        intent = plane_population_intent(features, logical_id, before, baseline, reference_binding,
            target=target, previous_op_ids=previous_op_ids, variable_op_ids=variable_op_ids, journal=journal)
        op_id = "plane-" + uuid4().hex
        journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                        action="experimental_plane_populate", logical_id=logical_id, intent=intent)
        stage = intent["source_stages"][intent["source_index"]]
        try:
            response = await backend.bridge.command({"kind": "partstudio_populate_plane", "op_id": op_id,
                "target": target.to_dict(), "tab_id": backend.tab_id,
                "expected_element_microversion": before["element_microversion"],
                "plane_edit": {"feature_id": before["editingFeatureId"],
                               "expression": stage["magnitude_expression"], "value": stage["magnitude_mm"],
                               "opposite_direction": stage["opposite_direction"],
                               "before_tree": before["tree"], "expected_tree": intent["expected_tree"]}})
        except PreDispatchRejected as exc:
            journal.transition(op_id, "rejected", error=str(exc))
            raise
        except Exception as exc:
            journal.transition(op_id, "unknown", error=str(exc))
            raise UncertainWrite(f"Plane outcome unknown; journal operation {op_id}") from exc
        if response.get("op_id") != op_id:
            journal.transition(op_id, "unknown", error="Plane receipt identity differs")
            raise UncertainWrite(f"Plane outcome unknown; journal operation {op_id}")
        journal.transition(op_id, "sent", receipt=response)
        return await _confirm_pending_readback(backend.bridge.reconcile_saved_source_plane,
                                               op_id, backend.tab_id, "Plane")
