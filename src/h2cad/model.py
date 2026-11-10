"""Small, serializable semantic CAD model; no kernel or transport dependencies."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def canonical(value: Any) -> str:
    """Stable JSON representation of supported semantic values."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass
class Target:
    did: str
    wid: str
    eid: str

    def to_dict(self) -> dict[str, Any]:
        return {"did": self.did, "wid": self.wid, "eid": self.eid}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Target:
        return cls(data["did"], data["wid"], data["eid"])


@dataclass
class Feature:
    logical_id: str
    kind: str
    parameters: dict[str, Any]
    dependencies: tuple[str, ...] = ()
    structure: dict[str, Any] = field(default_factory=dict)
    native_id: str | None = None
    ownership: str = "ai"
    regeneration: str = "unknown"

    def semantic_dict(self) -> dict[str, Any]:
        return {"logical_id": self.logical_id, "kind": self.kind,
                "parameters": self.parameters, "dependencies": list(self.dependencies),
                "structure": self.structure, "ownership": self.ownership}

    def semantically_equal(self, other: Feature) -> bool:
        return isinstance(other, Feature) and canonical(self.semantic_dict()) == canonical(other.semantic_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "native_id": self.native_id, "regeneration": self.regeneration}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Feature:
        return cls(data["logical_id"], data["kind"], data.get("parameters", {}),
                   tuple(data.get("dependencies", ())), data.get("structure", {}),
                   data.get("native_id"), data.get("ownership", "ai"),
                   data.get("regeneration", "unknown"))


@dataclass
class Snapshot:
    target: Target
    revision: str
    features: list[Feature]
    complete: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"target": self.target.to_dict(), "revision": self.revision,
                "features": [x.to_dict() for x in self.features], "complete": self.complete}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        return cls(Target.from_dict(data["target"]), data["revision"],
                   [Feature.from_dict(x) for x in data.get("features", [])],
                   data.get("complete", True))


@dataclass
class Operation:
    op_id: str
    action: str
    logical_id: str
    before: Feature | None
    after: Feature | None

    def to_dict(self) -> dict[str, Any]:
        return {"op_id": self.op_id, "action": self.action, "logical_id": self.logical_id,
                "before": self.before.to_dict() if self.before else None,
                "after": self.after.to_dict() if self.after else None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Operation:
        return cls(data["op_id"], data["action"], data["logical_id"],
                   Feature.from_dict(data["before"]) if data.get("before") else None,
                   Feature.from_dict(data["after"]) if data.get("after") else None)


@dataclass
class Conflict:
    logical_id: str
    path: str
    reason: str
    base: Any = None
    observed: Any = None
    desired: Any = None

    def to_dict(self) -> dict[str, Any]:
        return vars(self).copy()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Conflict:
        return cls(**data)


@dataclass
class Plan:
    target: Target
    expected_revision: str
    operations: list[Operation]
    conflicts: list[Conflict]
    merged: Snapshot

    def to_dict(self) -> dict[str, Any]:
        return {"target": self.target.to_dict(), "expected_revision": self.expected_revision,
                "operations": [x.to_dict() for x in self.operations],
                "conflicts": [x.to_dict() for x in self.conflicts], "merged": self.merged.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        return cls(Target.from_dict(data["target"]), data["expected_revision"],
                   [Operation.from_dict(x) for x in data.get("operations", [])],
                   [Conflict.from_dict(x) for x in data.get("conflicts", [])],
                   Snapshot.from_dict(data["merged"]))
