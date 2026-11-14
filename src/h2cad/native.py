"""Independent adapter for the installed Onshape Native loopback bridge.

Only the editor RPC channel is admitted. Captured upstream messages are never
replayed, and observed message shapes are not treated as proven capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import copy
import json
import math
from pathlib import Path
import re
from uuid import uuid4
from typing import Any

import httpx

from .backend import BackendError, Capabilities, Receipt, Unsupported, UncertainWrite
from .model import Feature, Operation, Snapshot, Target
from .journal import Journal

_ID = re.compile(r"[a-f0-9]{24}\Z")


async def _confirm_pending_readback(confirm, op_id: str, tab_id: int, label: str) -> dict[str, Any]:
    """Retry only read-only exact-intent confirmation after an acknowledged write."""
    last_error = None
    for attempt in range(2):
        try:
            result = await confirm(op_id, tab_id)
            if result.get("op_id") != op_id or not isinstance(result.get("evidence"), dict):
                raise BackendError("Readback receipt does not match journal operation")
            return result["evidence"]
        except BackendError as exc:
            last_error = exc
            if attempt == 0:
                await asyncio.sleep(0.5)
    raise UncertainWrite(f"{label} saved-state confirmation pending; journal operation {op_id}") from last_error


_DISPOSABLE = {"did": "f5a8353dc826a9ec52106138", "wid": "a3baadfcc7e36a50134951d6", "eid": "a2761fa52794bee99354ae96"}
_NATIVE_CREATE_TEST = {"did": "4e078dec822b4e509616b1cb", "wid": "af0627de07264acf086e646a", "eid": "9a062f0eef8bb961f8c84f8e"}
_NATIVE_CREATE_PROJECT = {"did": _NATIVE_CREATE_TEST["did"], "wid": _NATIVE_CREATE_TEST["wid"]}
_PRESERVED_CREATE_EIDS = {"45730d1931712e2c548fae00", "39a2e2afc5bc43eea167e938"}


def _configured_create_target(value: Any) -> dict[str, str]:
    if (not isinstance(value, dict) or set(value) != {"did", "wid", "eid"}
            or {key: value[key] for key in ("did", "wid")} != _NATIVE_CREATE_PROJECT
            or not isinstance(value["eid"], str) or not _ID.fullmatch(value["eid"])
            or value["eid"] in _PRESERVED_CREATE_EIDS):
        raise ValueError("Native creation target must be an explicitly bound test Part Studio in the authorized project")
    return dict(value)


class PreDispatchRejected(BackendError):
    """The paired page adapter attested that no modeling RPC was sent."""


@dataclass(frozen=True)
class PreparedCommand:
    command: str
    body: dict[str, Any]
    expected_element_microversion: str
    evidence: str


@dataclass(frozen=True)
class NativePairBlueprint:
    """Validated semantics for one literal Top-plane rectangle and blind solid."""

    sketch_logical_id: str
    extrusion_logical_id: str
    plane_name: str
    rectangle_m: tuple[float, float, float, float]
    depth_mm: float

    def to_dict(self) -> dict[str, Any]:
        return {"sketch_logical_id": self.sketch_logical_id,
                "extrusion_logical_id": self.extrusion_logical_id,
                "plane_name": self.plane_name,
                "rectangle_m": list(self.rectangle_m), "depth_mm": self.depth_mm,
                "write_ready": False,
                "missing_live_bindings": ["fresh feature ID allocator", "Top plane query binding",
                                          "sketch region query binding", "native feature regeneration proof"]}


def _validate_fsgen_rectangle(body: dict[str, Any], xy: tuple[float, float, float, float]) -> None:
    """Require the actual FSGen entities and constraints to match the summary."""
    x0, y0, x1, y1 = xy
    if x0 != 0 or y0 != 0:
        raise Unsupported("First native rectangle requires an origin anchor")
    entities = body.get("entities")
    constraints = body.get("constraints")
    if not isinstance(entities, list) or len(entities) != 4 or not isinstance(constraints, list) or len(constraints) != 11:
        raise Unsupported("First native rectangle requires four lines and eleven supported constraints")
    first_id = entities[0].get("entityId") if isinstance(entities[0], dict) else None
    prefix = first_id[:-7] if isinstance(first_id, str) and first_id.endswith(".bottom") else None
    if not prefix or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", prefix):
        raise Unsupported("Rectangle entity IDs are unsupported")
    specs = [("bottom", x0, y0, 1, 0, x1-x0), ("right", x1, y0, 0, 1, y1-y0),
             ("top", x1, y1, -1, 0, x1-x0), ("left", x0, y1, 0, -1, y1-y0)]
    for entity, (side, px, py, dx, dy, distance) in zip(entities, specs):
        if not isinstance(entity, dict) or entity.get("btType") != "BTMSketchCurveSegment-155" or entity.get("isConstruction") is not False:
            raise Unsupported("Rectangle line entity type or construction state differs")
        ident = f"{prefix}.{side}"
        if (entity.get("entityId") != ident or entity.get("startPointId") != ident + ".start"
                or entity.get("endPointId") != ident + ".end"):
            raise Unsupported("Rectangle line identity differs")
        geometry = entity.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("btType") != "BTCurveGeometryLine-117":
            raise Unsupported("Rectangle line geometry type differs")
        expected = {"startParam": 0, "endParam": distance,
                    "pntX": px, "pntY": py, "dirX": dx, "dirY": dy}
        for key, value in expected.items():
            actual = geometry.get(key) if key.startswith(("pnt", "dir")) else entity.get(key)
            if type(actual) not in (int, float) or not math.isfinite(actual) or not math.isclose(actual, value, rel_tol=0, abs_tol=1e-12):
                raise Unsupported(f"Rectangle line {side} {key} differs from summary")

    observed: list[tuple[Any, ...]] = []
    constraint_ids: set[str] = set()
    for constraint in constraints:
        if not isinstance(constraint, dict) or constraint.get("btType") != "BTMSketchConstraint-2" or not isinstance(constraint.get("parameters"), list):
            raise Unsupported("Rectangle constraint type differs")
        ident = constraint.get("entityId")
        if not isinstance(ident, str) or not ident or ident in constraint_ids:
            raise Unsupported("Rectangle constraint IDs are absent or duplicated")
        constraint_ids.add(ident)
        params = constraint["parameters"]
        by_id = {p.get("parameterId"): p for p in params if isinstance(p, dict)}
        if len(by_id) != len(params) or any(not isinstance(p, dict) or not isinstance(p.get("parameterId"), str) for p in params):
            raise Unsupported("Rectangle constraint parameters are ambiguous")
        kind = constraint.get("constraintType")
        if kind in {"COINCIDENT", "HORIZONTAL", "VERTICAL"}:
            first = by_id.get("localFirst")
            if not first or first.get("btType") != "BTMParameterString-149":
                raise Unsupported("Rectangle constraint local reference differs")
            second = by_id.get("localSecond")
            external = by_id.get("externalSecond")
            if second and second.get("btType") != "BTMParameterString-149":
                raise Unsupported("Rectangle coincidence reference differs")
            if external and (external.get("btType") != "BTMParameterQueryList-148" or
                             external.get("queries") != [{"btType": "BTMIndividualQuery-138",
                                                       "queryString": 'query=qCreatedBy(makeId("Origin"), EntityType.VERTEX);'}]):
                raise Unsupported("Rectangle origin anchor differs")
            if set(by_id) != ({"localFirst", "externalSecond"} if external else {"localFirst", "localSecond"} if second else {"localFirst"}):
                raise Unsupported("Rectangle constraint has extra parameters")
            observed.append((kind, first.get("value"), second.get("value") if second else None, bool(external)))
        elif kind == "DISTANCE":
            if set(by_id) != {"localFirst", "localSecond", "direction", "length"}:
                raise Unsupported("Rectangle distance dimension differs")
            if (by_id["localFirst"].get("btType") != "BTMParameterString-149" or
                    by_id["localSecond"].get("btType") != "BTMParameterString-149" or
                    by_id["direction"].get("btType") != "BTMParameterEnum-145" or
                    by_id["direction"].get("enumName") != "DimensionDirection" or
                    by_id["length"].get("btType") != "BTMParameterQuantity-147"):
                raise Unsupported("Rectangle dimension parameter schema differs")
            observed.append(("DISTANCE", by_id["localFirst"].get("value"), by_id["localSecond"].get("value"),
                             by_id["direction"].get("value"), by_id["length"].get("expression")))
        else:
            raise Unsupported("Rectangle contains an unsupported constraint")
    expected_constraints = [
        ("COINCIDENT", f"{prefix}.bottom.start", f"{prefix}.left.end", False),
        ("COINCIDENT", f"{prefix}.bottom.end", f"{prefix}.right.start", False),
        ("COINCIDENT", f"{prefix}.right.end", f"{prefix}.top.start", False),
        ("COINCIDENT", f"{prefix}.top.end", f"{prefix}.left.start", False),
        ("COINCIDENT", f"{prefix}.bottom.start", None, True),
        ("HORIZONTAL", f"{prefix}.bottom", None, False),
        ("HORIZONTAL", f"{prefix}.top", None, False),
        ("VERTICAL", f"{prefix}.right", None, False),
        ("VERTICAL", f"{prefix}.left", None, False),
        ("DISTANCE", f"{prefix}.bottom.start", f"{prefix}.bottom.end", "HORIZONTAL", f"{(x1-x0)*1000:g} mm"),
        ("DISTANCE", f"{prefix}.right.start", f"{prefix}.right.end", "VERTICAL", f"{(y1-y0)*1000:g} mm")]
    if sorted(map(repr, observed)) != sorted(map(repr, expected_constraints)):
        raise Unsupported("Rectangle constraints contradict entity geometry or dimensions")


def stage_minimal_pair(snapshot: Snapshot) -> NativePairBlueprint:
    """Normalize the first real FSGen plan without treating REST JSON as RPC."""
    if not snapshot.complete or len(snapshot.features) != 2:
        raise Unsupported("First native pair requires exactly one sketch and one extrusion")
    sketch, extrusion = snapshot.features
    if (sketch.kind != "newSketch" or extrusion.kind != "extrude"
            or extrusion.dependencies != (sketch.logical_id,)
            or sketch.dependencies or sketch.native_id or extrusion.native_id):
        raise Unsupported("First native pair requires new sketch then dependent extrusion")
    shape = sketch.structure.get("sketch")
    rectangle = shape.get("rectangle") if isinstance(shape, dict) else None
    if not isinstance(rectangle, dict) or shape.get("plane_name") != "Top":
        raise Unsupported("First native pair requires a Top-plane rectangle")
    xy = tuple(rectangle.get(key) for key in ("x0", "y0", "x1", "y1"))
    if (any(type(v) not in (int, float) or not math.isfinite(v) for v in xy)
            or not xy[0] < xy[2] or not xy[1] < xy[3]
            or rectangle.get("construction") is not False):
        raise Unsupported("Rectangle coordinates must be finite, ordered, and nonconstruction")
    sketch_body = sketch.structure.get("fsgen_native")
    if (not isinstance(sketch_body, dict) or sketch_body.get("featureType") != "newSketch"
            or sketch_body.get("name") != sketch.logical_id
            or not isinstance(sketch_body.get("entities"), list) or len(sketch_body["entities"]) != 4
            or not isinstance(sketch_body.get("constraints"), list)
            or sketch.parameters.get("sketchPlane") != ['query=qCreatedBy(makeId("Top"), EntityType.FACE);']):
        raise Unsupported("FSGen sketch entities, constraints, or Top query differ")
    _validate_fsgen_rectangle(sketch_body, xy)
    sketch_schema = sketch.structure.get("parameter_schema")
    extrusion_schema = extrusion.structure.get("parameter_schema")
    if (not isinstance(sketch_schema, dict) or not isinstance(extrusion_schema, dict)
            or not isinstance(sketch_schema.get("sketchPlane"), dict)
            or not isinstance(extrusion_schema.get("entities"), dict)
            or not isinstance(extrusion_schema.get("depth"), dict)
            or sketch_schema["sketchPlane"].get("btType") != "BTMParameterQueryList-148"
            or extrusion_schema["entities"].get("btType") != "BTMParameterQueryList-148"
            or extrusion_schema["depth"].get("btType") != "BTMParameterQuantity-147"):
        raise Unsupported("FSGen parameter schema differs from the supported pair")
    if (extrusion.parameters.get("bodyType") != "SOLID"
            or extrusion.parameters.get("operationType") != "NEW"
            or extrusion.parameters.get("endBound") != "BLIND"
            or extrusion.parameters.get("entities") != [f'query=qSketchRegion(makeId("{sketch.logical_id}"));']):
        raise Unsupported("Extrusion mode or sketch-region dependency differs")
    depth = extrusion.parameters.get("depth")
    match = re.fullmatch(r"(\d+(?:\.\d+)?) mm", depth) if isinstance(depth, str) else None
    if not match or not 0 < (depth_mm := float(match.group(1))) <= 1000:
        raise Unsupported("First native pair requires a literal positive millimeter depth")
    return NativePairBlueprint(sketch.logical_id, extrusion.logical_id, "Top", xy, depth_mm)


def _live_rectangle_feature(state: dict[str, Any], blueprint: NativePairBlueprint,
                            *, feature_id: str | None = None) -> dict[str, Any]:
    """Bind an active editor sketch and evaluate its four native line segments."""
    tree = state.get("tree")
    if (state.get("connected") is not True or not isinstance(tree, dict)
            or tree.get("$type") != "bsedit.GBTMModel" or not isinstance(tree.get("children"), list)):
        raise Unsupported("Active Part Studio tree is unavailable")
    feature_id = feature_id or state.get("editingFeatureId")
    matches = [node for node in tree["children"] if isinstance(node, dict)
               and node.get("featureId") == feature_id and node.get("featureType") == "newSketch"]
    if len(matches) != 1 or not isinstance(feature_id, str) or not feature_id or not matches[0].get("nodeId"):
        raise Unsupported("Exactly one active native sketch is required")
    sketch = matches[0]
    plane = [p for p in sketch.get("parameters", []) if isinstance(p, dict) and p.get("parameterId") == "sketchPlane"]
    if (len(plane) != 1 or plane[0].get("$type") != "bsedit.GBTMParameterQueryList"
            or not isinstance(plane[0].get("queries"), list) or len(plane[0]["queries"]) != 1
            or not isinstance(plane[0]["queries"][0], dict)
            or plane[0]["queries"][0].get("$type") != "bsedit.GBTMIndividualQuery"
            or not plane[0]["queries"][0].get("deterministicIds")):
        raise Unsupported("Active sketch lacks one editor-bound plane query")
    entities = sketch.get("entities")
    if not isinstance(entities, list) or len(entities) != 4:
        raise Unsupported("Active sketch requires exactly four native line entities")
    prefix = None
    x0, y0, x1, y1 = blueprint.rectangle_m
    expected = {"bottom": ((x0, y0), (x1, y0)), "right": ((x1, y0), (x1, y1)),
                "top": ((x0, y1), (x1, y1)), "left": ((x0, y0), (x0, y1))}
    seen: set[str] = set()
    for entity in entities:
        if not isinstance(entity, dict) or entity.get("$type") != "bsedit.GBTMSketchCurveSegment" or entity.get("isConstruction") is not False:
            raise Unsupported("Native rectangle contains an unsupported entity")
        ident = entity.get("entityId")
        if not isinstance(ident, str) or "." not in ident:
            raise Unsupported("Native rectangle entity ID is absent")
        current_prefix, side = ident.rsplit(".", 1)
        if (prefix is not None and current_prefix != prefix) or side not in expected or side in seen:
            raise Unsupported("Native rectangle entity IDs do not form one rectangle")
        prefix = current_prefix
        seen.add(side)
        geometry = entity.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("$type") != "bsedit.GBTCurveGeometryLine":
            raise Unsupported("Native rectangle line geometry is unavailable")
        values = [geometry.get(k) for k in ("pntX", "pntY", "dirX", "dirY")] + [entity.get(k) for k in ("startParam", "endParam")]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise Unsupported("Native rectangle line coordinates are invalid")
        px, py, dx, dy, start, end = values
        endpoints = ((px + start*dx, py + start*dy), (px + end*dx, py + end*dy))
        if not all(math.isclose(actual[0], wanted[0], rel_tol=0, abs_tol=1e-8)
                   and math.isclose(actual[1], wanted[1], rel_tol=0, abs_tol=1e-8)
                   for actual, wanted in zip(sorted(endpoints), sorted(expected[side]))):
            raise Unsupported("Native rectangle endpoints differ from FSGen plan")
    if seen != set(expected):
        raise Unsupported("Native rectangle is incomplete")
    return sketch


def _native_rectangle_constraints(sketch: dict[str, Any], blueprint: NativePairBlueprint) -> None:
    """Check native equivalent geometry constraints and editable dimensions."""
    entities = sketch["entities"]
    prefix = entities[0]["entityId"].rsplit(".", 1)[0]
    constraints = sketch.get("constraints")
    if not isinstance(constraints, list) or len(constraints) != 11:
        raise Unsupported("Native rectangle lacks eleven editor constraints")
    observed: set[tuple[Any, ...]] = set()
    ids: set[str] = set()
    for constraint in constraints:
        if not isinstance(constraint, dict) or constraint.get("$type") != "bsedit.GBTMSketchConstraint":
            raise Unsupported("Native constraint type unavailable")
        ident = constraint.get("entityId")
        if not isinstance(ident, str) or not ident.startswith(prefix + ".") or ident in ids:
            raise Unsupported("Native constraint identity duplicated or outside sketch")
        ids.add(ident)
        params = constraint.get("parameters")
        if not isinstance(params, list) or any(not isinstance(p, dict) for p in params):
            raise Unsupported("Native constraint parameters unavailable")
        by_id = {p.get("parameterId"): p for p in params}
        if len(by_id) != len(params):
            raise Unsupported("Native constraint parameter IDs duplicated")
        kind = constraint.get("constraintType")
        first = by_id.get("localFirst")
        second = by_id.get("localSecond")
        if not isinstance(first, dict) or first.get("$type") != "bsedit.GBTMParameterString":
            raise Unsupported("Native local constraint reference unavailable")
        if second is not None and second.get("$type") != "bsedit.GBTMParameterString":
            raise Unsupported("Native second constraint reference unavailable")
        if kind in {1, 2, 4, 5, 16}:
            if set(by_id) != ({"localFirst", "localSecond"} if second else {"localFirst"}):
                raise Unsupported("Native geometric constraint has extra fields")
            observed.add((kind, first.get("value"), second.get("value") if second else None))
        elif kind == 11:
            if set(by_id) != {"localFirst", "direction", "length", "alignment", "labelRatio", "labelDistance"}:
                raise Unsupported("Native dimension schema differs")
            length = by_id["length"]
            if (length.get("$type") != "bsedit.GBTMParameterQuantity"
                    or length.get("units") != "millimeter"
                    or by_id["direction"].get("value") != "MINIMUM"
                    or by_id["alignment"].get("value") != "ALIGNED"):
                raise Unsupported("Native editable dimension differs")
            observed.add(("dimension", first.get("value"), length.get("value"), length.get("expression")))
        else:
            raise Unsupported("Native rectangle contains unsupported constraint")
    x0, y0, x1, y1 = blueprint.rectangle_m
    expected = {(16, f"{prefix}.bottom.start", None),
                (5, f"{prefix}.top", f"{prefix}.left"),
                (2, f"{prefix}.bottom", f"{prefix}.top"),
                (2, f"{prefix}.left", f"{prefix}.right"),
                (4, f"{prefix}.top", None),
                (1, f"{prefix}.bottom.start", f"{prefix}.left.start"),
                (1, f"{prefix}.bottom.end", f"{prefix}.right.start"),
                (1, f"{prefix}.top.start", f"{prefix}.left.end"),
                (1, f"{prefix}.top.end", f"{prefix}.right.end"),
                ("dimension", f"{prefix}.top", (x1-x0)*1000, f"{(x1-x0)*1000:g} mm"),
                ("dimension", f"{prefix}.right", (y1-y0)*1000, f"{(y1-y0)*1000:g} mm")}
    if observed != expected:
        raise Unsupported("Native constraints or dimensions differ from FSGen rectangle")


def _verify_rectangle_graph(payload: dict[str, Any], prefix: str) -> None:
    """Require a solved origin anchor and all eleven supported constraints."""
    graph = payload.get("result")
    if not isinstance(graph, dict) or graph.get("$type") != "ui.sketch.GBTUiSketchGetConstraintGraphResponse":
        raise Unsupported("Native sketch constraint graph unavailable")
    constraints = graph.get("constraints")
    refs = graph.get("references")
    names = {f"{prefix}.{name}" for name in ("fixedOrigin", "perpendicular", "parallel.1", "parallel.2",
                                                "horizontal", "corner0", "corner1", "corner2", "corner3", "width", "height")}
    if (not isinstance(constraints, dict) or set(constraints) != names
            or any(node.get("status") != 4 or node.get("displayStatus") != 1 for node in constraints.values())
            or graph.get("worstSolveStatus") != 1
            or graph.get("sketchError", {}).get("statusEnum") != 0
            or not isinstance(refs, dict)):
        raise Unsupported("Native sketch constraint solver did not confirm all eleven constraints")
    fixed = constraints[f"{prefix}.fixedOrigin"]
    if (fixed.get("isExternal") is not False or fixed.get("type") != 16
            or fixed.get("referenceIds") != [f"{prefix}.bottom.start"]):
        raise Unsupported("Native fixed origin point is not internally constrained")
    start = refs.get(f"{prefix}.bottom.start")
    if (not isinstance(start, dict) or start.get("isSketchEntity") is not True
            or start.get("worstSolveStatus") != 1
            or any(type(start.get(k)) not in (int, float) or not math.isclose(start[k], 0, abs_tol=1e-8)
                   for k in ("anchorX", "anchorY", "anchorZ"))):
        raise Unsupported("Native rectangle start is not solved at the origin")


def _verify_source_region_query(payload: dict[str, Any], query: dict[str, Any], sketch_id: str) -> None:
    """Resolve one editor-created region query to the unique source rectangle."""
    result = payload.get("result")
    data = result.get("queryData") if isinstance(result, dict) else None
    if (not isinstance(result, dict) or result.get("$type") != "ui.GBTUiGetQueryDataResponse"
            or not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict)
            or data[0].get("deterministicIds") != query.get("deterministicIds")
            or data[0].get("featureId") != sketch_id
            or not query.get("deterministicIds")
            or data[0].get("evaluationDetails", {}).get("status") != 0
            or data[0].get("hasErrorEntity") is not False):
        raise Unsupported("Extrusion region does not resolve to the source sketch")
    item = data[0]
    detail = item["evaluationDetails"]
    canvas_face = (query.get("$type") == "bsedit.GBTMIndividualQuery"
                   and item.get("selectionName") == "Face"
                   and detail.get("fullOperationId") == f"{sketch_id}.imprint"
                   and detail.get("entityType") == 2)
    sole_sketch_region = (query.get("$type") == "bsedit.GBTMIndividualSketchRegionQuery"
                          and query.get("featureId") == sketch_id
                          and query.get("filterInnerLoops") is True
                          and item.get("selectionName") == "Faces"
                          and detail.get("fullOperationId") == ""
                          and detail.get("entityType") == 0)
    if not (canvas_face or sole_sketch_region):
        raise Unsupported("Extrusion query is not a supported source face or unique sketch region")


def _native_model_metadata(tree: dict[str, Any]) -> dict[str, Any]:
    """Compare CAD model metadata while ignoring one observed per-tab schema ID."""
    metadata = copy.deepcopy({key: value for key, value in tree.items() if key != "children"})
    annotations = metadata.get("modelAnnotations")
    tolerance = annotations.get("toleranceSchemaForParts") if isinstance(annotations, dict) else None
    if isinstance(tolerance, dict) and isinstance(tolerance.get("nodeId"), str) and tolerance["nodeId"]:
        tolerance["nodeId"] = "<per-tab-tolerance-schema-node>"
    return metadata


class NativeBridge:
    """HTTP client for an already running, separately installed companion."""

    def __init__(self, token: str, *, port: int = 8766, transport: httpx.AsyncBaseTransport | None = None):
        if not token or len(token) < 32 or port != 8766:
            raise ValueError("Expected installed companion token and fixed loopback port 8766")
        self.http = httpx.AsyncClient(base_url="http://127.0.0.1:8766", trust_env=False,
                                      headers={"Authorization": f"Bearer {token}"}, transport=transport,
                                      timeout=60)

    @classmethod
    def from_config(cls, path: str | Path, **kwargs: Any) -> "NativeBridge":
        config = json.loads(Path(path).read_text(encoding="utf-8"))
        if config.get("host") != "127.0.0.1" or config.get("port") != 8766:
            raise ValueError("Unexpected bridge host or port")
        bridge = cls(config["token"], **kwargs)
        bridge.create_target = _configured_create_target(config.get("h2cad_create_target", _NATIVE_CREATE_TEST))
        return bridge

    async def close(self) -> None:
        await self.http.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            response = await self.http.get("/health")
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendError("Installed native bridge unavailable") from exc
        if not isinstance(data, dict) or data.get("protocol") != 1:
            raise BackendError("Unknown native bridge protocol")
        return data

    async def reload_extension(self) -> dict[str, Any]:
        """Ask the paired bridge for one own-worker reload; never submit a CAD job."""
        try:
            response = await self.http.post("/local/extension_reload", timeout=30)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendError("Reload outcome uncertain; inspect the paired extension before another request") from exc
        if response.status_code != 200 or not isinstance(data, dict) or not isinstance(data.get("status"), str):
            raise BackendError("Bridge did not return a structured reload result")
        return data

    async def reconcile_known_sketch_rejection(self, op_id: str, tab_id: int) -> dict[str, Any]:
        """Resolve only the reviewed pre-RPC constructor rejection via the paired bridge."""
        try:
            response = await self.http.post("/local/reconcile_known_sketch_rejection",
                                            json={"op_id": op_id, "tab_id": tab_id}, timeout=30)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendError("Known sketch recovery unavailable; safety barrier remains") from exc
        if response.status_code != 200 or data.get("status") != "rejected_pre_dispatch":
            raise BackendError(str(data.get("reason", "Known sketch recovery was refused")))
        return data

    async def reconcile_completed_top_begin(self, op_id: str, tab_id: int) -> dict[str, Any]:
        """Resolve a finished Top binding or a saved blank partial begin."""
        try:
            response = await self.http.post("/local/reconcile_completed_top_begin",
                                            json={"op_id": op_id, "tab_id": tab_id}, timeout=30)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendError("Top begin reconciliation unavailable; safety barrier remains") from exc
        if response.status_code != 200 or data.get("status") not in {
                "observed_manual_top_completion", "observed_partial_top_begin"}:
            raise BackendError(str(data.get("reason", "Top begin reconciliation refused")))
        return data

    async def reconcile_completed_source_sketch(self, op_id: str, tab_id: int) -> dict[str, Any]:
        """Verify saved source geometry after a manual completion of its active edit."""
        try:
            response = await self.http.post("/local/reconcile_completed_source_sketch",
                                            json={"op_id": op_id, "tab_id": tab_id}, timeout=30)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendError("Source sketch reconciliation unavailable; safety barrier remains") from exc
        if response.status_code != 200 or data.get("status") not in {"observed_manual_source_completion", "observed_delayed_source_sketch"}:
            raise BackendError(str(data.get("reason", "Source sketch reconciliation refused")))
        return data

    async def reconcile_saved_source_extrude(self, op_id: str, tab_id: int) -> dict[str, Any]:
        """Verify an eventually saved source extrusion without replaying it."""
        try:
            response = await self.http.post("/local/reconcile_saved_source_extrude",
                                            json={"op_id": op_id, "tab_id": tab_id}, timeout=30)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendError("Source extrusion reconciliation unavailable; safety barrier remains") from exc
        if response.status_code != 200 or data.get("status") not in {"observed_delayed_source_extrusion", "observed_source_extrusion"}:
            raise BackendError(str(data.get("reason", "Source extrusion reconciliation refused")))
        return data

    async def finalize_known_invalid_sketch_cancel(self, op_id: str, tab_id: int) -> dict[str, Any]:
        """Verify UI rollback of the one applied-invalid sketch and release its guard."""
        try:
            response = await self.http.post("/local/finalize_known_invalid_sketch_cancel",
                                            json={"op_id": op_id, "tab_id": tab_id}, timeout=30)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendError("Known invalid sketch rollback inspection unavailable; barrier remains") from exc
        if response.status_code != 200 or data.get("status") != "rejected_after_rollback":
            raise BackendError(str(data.get("reason", "Known invalid sketch rollback refused")))
        return data

    async def command(self, job: dict[str, Any]) -> dict[str, Any]:
        if job.get("kind") not in {"state", "schema", "creation_probe", "native", "partstudio_depth_edit", "partstudio_begin_top_sketch", "partstudio_begin_source_extrude", "partstudio_populate_sketch", "partstudio_populate_extrude"}:
            raise Unsupported("Browser-mode adapter permits only native editor jobs")
        try:
            response = await self.http.post("/command", json=job)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UncertainWrite("Native bridge response unavailable; inspect before further mutation") from exc
        if isinstance(data, dict) and data.get("error"):
            diagnostic = ""
            if (data.get("read_phase") in {"extension_received", "tab_lookup", "page_script",
                                           "page_reply", "response_transfer"}
                    and type(data.get("elapsed_ms")) is int and 0 <= data["elapsed_ms"] <= 60000):
                diagnostic = f" [read_phase={data['read_phase']}, elapsed_ms={data['elapsed_ms']}]"
            if (job.get("kind") in {"partstudio_begin_top_sketch", "partstudio_begin_source_extrude", "partstudio_populate_sketch", "partstudio_populate_extrude"}
                    and data.get("write_stage") == "pre_dispatch"):
                raise PreDispatchRejected(str(data["error"]))
            if job.get("kind") in {"partstudio_depth_edit", "partstudio_begin_top_sketch", "partstudio_begin_source_extrude", "partstudio_populate_sketch", "partstudio_populate_extrude"}:
                raise UncertainWrite(str(data["error"]))
            raise BackendError(str(data["error"]) + diagnostic)
        if response.status_code != 200 or not isinstance(data, dict):
            raise BackendError(f"Native bridge rejected command (HTTP {response.status_code})")
        return data


def _target(target: Target) -> dict[str, str]:
    fields = {"did": target.did, "wid": target.wid, "eid": target.eid}
    if any(not isinstance(value, str) or not _ID.fullmatch(value) for value in fields.values()):
        raise ValueError("Native target requires exact 24-hex workspace IDs")
    return fields


def _schema_fields(defaults: dict[str, Any], required: set[str]) -> None:
    missing = required - defaults.keys()
    if missing:
        raise Unsupported("Runtime serializer lacks fields: " + ", ".join(sorted(missing)))


def stage_rectangle(feature: Feature, *, bindings: dict[str, Any], schema: dict[str, Any]) -> PreparedCommand:
    """Compile one native sketch entity only after the editor supplied live IDs.

    This is a typed command stage, not a complete create-sketch transaction.
    """
    sketch = feature.structure.get("sketch", {})
    rectangle = sketch.get("rectangle") if isinstance(sketch, dict) else None
    if feature.kind not in {"sketch", "newSketch"} or not isinstance(rectangle, dict):
        raise Unsupported("Expected semantic sketch.rectangle geometry")
    coordinates = tuple(rectangle.get(k) for k in ("x0", "y0", "x1", "y1"))
    if (any(type(v) not in (float, int) or not math.isfinite(v) for v in coordinates)
            or coordinates[0] == coordinates[2] or coordinates[1] == coordinates[3]
            or type(rectangle.get("construction", False)) is not bool):
        raise Unsupported("Rectangle needs nondegenerate numeric editor-plane coordinates in meters")
    if bindings.get("provenance") != "live_editor":
        raise Unsupported("Sketch entity and inference IDs must come from a live editor allocator")
    for key in ("sketch_feature_id", "sketch_entity_id", "inference_set_id", "element_microversion"):
        if not isinstance(bindings.get(key), str) or not bindings[key]:
            raise Unsupported(f"Missing live editor binding: {key}")
    if not _ID.fullmatch(bindings["element_microversion"]):
        raise Unsupported("Invalid live element revision")
    name = "ui.sketch.GBTUiSketchAddRectangleCall"
    if schema.get("name") != name or not isinstance(schema.get("defaults"), dict):
        raise Unsupported("Runtime rectangle schema unavailable")
    defaults = schema["defaults"]
    fields = {"firstX", "firstY", "oppositeX", "oppositeY", "sketchEntityId", "inferenceSetId", "isConstruction"}
    _schema_fields(defaults, fields)
    body = {"firstX": coordinates[0], "firstY": coordinates[1], "oppositeX": coordinates[2],
            "oppositeY": coordinates[3], "sketchEntityId": bindings["sketch_entity_id"],
            "inferenceSetId": bindings["inference_set_id"],
            "isConstruction": rectangle.get("construction", False)}
    return PreparedCommand(name, body, bindings["element_microversion"],
                           "typed runtime schema and live editor bindings; full transaction unverified")


def stage_extrusion(feature: Feature, *, bindings: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Validate semantic extrusion input and report the remaining native bindings.

    No AddFeature message is constructed until a live feature-settings response
    establishes parameter IDs and a region query at the current revision.
    """
    if feature.kind not in {"extrude", "extrusion"}:
        raise Unsupported("Expected semantic extrusion")
    value = feature.parameters.get("depth")
    if not isinstance(value, str) or not value.strip():
        raise Unsupported("Extrusion requires an explicit depth expression")
    if not feature.dependencies:
        raise Unsupported("Extrusion must depend on a sketch logical ID")
    if schema.get("name") != "ui.GBTUiAddFeatureCall" or not isinstance(schema.get("defaults"), dict):
        raise Unsupported("Runtime AddFeature schema unavailable")
    _schema_fields(schema["defaults"], {"newFeature", "editDescription", "rollbackState"})
    required = ("feature_settings", "insertion_location", "sketch_region_query", "element_microversion", "id_allocator")
    missing = [key for key in required if key not in bindings]
    return {"kind": "extrude", "depth": value, "sketch_logical_id": feature.dependencies[0],
            "missing_live_bindings": missing, "ready_to_submit": False,
            "reason": "Native feature definition and regeneration readback remain unverified"}


