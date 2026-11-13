"""Independent adapter for the installed Onshape Native loopback bridge.

Only the editor RPC channel is admitted. Captured upstream messages are never
replayed, and observed message shapes are not treated as proven capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
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
_DISPOSABLE = {"did": "f5a8353dc826a9ec52106138", "wid": "a3baadfcc7e36a50134951d6", "eid": "a2761fa52794bee99354ae96"}


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
            or len(sketch_body.get("entities", [])) != 4
            or not isinstance(sketch_body.get("constraints"), list)
            or sketch.parameters.get("sketchPlane") != ['query=qCreatedBy(makeId("Top"), EntityType.FACE);']):
        raise Unsupported("FSGen sketch entities, constraints, or Top query differ")
    if (sketch.structure.get("parameter_schema", {}).get("sketchPlane", {}).get("btType") != "BTMParameterQueryList-148"
            or extrusion.structure.get("parameter_schema", {}).get("entities", {}).get("btType") != "BTMParameterQueryList-148"
            or extrusion.structure.get("parameter_schema", {}).get("depth", {}).get("btType") != "BTMParameterQuantity-147"):
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
        return cls(config["token"], **kwargs)

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

    async def command(self, job: dict[str, Any]) -> dict[str, Any]:
        if job.get("kind") not in {"state", "schema", "creation_probe", "native", "partstudio_depth_edit"}:
            raise Unsupported("Browser-mode adapter permits only native editor jobs")
        try:
            response = await self.http.post("/command", json=job)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UncertainWrite("Native bridge response unavailable; inspect before further mutation") from exc
        if response.status_code != 200 or not isinstance(data, dict):
            raise BackendError(f"Native bridge rejected command (HTTP {response.status_code})")
        if data.get("error"):
            if job.get("kind") == "partstudio_depth_edit":
                raise UncertainWrite(str(data["error"]))
            raise BackendError(str(data["error"]))
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
