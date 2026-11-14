"""Pinned FSGen trace adapter. Compilation is offline and makes no Onshape calls."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from .model import Feature, Snapshot, Target


class FsgenUnavailable(RuntimeError):
    pass


class FsgenCompileError(ValueError):
    pass


def _rectangle(sketch) -> dict | None:
    """Recognize FSGen's four-line skRectangle expansion, in SI meters."""
    entities = sketch.entities
    if len(entities) != 4 or any(e.kind != "line" or e.construction for e in entities):
        return None
    names = [e.name.rsplit(".", 1)[-1] for e in entities]
    if names != ["bottom", "right", "top", "left"]:
        return None
    points = [tuple(float(v) for v in e.geom["p0"].a) for e in entities]
    if any(len(p) != 2 for p in points):
        return None
    x0, y0 = points[0]
    x1, y1 = points[2]
    if not (x0 < x1 and y0 < y1):
        return None
    if points != [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        return None
    ends = [tuple(float(v) for v in e.geom["p1"].a) for e in entities]
    if ends != [(x1, y0), (x1, y1), (x0, y1), (x0, y0)]:
        return None
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "construction": False}


def _parameter_value(item: dict):
    if "expression" in item:
        return item["expression"]
    if "value" in item:
        return item["value"]
    if "queries" in item:
        return [q.get("queryString") for q in item["queries"]]
    return item


def _semantic_native_body(template: dict) -> dict:
    """Exclude evaluated geometry FSGen proves is controlled by constraints.

    The complete creation body stays in provenance. Only the planner's semantic
    comparison drops numeric geometry for entities named by FSGen's `_driven`.
    Its entity identities, construction flags, and driving constraints remain.
    """
    driven = template.get("_driven", [])
    if (not isinstance(driven, list) or any(not isinstance(name, str) or not name for name in driven)
            or len(set(driven)) != len(driven)):
        raise FsgenCompileError("FSGen returned invalid driven entity IDs")
    body = copy.deepcopy({key: value for key, value in template.items()
                          if key not in {"parameters", "_driven"}})
    if driven:
        entities = body.get("entities")
        if (not isinstance(entities, list) or any(not isinstance(entity, dict)
                                                 or not isinstance(entity.get("entityId"), str)
                                                 for entity in entities)):
            raise FsgenCompileError("FSGen driven entities lack a sketch entity list")
        ids = [entity["entityId"] for entity in entities]
        if len(set(ids)) != len(ids) or not set(driven) <= set(ids):
            raise FsgenCompileError("FSGen driven entity IDs do not match the sketch")
        for entity in entities:
            if entity["entityId"] in driven:
                for field in ("geometry", "startParam", "endParam"):
                    entity.pop(field, None)
    return body


def compile_fsgen(source: str | Path, target: Target, revision: str = "local") -> Snapshot:
    """Compile supported FSGen records to semantic features and preserved JSON templates.

    `fsgen_feature_json` contains a local template with logical query references;
    it is **not** a browser RPC payload. Callers must validate selection semantics.
    """
    try:
        from fsgen.native.build import feature_json
        from fsgen.native.script import QText, trace
    except ImportError as exc:
        raise FsgenUnavailable("install pinned FSGen and its x64 OCP dependencies") from exc
    text = source.read_text(encoding="utf-8") if isinstance(source, Path) else source
    # Tree mode retains variable definitions as editable native features. Studio
    # mode would drop variable_list at this boundary and leave #expressions
    # dangling in browser-native execution.
    traced = trace(text, variables_mode="tree")
    if not traced.ok:
        raise FsgenCompileError(f"FSGen trace failed at line {traced.error_line}: {traced.error}")
    names = {f.name for f in traced.features}
    features: list[Feature] = []
    for rec in traced.features:
        refs: set[str] = set()

        def gather(value):
            if isinstance(value, QText):
                refs.update(value.refs)
            elif isinstance(value, dict):
                for v in value.values():
                    gather(v)
            elif isinstance(value, (list, tuple)):
                for v in value:
                    gather(v)

        gather(rec.params)
        if rec.sketch:
            gather(rec.sketch.plane)
        # A quantity expression can depend on an earlier Variable feature even
        # when the query graph does not. Sketch constraints carry those refs.
        variable_refs = {"#" + name for name in re.findall(
            r"(?<!#)#([A-Za-z][A-Za-z0-9_]*)", json.dumps(rec.params, default=str))}
        missing = refs - names
        if missing:
            raise FsgenCompileError(f"{rec.name}: unresolved feature reference(s): {sorted(missing)}")
        # feature_json resolves QText refs using the supplied map; avoid QText's
        # permissive fallback by having checked all logical names above.
        template = feature_json(rec, {name: name for name in names})
        def expressions(value):
            if isinstance(value, dict):
                if isinstance(value.get("expression"), str):
                    yield value["expression"]
                for child in value.values():
                    yield from expressions(child)
            elif isinstance(value, list):
                for child in value:
                    yield from expressions(child)

        variable_refs.update("#" + name for expression in expressions(template)
                             for name in re.findall(r"(?<!#)#([A-Za-z][A-Za-z0-9_]*)", expression))
        variable_refs.discard(rec.name)
        missing_vars = variable_refs - names
        if missing_vars:
            raise FsgenCompileError(f"{rec.name}: unresolved variable(s): {sorted(missing_vars)}")
        params = {p["parameterId"]: _parameter_value(p) for p in template.get("parameters", [])}
        # The body contains real nonparameter semantics (sketch entities,
        # constraints, feature type). They must participate in conflict checks.
        # Parameter payload values live only in `parameters`; retaining them
        # here would turn a simple depth edit into a false structural conflict.
        structure = {"fsgen_native": _semantic_native_body(template),
                     "parameter_schema": {
                         p["parameterId"]: {k: v for k, v in p.items()
                                            if k not in {"expression", "value", "queries"}}
                         for p in template.get("parameters", [])}}
        if rec.sketch:
            structure["sketch"] = {"plane_name": rec.sketch.plane_name,
                                   "rectangle": _rectangle(rec.sketch)}
        dependencies = tuple(f.name for f in traced.features if f.name in refs | variable_refs)
        features.append(Feature(rec.name, rec.feature_type, params,
                                dependencies, structure,
                                provenance={"fsgen_feature_json": template, "source_line": rec.line}))
    return Snapshot(target, revision, features)