class NativeBackend:
    def __init__(self, bridge: NativeBridge, *, tab_id: int | None = None):
        self.bridge = bridge
        self.tab_id = tab_id
        self.create_target = _configured_create_target(getattr(bridge, "create_target", _NATIVE_CREATE_TEST))

    async def capabilities(self) -> Capabilities:
        health = await self.bridge.health()
        extension = health.get("extension") or {}
        flags = frozenset(extension.get("capabilities") or ())
        if not health.get("extension_connected"):
            raise BackendError("Onshape Native extension is not connected")
        return Capabilities(category="browser_native_rpc", supported_kinds=frozenset(), atomic_revision=False,
                            verification=frozenset(), evidence={"bridge_protocol": health["protocol"],
                            "extension_version": extension.get("version"), "extension_capabilities": sorted(flags),
                            "sketch_extrusion": "observed-only; no supported write capability"})

    async def read(self, target: Target) -> Snapshot:
        data = await self.raw_state(target)
        revision = data["element_microversion"]
        # The raw editor tree has no stable, complete feature definition/status
        # normalization contract yet. Preserve the revision but fail verification.
        return Snapshot(target=target, revision=revision, features=(), complete=False)

    async def raw_state(self, target: Target) -> dict[str, Any]:
        job: dict[str, Any] = {"kind": "state", "target": _target(target)}
        if self.tab_id is not None:
            job["tab_id"] = self.tab_id
        data = await self.bridge.command(job)
        revision = data.get("element_microversion")
        if not isinstance(revision, str) or not _ID.fullmatch(revision):
            raise BackendError("Native state lacks exact element revision")
        if data.get("target") != job["target"] or not isinstance(data.get("tree"), dict):
            raise BackendError("Native state target/tree unavailable")
        return data

    async def schema(self, target: Target, command: str) -> dict[str, Any]:
        job: dict[str, Any] = {"kind": "schema", "target": _target(target), "name": command}
        if self.tab_id is not None:
            job["tab_id"] = self.tab_id
        return await self.bridge.command(job)

    async def creation_probe(self, target: Target) -> dict[str, Any]:
        """Inspect loaded editor allocator surfaces without invoking them."""
        job: dict[str, Any] = {"kind": "creation_probe", "target": _target(target)}
        if self.tab_id is not None:
            job["tab_id"] = self.tab_id
        result = await self.bridge.command(job)
        if result.get("target") != job["target"] or not _ID.fullmatch(str(result.get("element_microversion", ""))):
            raise BackendError("Creation probe target or element revision unavailable")
        return result

    async def feature_settings(self, target: Target, feature_key: str) -> dict[str, Any]:
        if feature_key not in {"::newSketch", "::extrude"}:
            raise Unsupported("Only sketch and extrusion settings may be probed")
        job: dict[str, Any] = {"kind": "native", "target": _target(target),
                               "command": "ui.GBTUiGetFeatureSettingsCall", "body": {"featureKey": feature_key}}
        if self.tab_id is not None:
            job["tab_id"] = self.tab_id
        return await self.bridge.command(job)

    async def modeling_probe(self, target: Target) -> dict[str, Any]:
        """Read-only evidence for a fresh editor build; never submits mutations."""
        health = await self.bridge.health()
        if not health.get("extension_connected"):
            raise BackendError("Onshape Native extension is not connected")
        state = await self.raw_state(target)
        if state.get("connected") is not True or state.get("editingFeatureId") or state.get("h2Readback", {}).get("complete") is not False:
            raise BackendError("Editor is busy or readback contract changed; inspect state manually")
        names = ("ui.GBTUiAddFeatureCall", "ui.GBTUiSpecifyFeature", "ui.GBTUiCommit",
                 "ui.sketch.GBTUiSketchAddRectangleCall")
        schemas = {name: await self.schema(target, name) for name in names}
        settings = {name: await self.feature_settings(target, name) for name in ("::newSketch", "::extrude")}
        return {"target": _target(target), "element_microversion": state["element_microversion"],
                "tree_type": state["tree"].get("$type"), "readback": state.get("h2Readback"),
                "schemas": schemas, "feature_settings": settings,
                "write_ready": False,
                "missing": ["verified live ID allocation", "exact insertion and plane bindings",
                            "full native feature/geometry regeneration readback"]}

    async def apply(self, operation: Operation, target: Target, expected_revision: str) -> Receipt:
        raise Unsupported("Native sketch/extrusion transaction lacks proven live ID allocation and complete readback")

    async def begin_test_top_sketch(self, target: Target, journal: Journal) -> dict[str, Any]:
        """Use observed normal editor controls to allocate one blank Top sketch."""
        if _target(target) != self.create_target or self.tab_id is None:
            raise Unsupported("Native sketch initiation requires the authorized temporary tab")
        key = f"{target.did}/{target.wid}/{target.eid}"
        with journal.target_lock(key):
            if journal.unresolved(key):
                raise UncertainWrite("Prior target write unresolved; inspect before mutation")
            health = await self.bridge.health()
            if (health.get("extension_connected") is not True
                    or "h2_native_begin_top_sketch_server_v1" not in (health.get("capabilities") or [])
                    or "h2_native_typed_top_plane_server_v1" not in (health.get("capabilities") or [])
                    or "h2_native_begin_top_sketch_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])
                    or "h2_native_begin_top_ready_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])
                    or "h2_native_typed_top_plane_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])):
                raise Unsupported("Installed bridge and loaded extension must both advertise Top-sketch initiation")
            before = await self.raw_state(target)
            children = before["tree"].get("children")
            if (before.get("connected") is not True or before.get("editingFeatureId") is not None
                    or before["tree"].get("$type") != "bsedit.GBTMModel"
                    or not isinstance(children, list) or len(children) != 1
                    or children[0].get("$type") != "bsedit.GBTMRollback"
                    or not children[0].get("nodeId")):
                # The first source-driven slice requires only default planes and
                # the rollback node. More complex history needs its own contract.
                raise Unsupported("Initial Top sketch requires an empty idle temporary Part Studio")
            op_id = "begin-sketch-" + uuid4().hex
            journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                            action="experimental_begin_top_sketch", logical_id="Top", intent={"before_state": before})
            job = {"kind": "partstudio_begin_top_sketch", "target": self.create_target,
                   "tab_id": self.tab_id, "expected_element_microversion": before["element_microversion"]}
            try:
                response = await self.bridge.command(job)
            except PreDispatchRejected as exc:
                journal.transition(op_id, "rejected", error=str(exc))
                raise
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Top sketch initiation outcome unknown; journal operation {op_id}") from exc
            journal.transition(op_id, "sent", receipt=response)
            try:
                after = await self.raw_state(target)
                after_children = after["tree"].get("children", [])
                feature_id = response.get("feature_id")
                matches = [node for node in after_children if isinstance(node, dict) and node.get("featureId") == feature_id]
                if (response.get("initiation_candidate") is not True or after.get("connected") is not True
                        or after.get("editingFeatureId") != feature_id
                        or after["element_microversion"] == before["element_microversion"]
                        or len(after_children) != len(children) + 1 or len(matches) != 1
                        or matches[0].get("nodeId") != response.get("feature_node_id")
                        or matches[0].get("featureType") != "newSketch"
                        or matches[0].get("entities") != [] or matches[0].get("constraints") != []
                        or any(node not in after_children for node in children)
                        or {k: v for k, v in before["tree"].items() if k != "children"}
                           != {k: v for k, v in after["tree"].items() if k != "children"}):
                    raise UncertainWrite("Independent Top sketch allocation or unchanged default tree not confirmed")
                plane = [p for p in matches[0].get("parameters", []) if p.get("parameterId") == "sketchPlane"]
                if (len(plane) != 1 or plane[0].get("$type") != "bsedit.GBTMParameterQueryList"
                        or len(plane[0].get("queries", [])) != 1
                        or plane[0]["queries"][0].get("deterministicIds") != response.get("plane_query_ids")):
                    raise UncertainWrite("Top plane binding differs from editor response")
                query = plane[0]["queries"][0]
                resolved = await self.bridge.command({"kind": "native", "target": self.create_target,
                    "tab_id": self.tab_id, "command": "ui.GBTUiGetQueryDataCall",
                    "body": {"elementId": target.eid, "queries": [query], "qFunction": "",
                             "additionalArguments": [], "queryNodeIdToInContextNodeId": {}}})
                result = resolved.get("result") or {}
                item = result.get("queryData", [None])
                item = item[0] if isinstance(item, list) and len(item) == 1 else None
                detail = item.get("evaluationDetails", {}) if isinstance(item, dict) else {}
                if (result.get("$type") != "ui.GBTUiGetQueryDataResponse"
                        or not isinstance(item, dict) or item.get("deterministicIds") != query["deterministicIds"]
                        or item.get("featureId") != "Top" or item.get("selectionName") != "Face"
                        or detail.get("fullOperationId") != "Top.planeOp" or detail.get("entityType") != 2
                        or detail.get("status") != 0 or item.get("hasErrorEntity") is not False
                        or detail.get("outsideExactDependencies") is not False):
                    raise UncertainWrite("Bound sketch plane does not resolve to Top")
                stable = await self.raw_state(target)
                if (stable.get("connected") is not True
                        or stable.get("editingFeatureId") != feature_id
                        or stable.get("element_microversion") != after["element_microversion"]
                        or stable.get("tree") != after["tree"]):
                    raise UncertainWrite("Top sketch editor changed during independent plane query")
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Top sketch initiation outcome unknown; journal operation {op_id}") from exc
            evidence = {"op_id": op_id, "feature_id": feature_id,
                        "revision_before": before["element_microversion"], "revision_after": after["element_microversion"],
                        "top_bound_by_verified_query": True, "blank_sketch_observed": True}
            journal.transition(op_id, "observed", observation=evidence)
            return evidence

    async def populate_test_sketch(self, target: Target, source: str | Path, journal: Journal) -> dict[str, Any]:
        """Populate one UI-allocated blank sketch from an exact FSGen source pair.

        This experimental slice is confined to the named temporary Part Studio.
        A returned definition observation does not prove solid regeneration.
        """
        if _target(target) != self.create_target or self.tab_id is None:
            raise Unsupported("Native sketch population requires the authorized temporary tab")
        from .fsgen import compile_fsgen
        snapshot = compile_fsgen(source, target)
        blueprint = stage_minimal_pair(snapshot)
        entities = snapshot.features[0].structure["fsgen_native"]["entities"]
        prefix = entities[0]["entityId"].rsplit(".", 1)[0]
        key = f"{target.did}/{target.wid}/{target.eid}"
        with journal.target_lock(key):
            if journal.unresolved(key):
                raise UncertainWrite("Prior target write unresolved; inspect before mutation")
            health = await self.bridge.health()
            if (health.get("extension_connected") is not True
                    or "h2_native_sketch_populate_server_v1" not in (health.get("capabilities") or [])
                    or "h2_native_completion_receipt_server_v1" not in (health.get("capabilities") or [])
                    or "h2_native_sketch_populate_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])
                    or "h2_native_fixed_origin_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])
                    or "h2_native_completion_receipt_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])):
                raise Unsupported("Installed bridge and loaded extension must both advertise native sketch support")
            before = await self.raw_state(target)
            tree = before["tree"]
            if (before.get("connected") is not True or before.get("h2Readback", {}).get("contract") != "h2-readback-probe-v1"
                    or tree.get("$type") != "bsedit.GBTMModel" or not isinstance(tree.get("children"), list)):
                raise Unsupported("Connected native Part Studio tree unavailable")
            feature_id = before.get("editingFeatureId")
            matches = [node for node in tree["children"] if isinstance(node, dict) and node.get("featureId") == feature_id]
            if (not isinstance(feature_id, str) or not feature_id or len(matches) != 1
                    or matches[0].get("featureType") != "newSketch" or not matches[0].get("nodeId")
                    or matches[0].get("entities") != [] or matches[0].get("constraints") != []):
                raise Unsupported("One empty UI-allocated sketch must be actively edited")
            plane = [p for p in matches[0].get("parameters", []) if isinstance(p, dict) and p.get("parameterId") == "sketchPlane"]
            if (len(plane) != 1 or plane[0].get("$type") != "bsedit.GBTMParameterQueryList"
                    or len(plane[0].get("queries", [])) != 1
                    or not plane[0]["queries"][0].get("deterministicIds")):
                raise Unsupported("Editor has not bound a sketch plane")
            op_id = "sketch-" + uuid4().hex
            journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                            action="experimental_sketch_populate", logical_id=blueprint.sketch_logical_id,
                            intent={"before_state": before, "feature_id": feature_id,
                                    "blueprint": blueprint.to_dict(), "entity_prefix": prefix})
            job: dict[str, Any] = {"kind": "partstudio_populate_sketch", "op_id": op_id, "target": self.create_target,
                                   "tab_id": self.tab_id, "expected_element_microversion": before["element_microversion"],
                                   "sketch_edit": {"feature_id": feature_id, "entity_prefix": prefix,
                                                   "rectangle_m": list(blueprint.rectangle_m)}}
            try:
                response = await self.bridge.command(job)
            except PreDispatchRejected as exc:
                journal.transition(op_id, "rejected", error=str(exc))
                raise
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Sketch population outcome unknown; journal operation {op_id}") from exc
            if response.get("op_id") != op_id:
                journal.transition(op_id, "unknown", error="Sketch receipt operation identity differs")
                raise UncertainWrite(f"Sketch receipt identity unknown; journal operation {op_id}")
            journal.transition(op_id, "sent", receipt=response)
            if response.get("completion_pending") is True:
                return await _confirm_pending_readback(self.bridge.reconcile_completed_source_sketch,
                                                       op_id, self.tab_id, "Sketch")
            try:
                after = await self.raw_state(target)
                result = _live_rectangle_feature(after, blueprint, feature_id=feature_id)
                _native_rectangle_constraints(result, blueprint)
                previous = tree["children"]
                current = after["tree"].get("children", [])
                pos = next(i for i, node in enumerate(previous) if node.get("featureId") == feature_id)
                if (response.get("definition_candidate") is not True
                        or after.get("connected") is not True or after.get("editingFeatureId") is not None
                        or after["element_microversion"] == before["element_microversion"]
                        or len(current) != len(previous) or current[pos].get("nodeId") != matches[0]["nodeId"]
                        or result.get("parameters") != matches[0].get("parameters")
                        or any(current[i] != previous[i] for i in range(len(previous)) if i != pos)):
                    raise UncertainWrite("Independent sketch readback or unrelated tree differs")
                # Saved sketches can return a generic response without graph
                # fields. The page captured the graph while the edit was active,
                # after SpecifyFeature and before Commit.
                _verify_rectangle_graph({"result": response.get("active_constraint_graph")}, prefix)
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Sketch population outcome unknown; journal operation {op_id}") from exc
            evidence = {"op_id": op_id, "feature_id": feature_id,
                        "revision_before": before["element_microversion"], "revision_after": after["element_microversion"],
                        "definition_observed": True, "origin_verified": True,
                        "geometry_verified": False, "constraint_graph_verified": True,
                        "graph_phase": "active_after_specify_before_commit",
                        "ui_editability_verified": False}
            return await _confirm_pending_readback(self.bridge.reconcile_completed_source_sketch,
                                                   op_id, self.tab_id, "Sketch")

    async def reconcile_test_sketch(self, op_id: str, journal: Journal) -> dict[str, Any]:
        """Inspect an uncertain sketch write without retrying or declaring completion."""
        row = journal.get(op_id)
        if row is None or row["action"] != "experimental_sketch_populate":
            raise Unsupported("Journal operation is not a native sketch population")
        if row["state"] == "observed":
            return {"op_id": op_id, "status": "verified", "evidence": json.loads(row["observation"] or "{}")}
        if row["state"] == "rejected":
            return {"op_id": op_id, "status": "rejected", "reason": row["error"]}
        fields = row["target"].split("/")
        if len(fields) != 3 or dict(zip(("did", "wid", "eid"), fields)) != self.create_target:
            raise Unsupported("Experimental sketch journal target differs from the authorized studio")
        try:
            state = await self.raw_state(Target(*fields))
        except Exception as exc:
            return {"op_id": op_id, "status": "unknown", "reason": f"Read-only inspection failed: {exc}"}
        before = json.loads(row["intent"]).get("before_state", {})
        return {"op_id": op_id, "status": "unknown", "reason":
                "Sketch write needs independent definition and constraint-graph review; no command was replayed",
                "revision_before": before.get("element_microversion"),
                "revision_now": state.get("element_microversion"),
                "editing_feature_id": state.get("editingFeatureId")}

    async def classify_known_invalid_sketch(self, op_id: str, journal: Journal) -> dict[str, Any]:
        """Record applied-invalid editor state while retaining the unknown barrier."""
        if op_id != "sketch-d9d02a9ba8b44bdea72b4bb67281c7e1":
            raise Unsupported("Only the reviewed failed sketch operation can be classified")
        row = journal.get(op_id)
        if (row is None or row["action"] != "experimental_sketch_populate"
                or row["state"] != "unknown" or row["target"] != "/".join(self.create_target.values())
                or row["error"] != "Sketch command acknowledged but saved definition/idle state is unconfirmed; outcome unknown."):
            raise Unsupported("Known applied-invalid journal row differs")
        intent = json.loads(row["intent"])
        before = intent.get("before_state")
        feature_id = intent.get("feature_id")
        if (not isinstance(before, dict) or before.get("element_microversion") != row["expected_revision"]
                or before.get("editingFeatureId") != feature_id):
            raise Unsupported("Known sketch prewrite snapshot differs")
        target = Target(**self.create_target)
        with journal.target_lock(row["target"]):
            after = await self.raw_state(target)
            blueprint_data = intent.get("blueprint")
            if not isinstance(blueprint_data, dict):
                raise Unsupported("Known sketch blueprint unavailable")
            blueprint = NativePairBlueprint(blueprint_data["sketch_logical_id"],
                                            blueprint_data["extrusion_logical_id"],
                                            blueprint_data["plane_name"],
                                            tuple(blueprint_data["rectangle_m"]), blueprint_data["depth_mm"])
            feature = _live_rectangle_feature(after, blueprint, feature_id=feature_id)
            _native_rectangle_constraints(feature, blueprint)
            previous = before["tree"].get("children")
            current = after["tree"].get("children")
            prior_feature = next((x for x in previous if isinstance(x, dict) and x.get("featureId") == feature_id), None) if isinstance(previous, list) else None
            if (after.get("connected") is not True or after.get("editingFeatureId") not in (None, feature_id)
                    or after.get("element_microversion") != "97955554c86d659d57a74a68"
                    or not isinstance(previous, list) or not isinstance(current, list)
                    or len(previous) != len(current)
                    or any(a != b for a, b in zip(previous, current) if a.get("featureId") != feature_id)
                    or prior_feature is None or feature.get("parameters") != prior_feature.get("parameters")
                    or _native_model_metadata(before["tree"]) != _native_model_metadata(after["tree"])):
                raise Unsupported("Current failed sketch or unrelated tree differs from the known attempt")
            graph = await self.bridge.command({"kind": "native", "target": self.create_target,
                                               "tab_id": self.tab_id,
                                               "command": "ui.sketch.GBTUiSketchGetConstraintGraphCall",
                                               "body": {"elementId": target.eid, "sketchFeatureId": feature_id,
                                                        "supportsConsolidatedConstraints": False}})
            result = graph.get("result")
            if not isinstance(result, dict):
                raise Unsupported("Known failed sketch graph response unavailable")
            if (result.get("$type") == "ui.sketch.GBTUiSketchGetConstraintGraphResponse"
                    and result.get("constraints") in (None, {})
                    and result.get("references") in (None, {})):
                graph_status = "empty_active"
            elif (after.get("editingFeatureId") is None
                    and result.get("$type") == "ui.sketch.GBTUiSketchResponse"
                    and "constraints" not in result and "references" not in result):
                graph_status = "unavailable_saved"
            else:
                raise Unsupported("Known failed sketch graph differs or shows solved constraints")
            evidence = {"classification": "applied_invalid", "op_id": op_id,
                        "feature_id": feature_id, "revision_before": row["expected_revision"],
                        "revision_invalid": after["element_microversion"],
                        "saved_invalid_feature": after.get("editingFeatureId") is None,
                        "definition_present": True, "constraint_graph_status": graph_status,
                        "unrelated_tree_preserved": True}
            journal.annotate_unknown(op_id, evidence)
            return {"op_id": op_id, "status": "applied_invalid_unresolved", "evidence": evidence}

    async def begin_test_source_extrude(self, target: Target, source: str | Path, *,
                                        sketch_op_id: str, journal: Journal) -> dict[str, Any]:
        """Select the sole saved source sketch and start its editor-bound Extrude."""
        if _target(target) != self.create_target or self.tab_id is None:
            raise Unsupported("Source Extrude initiation requires the configured test tab")
        from .fsgen import compile_fsgen
        blueprint = stage_minimal_pair(compile_fsgen(source, target))
        key = f"{target.did}/{target.wid}/{target.eid}"
        with journal.target_lock(key):
            if journal.unresolved(key):
                raise UncertainWrite("Prior target write unresolved; inspect before mutation")
            sketch_op = journal.get(sketch_op_id)
            if (not sketch_op or sketch_op["target"] != key or sketch_op["state"] != "observed"
                    or sketch_op["action"] != "experimental_sketch_populate"
                    or sketch_op["logical_id"] != blueprint.sketch_logical_id):
                raise Unsupported("An observed sketch from this source and target is required")
            evidence = json.loads(sketch_op["observation"] or "{}")
            sketch_id = evidence.get("feature_id")
            if (not isinstance(sketch_id, str) or evidence.get("origin_verified") is not True
                    or evidence.get("constraint_graph_verified") is not True):
                raise Unsupported("Source sketch and active solver proof are required")
            health = await self.bridge.health()
            if (health.get("extension_connected") is not True
                    or "h2_native_begin_source_extrude_server_v1" not in (health.get("capabilities") or [])
                    or "h2_native_begin_source_extrude_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])):
                raise Unsupported("Loaded bridge and extension lack source Extrude initiation")
            before = await self.raw_state(target)
            tree = before.get("tree", {})
            children = tree.get("children")
            if (before.get("connected") is not True or before.get("editingFeatureId") is not None
                    or tree.get("$type") != "bsedit.GBTMModel" or not isinstance(children, list)
                    or len(children) != 2 or children[-1].get("$type") != "bsedit.GBTMRollback"):
                raise Unsupported("One saved source sketch in an idle test studio is required")
            sketch = _live_rectangle_feature(before, blueprint, feature_id=sketch_id)
            _native_rectangle_constraints(sketch, blueprint)
            op_id = "begin-extrude-" + uuid4().hex
            journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                            action="experimental_begin_source_extrude", logical_id=blueprint.extrusion_logical_id,
                            intent={"before_state": before, "sketch_op_id": sketch_op_id,
                                    "sketch_feature_id": sketch_id})
            job = {"kind": "partstudio_begin_source_extrude", "op_id": op_id, "target": self.create_target,
                   "tab_id": self.tab_id, "expected_element_microversion": before["element_microversion"],
                   "sketch_feature_id": sketch_id}
            try:
                response = await self.bridge.command(job)
            except PreDispatchRejected as exc:
                journal.transition(op_id, "rejected", error=str(exc))
                raise
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Source Extrude initiation unknown; journal operation {op_id}") from exc
            journal.transition(op_id, "sent", receipt=response)
            try:
                after = await self.raw_state(target)
                current = after["tree"].get("children", [])
                feature_id = response.get("feature_id")
                matches = [node for node in current if node.get("featureId") == feature_id]
                if (response.get("op_id") != op_id or response.get("initiation_candidate") is not True
                        or response.get("region_source_verified") is not True
                        or after.get("connected") is not True or after.get("editingFeatureId") != feature_id
                        or after["element_microversion"] == before["element_microversion"]
                        or len(current) != 3 or len(matches) != 1 or matches[0].get("featureType") != "extrude"
                        or matches[0].get("nodeId") != response.get("feature_node_id")
                        or current[0] != children[0] or current[-1] != children[-1]):
                    raise UncertainWrite("Independent source Extrude allocation differs")
                params = matches[0].get("parameters", [])
                by_id = lambda name: [p for p in params if p.get("parameterId") == name]
                queries = by_id("entities")[0].get("queries", [])
                if (len(queries) != 1 or queries[0].get("$type") != "bsedit.GBTMIndividualSketchRegionQuery"
                        or queries[0].get("featureId") != sketch_id or queries[0].get("filterInnerLoops") is not True
                        or queries[0].get("deterministicIds") != response.get("region_query_ids")
                        or any(len(by_id(k)) != 1 or by_id(k)[0].get("value") != v for k, v in
                               (("bodyType", "SOLID"), ("operationType", "NEW"), ("endBound", "BLIND")))):
                    raise UncertainWrite("Source region or NEW solid mode differs")
                resolved = await self.bridge.command({"kind": "native", "target": self.create_target,
                    "tab_id": self.tab_id, "command": "ui.GBTUiGetQueryDataCall",
                    "body": {"elementId": target.eid, "queries": queries, "qFunction": "",
                             "additionalArguments": [], "queryNodeIdToInContextNodeId": {}}})
                _verify_source_region_query(resolved, queries[0], sketch_id)
                confirmed = await self.raw_state(target)
                if (confirmed.get("connected") is not True
                        or confirmed.get("editingFeatureId") != feature_id
                        or confirmed.get("element_microversion") != after["element_microversion"]
                        or confirmed.get("tree") != after["tree"]):
                    raise UncertainWrite("Source Extrude editor changed during region resolution")
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Source Extrude initiation unknown; journal operation {op_id}") from exc
            result = {"op_id": op_id, "feature_id": feature_id, "sketch_feature_id": sketch_id,
                      "revision_before": before["element_microversion"],
                      "revision_after": after["element_microversion"], "region_source_verified": True,
                      "active_draft_observed": True, "region_query_evidence": resolved}
            journal.transition(op_id, "observed", observation=result)
            return result

    async def populate_test_extrude(self, target: Target, source: str | Path, *,
                                    sketch_op_id: str, journal: Journal) -> dict[str, Any]:
        """Set the source depth on one active, editor-bound native extrusion."""
        if _target(target) != self.create_target or self.tab_id is None:
            raise Unsupported("Native extrusion population requires the authorized temporary tab")
        from .fsgen import compile_fsgen
        blueprint = stage_minimal_pair(compile_fsgen(source, target))
        key = f"{target.did}/{target.wid}/{target.eid}"
        with journal.target_lock(key):
            if journal.unresolved(key):
                raise UncertainWrite("Prior target write unresolved; inspect before mutation")
            sketch_op = journal.get(sketch_op_id)
            if (not sketch_op or sketch_op["target"] != key
                    or sketch_op["action"] != "experimental_sketch_populate"
                    or sketch_op["state"] != "observed"
                    or sketch_op["logical_id"] != blueprint.sketch_logical_id):
                raise Unsupported("One observed source sketch intent is required")
            sketch_evidence = json.loads(sketch_op["observation"] or "{}")
            sketch_id = sketch_evidence.get("feature_id")
            if (not isinstance(sketch_id, str) or not sketch_id
                    or sketch_evidence.get("origin_verified") is not True
                    or sketch_evidence.get("constraint_graph_verified") is not True):
                raise Unsupported("Source sketch origin and solver graph remain unverified")
            health = await self.bridge.health()
            if (health.get("extension_connected") is not True
                    or "h2_native_extrude_populate_server_v1" not in (health.get("capabilities") or [])
                    or "h2_native_completion_receipt_server_v1" not in (health.get("capabilities") or [])
                    or "h2_native_extrude_populate_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])
                    or "h2_native_source_region_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])
                    or "h2_native_extrude_recheck_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])
                    or "h2_native_completion_receipt_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])):
                raise Unsupported("Installed bridge and loaded extension must both advertise native extrusion support")
            before = await self.raw_state(target)
            tree = before["tree"]
            if (before.get("connected") is not True or tree.get("$type") != "bsedit.GBTMModel"
                    or not isinstance(tree.get("children"), list)):
                raise Unsupported("Connected native Part Studio tree unavailable")
            children = tree["children"]
            sketches = [node for node in children if isinstance(node, dict) and node.get("featureType") == "newSketch"]
            if len(sketches) != 1 or sketches[0].get("featureId") != sketch_id:
                raise Unsupported("Exactly one saved source sketch is required")
            _native_rectangle_constraints(_live_rectangle_feature(before, blueprint, feature_id=sketch_id), blueprint)
            feature_id = before.get("editingFeatureId")
            extrusions = [node for node in children if isinstance(node, dict) and node.get("featureId") == feature_id]
            if (not isinstance(feature_id, str) or not feature_id or len(extrusions) != 1
                    or extrusions[0].get("featureType") != "extrude" or not extrusions[0].get("nodeId")):
                raise Unsupported("Exactly one active UI-allocated extrusion is required")
            params = extrusions[0].get("parameters")
            if not isinstance(params, list):
                raise Unsupported("Active extrusion parameters unavailable")
            by_id = lambda name: [p for p in params if isinstance(p, dict) and p.get("parameterId") == name]
            depth = by_id("depth")
            region = by_id("entities")
            if (len(depth) != 1 or depth[0].get("$type") != "bsedit.GBTMParameterQuantity"
                    or depth[0].get("units") != "millimeter" or not depth[0].get("nodeId")
                    or len(region) != 1 or region[0].get("$type") != "bsedit.GBTMParameterQueryList"
                    or len(region[0].get("queries", [])) != 1
                    or not region[0]["queries"][0].get("deterministicIds")):
                raise Unsupported("Editor has not bound one extrusion region and literal depth")
            from_mm = depth[0].get("value")
            if (type(from_mm) not in (int, float) or not math.isfinite(from_mm) or not 0 < from_mm <= 1000
                    or depth[0].get("expression") != f"{from_mm:g} mm" or from_mm == blueprint.depth_mm):
                raise Unsupported("Expected a distinct positive literal editor depth before source update")
            selected_query = region[0]["queries"][0]
            resolved = await self.bridge.command({"kind": "native", "target": self.create_target,
                                                  "tab_id": self.tab_id,
                                                  "command": "ui.GBTUiGetQueryDataCall",
                                                  "body": {"elementId": target.eid, "queries": [selected_query],
                                                           "qFunction": "", "additionalArguments": [],
                                                           "queryNodeIdToInContextNodeId": {}}})
            _verify_source_region_query(resolved, selected_query, sketch_id)
            confirm = await self.raw_state(target)
            if (confirm.get("connected") is not True or confirm.get("editingFeatureId") != feature_id
                    or confirm.get("element_microversion") != before["element_microversion"]
                    or confirm.get("tree") != tree):
                raise Unsupported("Extrusion editor changed during source-region resolution")
            expected_tree = _depth_expected_tree(tree, feature_id, from_mm, blueprint.depth_mm)
            op_id = "extrude-" + uuid4().hex
            journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                            action="experimental_extrude_populate", logical_id=blueprint.extrusion_logical_id,
                            intent={"before_state": before, "expected_tree": expected_tree,
                                    "sketch_op_id": sketch_op_id, "sketch_feature_id": sketch_id,
                                    "region_query_evidence": resolved})
            job = {"kind": "partstudio_populate_extrude", "op_id": op_id, "target": self.create_target,
                   "tab_id": self.tab_id, "expected_element_microversion": before["element_microversion"],
                   "extrude_edit": {"feature_id": feature_id, "sketch_feature_id": sketch_id,
                                    "from_mm": from_mm, "to_mm": blueprint.depth_mm}}
            try:
                response = await self.bridge.command(job)
            except PreDispatchRejected as exc:
                journal.transition(op_id, "rejected", error=str(exc))
                raise
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Extrusion population outcome unknown; journal operation {op_id}") from exc
            if response.get("op_id") != op_id:
                journal.transition(op_id, "unknown", error="Extrusion receipt operation identity differs")
                raise UncertainWrite(f"Extrusion receipt identity unknown; journal operation {op_id}")
            journal.transition(op_id, "sent", receipt=response)
            if response.get("completion_pending") is True:
                # The broker retains its write barrier. Only a fresh exact
                # readback tied to this durable operation can release it.
                return await _confirm_pending_readback(self.bridge.reconcile_saved_source_extrude,
                                                       op_id, self.tab_id, "Extrusion")
            try:
                after = await self.raw_state(target)
                if (response.get("definition_candidate") is not True
                        or response.get("region_source_verified") is not True or after.get("connected") is not True
                        or after.get("editingFeatureId") is not None
                        or after["element_microversion"] == before["element_microversion"]
                        or after["tree"] != expected_tree):
                    raise UncertainWrite("Independent extrusion definition or unrelated tree differs")
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Extrusion population outcome unknown; journal operation {op_id}") from exc
            evidence = {"op_id": op_id, "feature_id": feature_id, "sketch_feature_id": sketch_id,
                        "revision_before": before["element_microversion"], "revision_after": after["element_microversion"],
                        "depth_mm": blueprint.depth_mm, "definition_observed": True,
                        "solid_geometry_verified": False, "ui_editability_verified": False,
                        "region_source_verified": True}
            return await _confirm_pending_readback(self.bridge.reconcile_saved_source_extrude,
                                                   op_id, self.tab_id, "Extrusion")

    async def reconcile_test_extrude(self, op_id: str, journal: Journal) -> dict[str, Any]:
        """Read an uncertain extrusion intent, never replaying its editor commands."""
        row = journal.get(op_id)
        if row is None or row["action"] != "experimental_extrude_populate":
            raise Unsupported("Journal operation is not a native extrusion population")
        if row["state"] == "observed":
            return {"op_id": op_id, "status": "verified", "evidence": json.loads(row["observation"] or "{}")}
        if row["state"] == "rejected":
            return {"op_id": op_id, "status": "rejected", "reason": row["error"]}
        fields = row["target"].split("/")
        if len(fields) != 3 or dict(zip(("did", "wid", "eid"), fields)) != self.create_target:
            raise Unsupported("Experimental extrusion journal target differs from the authorized studio")
        try:
            state = await self.raw_state(Target(*fields))
        except Exception as exc:
            return {"op_id": op_id, "status": "unknown", "reason": f"Read-only inspection failed: {exc}"}
        return {"op_id": op_id, "status": "unknown", "reason":
                "Extrusion write needs independent region, solid, and editability review; no command was replayed",
                "revision_now": state.get("element_microversion")}

    async def edit_disposable_extrude_depth(self, target: Target, *, feature_id: str,
                                            from_mm: int | float, to_mm: int | float,
                                            journal: Journal) -> dict[str, Any]:
        """One experimental editor transaction; a new state is read independently.

        This does not grant the generic planner a native write capability or prove
        regeneration. An unknown outcome remains journaled and is never replayed.
        """
        if _target(target) != _DISPOSABLE:
            raise Unsupported("Depth edit is limited to the authorized disposable Part Studio")
        if not isinstance(feature_id, str) or not feature_id or len(feature_id) > 80:
            raise ValueError("Expected one live feature ID")
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 1000 for v in (from_mm, to_mm)) or from_mm == to_mm:
            raise ValueError("Expected distinct positive bounded millimeter depths")
        key = f"{target.did}/{target.wid}/{target.eid}"
        with journal.target_lock(key):
            if journal.unresolved(key):
                raise UncertainWrite("Prior target write unresolved; inspect before mutation")
            health = await self.bridge.health()
            if (health.get("extension_connected") is not True
                    or "h2_depth_edit_server_v1" not in (health.get("capabilities") or [])
                    or "h2_depth_edit_page_v1" not in ((health.get("extension") or {}).get("capabilities") or [])):
                raise Unsupported("Installed bridge and loaded extension must both advertise depth-edit support")
            before = await self.raw_state(target)
            if (before.get("connected") is not True or before.get("editingFeatureId") is not None
                    or before.get("h2Readback", {}).get("contract") != "h2-readback-probe-v1"
                    or before.get("h2DepthEdit") != {"contract": "h2-depth-edit-page-v1", "supported": True}):
                raise Unsupported("Editor state unavailable or busy")
            expected_tree = _depth_expected_tree(before["tree"], feature_id, from_mm, to_mm)
            op_id = "depth-" + uuid4().hex
            journal.prepare(op_id=op_id, target=key, expected_revision=before["element_microversion"],
                            action="experimental_depth_edit", logical_id=feature_id,
                            intent={"before_state": before, "expected_tree": expected_tree, "to_mm": to_mm})
            job: dict[str, Any] = {"kind": "partstudio_depth_edit", "target": _DISPOSABLE,
                                   "expected_element_microversion": before["element_microversion"],
                                   "depth_edit": {"feature_id": feature_id, "from_mm": from_mm, "to_mm": to_mm}}
            if self.tab_id is not None:
                job["tab_id"] = self.tab_id
            try:
                response = await self.bridge.command(job)
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Depth edit outcome unknown; journal operation {op_id}") from exc
            journal.transition(op_id, "sent", receipt=response)
            try:
                after = await self.raw_state(target)
                if (response.get("definition_verified") is not True or after["tree"] != expected_tree
                        or after.get("connected") is not True or after.get("editingFeatureId") is not None
                        or after.get("element_microversion") == before["element_microversion"]):
                    raise UncertainWrite("Independent tree readback or revision differs from expected edit")
            except Exception as exc:
                journal.transition(op_id, "unknown", error=str(exc))
                raise UncertainWrite(f"Depth edit outcome unknown; journal operation {op_id}") from exc
            evidence = {"op_id": op_id, "feature_id": feature_id, "from_mm": from_mm, "to_mm": to_mm,
                        "revision_before": before["element_microversion"], "revision_after": after["element_microversion"],
                        "definition_verified": True, "geometry_verified": False, "ui_editability_verified": False}
            journal.transition(op_id, "observed", observation=evidence)
            return evidence

    async def reconcile_disposable_extrude_depth(self, op_id: str, journal: Journal) -> dict[str, Any]:
        """Read-only recovery for one prior experimental depth intent."""
        row = journal.get(op_id)
        if row is None:
            raise ValueError(f"Unknown journal operation {op_id}")
        if row["action"] != "experimental_depth_edit":
            raise Unsupported("Journal operation is not an experimental depth edit")
        if row["state"] == "observed":
            return {"op_id": op_id, "status": "verified", "evidence": json.loads(row["observation"] or "{}")}
        if row["state"] == "rejected":
            return {"op_id": op_id, "status": "rejected", "reason": row["error"]}
        fields = row["target"].split("/")
        if len(fields) != 3 or dict(zip(("did", "wid", "eid"), fields)) != _DISPOSABLE:
            raise Unsupported("Experimental journal target differs from the authorized disposable Part Studio")
        intent = json.loads(row["intent"])
        before = intent.get("before_state")
        expected = intent.get("expected_tree")
        if not isinstance(before, dict) or not isinstance(expected, dict) or before.get("element_microversion") != row["expected_revision"]:
            raise Unsupported("Experimental journal intent is incomplete")
        target = Target(*fields)
        with journal.target_lock(row["target"]):
            try:
                after = await self.raw_state(target)
            except Exception as exc:
                return {"op_id": op_id, "status": "unknown", "reason": f"Read-only inspection failed: {exc}"}
            if (after.get("connected") is not True or after.get("editingFeatureId") is not None
                    or after.get("element_microversion") == row["expected_revision"] or after.get("tree") != expected):
                return {"op_id": op_id, "status": "unknown", "reason": "Current editor state does not exactly match the journaled depth edit"}
            evidence = {"op_id": op_id, "feature_id": row["logical_id"],
                        "revision_before": row["expected_revision"], "revision_after": after["element_microversion"],
                        "definition_verified": True, "geometry_verified": False, "ui_editability_verified": False,
                        "reconciled_read_only": True}
            if row["state"] == "prepared":
                journal.transition(op_id, "unknown", error="Prepared intent recovered; submission status unknown")
            journal.transition(op_id, "observed", observation=evidence)
            return {"op_id": op_id, "status": "verified", "evidence": evidence}


