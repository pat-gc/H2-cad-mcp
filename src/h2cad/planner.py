"""Deterministic, conservative three-way planner for one Part Studio."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

from .model import Conflict, Feature, Operation, Plan, Snapshot, Target, canonical


_MISSING = object()


def _index(snapshot: Snapshot, conflicts: list[Conflict], label: str) -> dict[str, Feature]:
    out: dict[str, Feature] = {}
    for feature in snapshot.features:
        if feature.logical_id in out:
            conflicts.append(Conflict(feature.logical_id, label, "duplicate logical ID"))
        out[feature.logical_id] = feature
    return out


def _op(target: Target, revision: str, action: str, logical_id: str,
        before: Feature | None, after: Feature | None) -> Operation:
    payload = {"target": target.to_dict(), "revision": revision,
               "native_id": before.native_id if before else None,
               "action": action, "logical_id": logical_id,
               "before": before.semantic_dict() if before else None,
               "after": after.semantic_dict() if after else None}
    digest = hashlib.sha256(canonical(payload).encode()).hexdigest()[:20]
    return Operation(digest, action, logical_id, before, after)


def _merge_feature(base: Feature, observed: Feature, desired: Feature,
                   conflicts: list[Conflict]) -> Feature:
    fid = base.logical_id
    if observed.native_id != base.native_id and base.native_id is not None:
        conflicts.append(Conflict(fid, "native_id", "remote identity changed", base.native_id,
                                  observed.native_id, desired.native_id))
    for field in ("kind", "dependencies", "structure"):
        old, remote, want = getattr(base, field), getattr(observed, field), getattr(desired, field)
        if canonical(want) != canonical(old):
            conflicts.append(Conflict(fid, field, "structural edits require explicit migration", old, remote, want))
        elif canonical(remote) != canonical(old):
            conflicts.append(Conflict(fid, field, "remote structure changed", old, remote, want))
    if desired.ownership != base.ownership:
        conflicts.append(Conflict(fid, "ownership", "ownership change requires review",
                                  base.ownership, observed.ownership, desired.ownership))
    result = dict(observed.parameters)
    for key in sorted(set(base.parameters) | set(observed.parameters) | set(desired.parameters)):
        old = base.parameters.get(key, _MISSING)
        remote = observed.parameters.get(key, _MISSING)
        want = desired.parameters.get(key, _MISSING)
        changed_remote = canonical(remote) != canonical(old) if remote is not _MISSING and old is not _MISSING else remote is not old
        changed_want = canonical(want) != canonical(old) if want is not _MISSING and old is not _MISSING else want is not old
        if not changed_want:
            continue
        if observed.ownership != "ai":
            conflicts.append(Conflict(fid, f"parameters.{key}", "feature is not AI owned",
                                      None if old is _MISSING else old,
                                      None if remote is _MISSING else remote,
                                      None if want is _MISSING else want))
        elif changed_remote and (remote is _MISSING or want is _MISSING or canonical(remote) != canonical(want)):
            conflicts.append(Conflict(fid, f"parameters.{key}", "concurrent parameter edit",
                                      None if old is _MISSING else old,
                                      None if remote is _MISSING else remote,
                                      None if want is _MISSING else want))
        elif want is _MISSING:
            result.pop(key, None)
        else:
            result[key] = want
    return replace(observed, parameters=result)


def _dependency_conflicts(features: list[Feature]) -> list[Conflict]:
    errors: list[Conflict] = []
    by_id = {f.logical_id: f for f in features}
    seen: set[str] = set()
    visiting: set[str] = set()

    def visit(fid: str) -> None:
        if fid in visiting:
            errors.append(Conflict(fid, "dependencies", "dependency cycle"))
            return
        if fid in seen:
            return
        visiting.add(fid)
        for dep in by_id[fid].dependencies:
            if dep not in by_id:
                errors.append(Conflict(fid, "dependencies", f"missing dependency {dep}"))
            else:
                visit(dep)
        visiting.remove(fid)
        seen.add(fid)

    for f in features:
        visit(f.logical_id)
    position = {f.logical_id: i for i, f in enumerate(features)}
    for f in features:
        for dep in f.dependencies:
            if dep in position and position[dep] >= position[f.logical_id]:
                errors.append(Conflict(f.logical_id, "dependencies",
                                       f"dependency {dep} does not precede feature"))
    return errors


def plan_changes(base: Snapshot, observed: Snapshot, desired: Snapshot) -> Plan:
    """Preserve remote features; merge independent parameter values only.

    A conflict makes the entire returned plan nonexecutable. Deletion and structural
    edits are deliberately unsupported. No remote writes occur here.
    """
    conflicts: list[Conflict] = []
    if base.target != observed.target or base.target != desired.target:
        conflicts.append(Conflict("", "target", "snapshots target different Part Studios"))
    if not observed.complete:
        conflicts.append(Conflict("", "snapshot", "remote readback is incomplete"))
    if not base.complete:
        conflicts.append(Conflict("", "base", "baseline snapshot is incomplete"))
    b = _index(base, conflicts, "base")
    o = _index(observed, conflicts, "observed")
    d = _index(desired, conflicts, "desired")
    merged: list[Feature] = []
    operations: list[Operation] = []

    for current in observed.features:
        fid = current.logical_id
        if fid not in b:
            if fid in d and not current.semantically_equal(d[fid]):
                conflicts.append(Conflict(fid, "feature", "logical ID created concurrently"))
            merged.append(current)
            continue
        if fid not in d:
            if b[fid].ownership == "ai":
                conflicts.append(Conflict(fid, "feature", "AI feature deletion is unsupported"))
            merged.append(current)
            continue
        next_feature = _merge_feature(b[fid], current, d[fid], conflicts)
        merged.append(next_feature)
        if not next_feature.semantically_equal(current):
            operations.append(_op(observed.target, observed.revision, "update", fid, current, next_feature))

    for fid, original in b.items():
        if fid not in o:
            conflicts.append(Conflict(fid, "feature", "base feature missing from remote snapshot"))
    for wanted in desired.features:
        fid = wanted.logical_id
        if fid in o or fid in b:
            continue
        if wanted.ownership != "ai" or wanted.native_id is not None:
            conflicts.append(Conflict(fid, "feature", "new feature must be AI owned without native ID"))
            continue
        merged.append(wanted)
        operations.append(_op(observed.target, observed.revision, "create", fid, None, wanted))

    base_managed_order = [f.logical_id for f in base.features if f.ownership == "ai" and f.logical_id in d]
    desired_managed_order = [f.logical_id for f in desired.features if f.logical_id in base_managed_order]
    if desired_managed_order != base_managed_order:
        conflicts.append(Conflict("", "order", "reordering existing AI features is unsupported"))

    conflicts.extend(_dependency_conflicts(merged))
    # Created features must have predecessors in the remote tree or earlier creates.
    available = set(o)
    for op in operations:
        if op.action == "create" and op.after:
            for dep in op.after.dependencies:
                if dep not in available:
                    conflicts.append(Conflict(op.logical_id, "dependencies",
                                              f"dependency {dep} is not available before creation"))
            available.add(op.logical_id)
    return Plan(observed.target, observed.revision, operations, conflicts,
                Snapshot(observed.target, observed.revision, merged, observed.complete))
