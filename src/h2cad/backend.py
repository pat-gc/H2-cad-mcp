"""Narrow backend contract for deterministic CAD execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .model import Operation, Snapshot, Target


@dataclass(frozen=True)
class Capabilities:
    category: str
    supported_kinds: frozenset[str] = frozenset()
    atomic_revision: bool = False
    verification: frozenset[str] = frozenset()
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Receipt:
    native_id: str | None = None
    revision: str | None = None
    acknowledgement: dict[str, Any] = field(default_factory=dict)


class Backend(Protocol):
    async def capabilities(self) -> Capabilities: ...

    async def read(self, target: Target) -> Snapshot: ...

    async def apply(self, operation: Operation, target: Target, expected_revision: str) -> Receipt: ...


class BackendError(RuntimeError):
    pass


class Unsupported(BackendError):
    pass


class UncertainWrite(BackendError):
    """Submission may have committed remotely; never replay automatically."""

