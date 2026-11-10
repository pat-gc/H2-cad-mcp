"""Serial execution with durable submission and semantic readback."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from typing import Any

from .backend import Backend, BackendError, Receipt, Unsupported
from .journal import Journal
from .model import Feature, Operation, Plan, Snapshot, Target


@dataclass(frozen=True)
class StepOutcome:
    op_id: str
    status: str
    reason: str = ""
    receipt: Receipt | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    steps: tuple[StepOutcome, ...]
    revision: str | None = None


def _target_key(target: Target) -> str:
    return f"{target.did}/{target.wid}/{target.eid}"


def _same_target(a: Target, b: Target) -> bool:
    return _target_key(a) == _target_key(b)


def _same_feature(a: Feature, b: Feature) -> bool:
    return (a.logical_id, a.kind, a.parameters, a.dependencies, a.structure, a.native_id, a.ownership) == (
        b.logical_id, b.kind, b.parameters, b.dependencies, b.structure, b.native_id, b.ownership)


def _validate_plan(plan: Plan) -> str | None:
    if not _same_target(plan.target, plan.merged.target):
        return "merged snapshot target differs from plan"
    ids = [op.op_id for op in plan.operations]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        return "operation IDs are empty or duplicated"
    available = {f.logical_id for f in plan.merged.features} - {op.logical_id for op in plan.operations if op.action == "create"}
    for op in plan.operations:
        if op.action not in {"create", "update"} or op.after is None or op.logical_id != op.after.logical_id:
            return "invalid operation action or feature identity"
        if op.after.ownership != "ai":
            return "only AI-owned features may be changed"
        if op.action == "create" and (op.before is not None or op.after.native_id is not None):
            return "create operation reuses a feature identity"
        if op.action == "update" and (op.before is None or op.before.ownership != "ai" or not op.before.native_id
                                      or op.after.native_id != op.before.native_id):
            return "update requires stable AI-owned native identity"
        if any(dep not in available for dep in op.after.dependencies):
            return "operation dependency is absent or out of order"
        available.add(op.logical_id)
    merged = {f.logical_id: f for f in plan.merged.features}
    if len(merged) != len(plan.merged.features) or any(op.logical_id not in merged or not _same_feature(merged[op.logical_id], op.after)
                                                      for op in plan.operations):
        return "merged snapshot omits or changes a planned feature"
    return None


def _check_precondition(op: Operation, snapshot: Snapshot) -> str | None:
    matches = [f for f in snapshot.features if f.logical_id == op.logical_id]
    if op.action == "create":
        return "feature already exists" if matches else None
    if len(matches) != 1 or op.before is None:
        return "feature absent or ambiguous before update"
    if matches[0].ownership != "ai" or not _same_feature(matches[0], op.before):
        return "fresh feature differs from planned before state or is not AI-owned"
    return None


def _verified_feature(operation: Operation, receipt: Receipt, before: Snapshot, snapshot: Snapshot) -> tuple[bool, str, dict[str, Any]]:
    expected: Feature | None = operation.after
    if expected is None:
        return False, "operation has no desired feature", {}
    if not snapshot.complete:
        return False, "native readback is incomplete", {}
    matches = [f for f in snapshot.features if f.logical_id == operation.logical_id]
    if len(matches) != 1:
        return False, "feature identity absent or ambiguous in readback", {"matches": len(matches)}
    actual = matches[0]
    required_id = operation.before.native_id if operation.action == "update" and operation.before else receipt.native_id or expected.native_id
    if operation.action == "update" and receipt.native_id and receipt.native_id != required_id:
        return False, "update changed native feature ID", {"receipt_id": receipt.native_id, "expected_id": required_id}
    if not required_id or actual.native_id != required_id:
        return False, "native feature ID is missing or changed", {"expected_id": required_id, "observed_id": actual.native_id}
    if (actual.kind != expected.kind or actual.parameters != expected.parameters or actual.structure != expected.structure
            or actual.dependencies != expected.dependencies or actual.ownership != expected.ownership):
        return False, "feature semantics differ from intended operation", {"observed_id": actual.native_id}
    if actual.regeneration != "OK":
        return False, "regeneration was not verified OK", {"regeneration": actual.regeneration}
    old_unrelated = {f.logical_id: f for f in before.features if f.logical_id != operation.logical_id}
    new_unrelated = {f.logical_id: f for f in snapshot.features if f.logical_id != operation.logical_id}
    if [f.logical_id for f in before.features if f.logical_id != operation.logical_id] != [
            f.logical_id for f in snapshot.features if f.logical_id != operation.logical_id]:
        return False, "unrelated feature order changed during operation", {}
    if old_unrelated.keys() != new_unrelated.keys() or any(not _same_feature(f, new_unrelated[k]) for k, f in old_unrelated.items()):
        return False, "unrelated feature changed during operation", {}
    if any(f.regeneration == "OK" and new_unrelated[k].regeneration != "OK" for k, f in old_unrelated.items()):
        return False, "previously valid dependent feature failed regeneration", {}
    return True, "", {"native_id": actual.native_id, "regeneration": actual.regeneration, "revision": snapshot.revision}


class Executor:
    def __init__(self, backend: Backend, journal: Journal):
        self.backend = backend
        self.journal = journal
        self._locks: dict[str, asyncio.Lock] = {}

    async def execute(self, plan: Plan, experimental_isolated: bool = False) -> ExecutionResult:
        key = _target_key(plan.target)
        async with self._locks.setdefault(key, asyncio.Lock()):
            if plan.conflicts:
                return ExecutionResult("conflict", (), plan.expected_revision)
            invalid = _validate_plan(plan)
            if invalid:
                return ExecutionResult("invalid_plan", (StepOutcome("", "rejected", invalid),), plan.expected_revision)
            if self.journal.unresolved(key):
                return ExecutionResult("unresolved_prior_write", (), plan.expected_revision)
            caps = await self.backend.capabilities()
            if not caps.atomic_revision and not experimental_isolated:
                return ExecutionResult("atomic_revision_required", (), plan.expected_revision)
            if any(op.action not in {"create", "update"} or op.after is None or op.after.kind not in caps.supported_kinds
                   for op in plan.operations):
                return ExecutionResult("unsupported", (), plan.expected_revision)
            state = await self.backend.read(plan.target)
            if not _same_target(state.target, plan.target) or not state.complete:
                return ExecutionResult("incomplete_baseline", (), state.revision)
            if state.revision != plan.expected_revision:
                return ExecutionResult("stale_plan", (), state.revision)
            touched = {op.logical_id for op in plan.operations}
            state_untouched = {f.logical_id: f for f in state.features if f.logical_id not in touched}
            merged_untouched = {f.logical_id: f for f in plan.merged.features if f.logical_id not in touched}
            if [f.logical_id for f in state.features if f.logical_id not in touched] != [
                    f.logical_id for f in plan.merged.features if f.logical_id not in touched]:
                return ExecutionResult("invalid_plan", (StepOutcome("", "rejected", "merged plan reorders untouched features"),), state.revision)
            if state_untouched.keys() != merged_untouched.keys() or any(
                    not _same_feature(f, merged_untouched[k]) for k, f in state_untouched.items()):
                return ExecutionResult("invalid_plan", (StepOutcome("", "rejected", "merged plan changes untouched features"),), state.revision)
            if not plan.operations:
                self.journal.save_sync_snapshot(key, state.to_dict())
                return ExecutionResult("verified", (), state.revision)
            steps: list[StepOutcome] = []
            for op in plan.operations:
                precondition = _check_precondition(op, state)
                if precondition:
                    steps.append(StepOutcome(op.op_id, "rejected", precondition))
                    return ExecutionResult("stopped", tuple(steps), state.revision)
                if self.journal.get(op.op_id):
                    steps.append(StepOutcome(op.op_id, "duplicate_intent", "operation ID is already journaled"))
                    return ExecutionResult("stopped", tuple(steps), state.revision)
                self.journal.prepare(op_id=op.op_id, target=key, expected_revision=state.revision,
                                     action=op.action, logical_id=op.logical_id,
                                     intent={"operation": op.to_dict(), "before_snapshot": state.to_dict()})
                try:
                    receipt = await self.backend.apply(op, plan.target, state.revision)
                except Unsupported as exc:
                    self.journal.transition(op.op_id, "rejected", error=str(exc))
                    steps.append(StepOutcome(op.op_id, "rejected", str(exc)))
                    return ExecutionResult("stopped", tuple(steps), state.revision)
                except Exception as exc:
                    # A failure after handoff may have committed remotely. No replay.
                    self.journal.transition(op.op_id, "unknown", error=str(exc))
                    steps.append(StepOutcome(op.op_id, "unknown", str(exc)))
                    return ExecutionResult("stopped", tuple(steps), state.revision)
                self.journal.transition(op.op_id, "sent", receipt={"native_id": receipt.native_id, "revision": receipt.revision,
                                                                       "acknowledgement": receipt.acknowledgement})
                try:
                    observed = await self.backend.read(plan.target)
                except Exception as exc:
                    self.journal.transition(op.op_id, "unknown", error=f"readback failed: {exc}")
                    steps.append(StepOutcome(op.op_id, "unknown", f"readback failed: {exc}", receipt))
                    return ExecutionResult("stopped", tuple(steps), state.revision)
                if not _same_target(observed.target, plan.target):
                    ok, reason, evidence = False, "readback target differs", {}
                else:
                    ok, reason, evidence = _verified_feature(op, receipt, state, observed)
                observed_ids = [f.logical_id for f in observed.features]
                intended_seen = [f.logical_id for f in plan.merged.features if f.logical_id in set(observed_ids)]
                if ok and observed_ids != intended_seen:
                    ok, reason, evidence = False, "feature order differs from plan", {}
                if not ok:
                    self.journal.transition(op.op_id, "unknown", observation={"revision": observed.revision}, error=reason)
                    steps.append(StepOutcome(op.op_id, "unknown", reason, receipt, evidence))
                    return ExecutionResult("stopped", tuple(steps), observed.revision)
                self.journal.transition(op.op_id, "observed", observation=evidence)
                steps.append(StepOutcome(op.op_id, "verified", receipt=receipt, evidence=evidence))
                state = observed
            self.journal.save_sync_snapshot(key, state.to_dict())
            return ExecutionResult("verified", tuple(steps), state.revision)

    async def reconcile(self, op_id: str) -> StepOutcome:
        """Read-only inspection of a persisted uncertain write; never resubmit it."""
        row = self.journal.get(op_id)
        if row is None:
            raise ValueError(f"Unknown journal operation {op_id}")
        if row["state"] == "observed":
            return StepOutcome(op_id, "verified", evidence=json.loads(row["observation"] or "{}"))
        if row["state"] == "rejected":
            return StepOutcome(op_id, "rejected", row["error"] or "")
        intent = json.loads(row["intent"])
        operation = Operation.from_dict(intent["operation"])
        before = Snapshot.from_dict(intent["before_snapshot"])
        if row["target"] != _target_key(before.target) or row["logical_id"] != operation.logical_id or row["action"] != operation.action:
            raise ValueError("Journal target or intent does not match stored operation")
        receipt_data = json.loads(row["receipt"]) if row["receipt"] else {}
        receipt = Receipt(receipt_data.get("native_id"), receipt_data.get("revision"), receipt_data.get("acknowledgement") or {})
        if operation.action == "create" and not receipt.native_id:
            return StepOutcome(op_id, "unknown", "create lacks a confirmed native feature ID")
        try:
            observed = await self.backend.read(before.target)
        except Exception as exc:
            return StepOutcome(op_id, "unknown", f"readback failed: {exc}")
        if not _same_target(observed.target, before.target):
            return StepOutcome(op_id, "unknown", "readback target differs")
        ok, reason, evidence = _verified_feature(operation, receipt, before, observed)
        if not ok:
            return StepOutcome(op_id, "unknown", reason, receipt, evidence)
        if row["state"] == "prepared":
            self.journal.transition(op_id, "unknown", error="prepared intent recovered after restart")
        self.journal.transition(op_id, "observed", observation=evidence)
        return StepOutcome(op_id, "verified", receipt=receipt, evidence=evidence)
