"""Offline geometric validation with explicit coverage and provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fsgen import FsgenCompileError, FsgenUnavailable


@dataclass
class ValidationReport:
    status: str  # passed | partial | failed
    geometry: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    provenance: str = "FSGen local OpenCascade only"
    remote: str = "not_run"
    native_editability: str = "not_run"

    def to_dict(self) -> dict[str, Any]:
        return vars(self).copy()


def validate_fsgen(source: str | Path) -> ValidationReport:
    """Build a script locally; partial OCC builds are never reported as passes."""
    try:
        from fsgen.native.local import build_local
        from fsgen.native.script import trace
    except ImportError as exc:
        raise FsgenUnavailable("install pinned FSGen and its x64 OCP dependencies") from exc
    text = source.read_text() if isinstance(source, Path) else source
    traced = trace(text, variables_mode="studio")
    if not traced.ok:
        return ValidationReport("failed", error=f"trace line {traced.error_line}: {traced.error}")
    local = build_local(traced)
    if not local.ok:
        return ValidationReport("failed", warnings=list(local.warnings), error=local.error)
    return ValidationReport("partial" if local.partial else "passed", local.metrics(),
                            list(local.warnings))
