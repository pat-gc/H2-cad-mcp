"""Generate an offline, auditable concept-car preview. Never connects to Onshape."""

from __future__ import annotations

import json
from pathlib import Path

from fsgen.native.local import build_local, render
from fsgen.native.paste import paste_export
from fsgen.native.script import trace

from h2cad.fsgen import compile_fsgen
from h2cad.model import Snapshot, Target
from h2cad.planner import plan_changes
from h2cad.validation import validate_fsgen


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures" / "car" / "basic_car.fs"
OUTPUT = ROOT / "artifacts" / "car-local-preview"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_large_isometric(run, path: Path) -> None:
    """Shade the actual OCC solids; colors identify parts, not CAD material."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgb
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    from fsgen.fslite import geom as G

    fig = plt.figure(figsize=(13, 8.5), facecolor="#f7f8fa")
    ax = fig.add_axes([0.03, 0.12, 0.77, 0.79], projection="3d", facecolor="#f7f8fa")
    palette = {"Chassis": "#6592b9", "Body": "#2c638e", "Axles": "#a6abb4",
               "Left wheels": "#303c4a", "Right wheels": "#303c4a"}
    for body in run.solids:
        name = str(body.creator).removeprefix("id(").split(".tool", 1)[0]
        BRepMesh_IncrementalMesh(body.shape, 0.00015, False, 0.3, True)
        triangles = []
        for face in G.subshapes(body.shape, G.TopAbs_FACE):
            loc = TopLoc_Location()
            mesh = G.BRep_Tool.Triangulation_s(G.TopoDS.Face(face), loc)
            if mesh is None:
                continue
            transform = loc.Transformation()
            nodes = np.array([[p.X(), p.Y(), p.Z()] for p in
                              (mesh.Node(i).Transformed(transform) for i in range(1, mesh.NbNodes() + 1))]) * 1000
            reversed_face = G.TopoDS.Face(face).Orientation() == 1
            for i in range(1, mesh.NbTriangles() + 1):
                a, b, c = mesh.Triangle(i).Get()
                triangles.append(nodes[[a - 1, c - 1, b - 1]] if reversed_face
                                 else nodes[[a - 1, b - 1, c - 1]])
        triangles = np.asarray(triangles)
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
        light = np.array([-0.35, -0.55, 0.76])
        light /= np.linalg.norm(light)
        shade = 0.55 + 0.45 * np.clip(normals @ light, 0, 1)
        base = np.array(to_rgb(palette[name]))
        colors = np.column_stack([shade[:, None] * base, np.ones(len(shade))])
        ax.add_collection3d(Poly3DCollection(triangles, facecolors=colors, edgecolor="none", zsort="average"))
    ax.set(xlim=(-72, 72), ylim=(-105, 105), zlim=(-12, 78))
    ax.set_box_aspect((144, 210, 90))
    ax.view_init(elev=23, azim=-55)
    ax.set_axis_off()
    fig.text(0.055, 0.925, "LOCAL MODEL PREVIEW", fontsize=20, weight="bold", color="#1c2f42")
    fig.text(0.055, 0.882, "Actual OpenCascade solids  |  Not pushed to Onshape", fontsize=12, color="#526579")
    fig.text(0.77, 0.72, "8 separate solids", fontsize=14, weight="bold", color="#1c2f42")
    fig.text(0.77, 0.665, "1 chassis\n1 body\n2 axles\n4 wheels", fontsize=12,
             linespacing=1.7, color="#394e61", va="top")
    fig.text(0.055, 0.055, "Bounding size: 114 × 180 × 64 mm    •    Concept model; no assembly mates",
             fontsize=11, color="#526579")
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text(encoding="utf-8")
    (OUTPUT / "basic_car.fs").write_text(source, encoding="utf-8")

    traced = trace(source, variables_mode="studio")
    if not traced.ok:
        raise RuntimeError(f"FSGen trace failed: {traced.error}")
    built = build_local(traced)
    if not built.ok or built.partial or built.warnings or built.run is None:
        raise RuntimeError(f"Incomplete local build: {built.report()}")
    model_png = OUTPUT / "car-actual-local-model.png"
    if render(built, model_png, "LOCAL OPENCASCADE MODEL — NOT PUSHED") != model_png:
        raise RuntimeError("Local model rendering failed")
    render_large_isometric(built.run, OUTPUT / "car-isometric-local-model.png")

    validation = validate_fsgen(source)
    if validation.status != "passed" or validation.geometry["parts"] != 8 or validation.warnings:
        raise RuntimeError(f"Local validation failed: {validation.to_dict()}")
    variant_source = source.replace('"bodyHeight", 37 * millimeter',
                                    '"bodyHeight", 42 * millimeter')
    if variant_source == source:
        raise RuntimeError("Body height parameter substitution failed")
    variant = validate_fsgen(variant_source)
    if variant.status != "passed" or variant.geometry["parts"] != 8 or variant.warnings:
        raise RuntimeError(f"Body height variant failed: {variant.to_dict()}")

    feature_script, paste_check = paste_export(traced, "H2 Minimal Car")
    if (not paste_check["ok"] or paste_check["paste_parts"] != 8
            or paste_check["paste_volume_mm3"] != validation.geometry["volume_mm3"]):
        raise RuntimeError(f"Feature Studio export did not match local geometry: {paste_check}")
    (OUTPUT / "onshape-custom-feature.fs").write_text(feature_script, encoding="utf-8")
    write_json(OUTPUT / "custom-feature-local-check.json", paste_check)

    # Placeholder IDs and revision identify a purely simulated empty Part Studio.
    target = Target("SIMULATED_DID", "SIMULATED_WID", "SIMULATED_EID")
    empty = Snapshot(target, "SIMULATED_EMPTY_REVISION", [])
    desired = compile_fsgen(source, target, "SIMULATED_EMPTY_REVISION")
    plan = plan_changes(empty, empty, desired)
    if plan.conflicts or len(plan.operations) != len(desired.features):
        raise RuntimeError("Simulated create plan contains a conflict or missing operation")
    write_json(OUTPUT / "semantic-desired.json", desired.to_dict())
    write_json(OUTPUT / "simulated-empty-create-plan.json", plan.to_dict())

    report = {
        "label": "LOCAL PREVIEW / NOT PUSHED",
        "source": "fixtures/car/basic_car.fs",
        "kernel": "FSGen local OpenCascade",
        "geometry": validation.geometry,
        "warnings": validation.warnings,
        "partial": built.partial,
        "feature_count": len(desired.features),
        "feature_kinds": sorted(set(f.kind for f in desired.features)),
        "simulated_plan": {
            "baseline": "simulated empty Part Studio, not a remote read",
            "operation_count": len(plan.operations),
            "operations": [{"action": op.action, "logical_id": op.logical_id,
                            "kind": op.after.kind if op.after else None,
                            "depends_on": list(op.after.dependencies) if op.after else []}
                           for op in plan.operations],
            "conflicts": [c.to_dict() for c in plan.conflicts],
            "executable_with_current_native_backend": False,
        },
        "parameter_edit_check": {
            "bodyHeight_before_mm": 37,
            "bodyHeight_after_mm": 42,
            "body_count_after": variant.geometry["parts"],
            "volume_delta_mm3": round(variant.geometry["volume_mm3"] -
                                       validation.geometry["volume_mm3"], 4),
        },
        "remote_regeneration": "not_run",
        "native_editability": "not_run",
    }
    write_json(OUTPUT / "validation-report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
