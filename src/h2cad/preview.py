"""Render the actual local solids before any native operation is considered."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from .fsgen import FsgenUnavailable
from .preview_renderer import render_local_solids


def preview_fsgen(source: Path, output: Path) -> dict:
    if output.suffix.lower() != ".png":
        raise ValueError("Preview output must have a .png extension")
    report_path = output.with_suffix(".json")
    if source.resolve() in (output.resolve(), report_path.resolve()):
        raise ValueError("Preview outputs must not overwrite their source")
    try:
        from fsgen.native.local import build_local
        from fsgen.native.script import trace
        from OCP.BRepCheck import BRepCheck_Analyzer
    except ImportError as exc:
        raise FsgenUnavailable("Install pinned FSGen, x64 OpenCascade and rendering dependencies") from exc
    text = source.read_text(encoding="utf-8")
    traced = trace(text, variables_mode="studio")
    if not traced.ok:
        raise ValueError(f"Local source trace failed: {traced.error}")
    built = build_local(traced)
    if not built.ok or built.partial or built.run is None or not built.run.solids:
        raise ValueError("Preview requires a complete, nonempty local solid model")
    if not all(BRepCheck_Analyzer(body.shape).IsValid() for body in built.run.solids):
        raise ValueError("Preview rejected an invalid local solid")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="h2-preview-", dir=output.parent) as temp:
        image = Path(temp) / "model.png"
        if render_local_solids(built, image, "LOCAL OPENCASCADE PREVIEW - NO ONSHAPE WRITE") != image or not image.is_file():
            raise ValueError("Local geometry renderer did not produce an image")
        data = image.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Local geometry renderer did not produce a PNG")
        result = {"status": "rendered", "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
                  "image_sha256": hashlib.sha256(data).hexdigest(), "image": output.name,
                  "geometry": built.metrics(), "kernel_valid_solids": len(built.run.solids),
                  "warnings": list(built.warnings), "provenance": "FSGen local OpenCascade",
                  "renderer": "H2 orthographic solid tessellation (millimetres)",
                  "remote": "not_run", "native_compatibility": "not_checked",
                  "native_editability": "not_run"}
        report = Path(temp) / "report.json"
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        os.replace(image, output)
        os.replace(report, report_path)
    return result