def _depth_expected_tree(tree: dict[str, Any], feature_id: str, from_mm: int | float, to_mm: int | float) -> dict[str, Any]:
    if tree.get("$type") != "bsedit.GBTMModel" or not isinstance(tree.get("children"), list):
        raise Unsupported("Expected a Part Studio model tree")
    expected = copy.deepcopy(tree)
    matches = [child for child in expected["children"] if isinstance(child, dict) and child.get("featureId") == feature_id]
    if len(matches) != 1 or matches[0].get("featureType") != "extrude":
        raise Unsupported("Extrusion identity absent or ambiguous")
    params = matches[0].get("parameters")
    if not isinstance(params, list):
        raise Unsupported("Extrusion parameters unavailable")
    depth = [p for p in params if p.get("parameterId") == "depth"]
    modes = {p.get("parameterId"): p.get("value") for p in params}
    if (len(depth) != 1 or depth[0].get("$type") != "bsedit.GBTMParameterQuantity"
            or depth[0].get("expression") != f"{from_mm:g} mm" or depth[0].get("value") != from_mm
            or depth[0].get("units") != "millimeter" or not depth[0].get("nodeId")
            or any(modes.get(k) != v for k, v in (("bodyType", "SOLID"), ("operationType", "NEW"), ("endBound", "BLIND")))):
        raise Unsupported("Live extrusion depth or mode differs from expected fixture")
    depth[0]["expression"] = f"{to_mm:g} mm"
    depth[0]["value"] = to_mm
    return expected
