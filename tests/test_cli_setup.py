import json
from pathlib import Path

from h2cad.cli import main
from h2cad.model import Feature, Snapshot, Target


def test_bootstrap_check_and_dry_run_are_read_only(tmp_path, capsys):
    import importlib.util
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("h2_bootstrap", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check", "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["native"]["present"] is False
    assert module.main(["--dry-run", "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"
    assert not list(tmp_path.iterdir())


def test_bootstrap_applies_native_patch_to_pinned_local_clone(tmp_path):
    import importlib.util
    import subprocess
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("h2_bootstrap_clone", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    local_clone = Path(__file__).resolve().parents[3] / "upstream" / "onshape-native"
    if not local_clone.is_dir():
        import pytest
        pytest.skip("pinned upstream clone unavailable")
    module.NATIVE_URL = str(local_clone)
    result = module.bootstrap(tmp_path, with_fsgen=False, dry_run=False, python="python", sources_only=True)
    assert result["status"] == "sources_ready"
    checkout = tmp_path / "upstream" / "onshape-native"
    parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=checkout, text=True).strip()
    assert parent == module.NATIVE_SHA
    assert "h2Readback" in (checkout / "extension" / "page-adapter.js").read_text(encoding="utf-8")
    # Re-running setup leaves the reviewed checkout intact.
    assert module.bootstrap(tmp_path, with_fsgen=False, dry_run=False, python="python", sources_only=True)["status"] == "sources_ready"


def test_cli_doctor_and_plan_json(tmp_path, capsys):
    assert main(["doctor"]) == 0
    assert "disabled" in json.loads(capsys.readouterr().out)["browser_write"]
    target = Target("a" * 24, "b" * 24, "c" * 24)
    base = Snapshot(target, "d" * 24, [Feature("f", "extrude", {"depth": "5 mm"}, native_id="native-f")])
    desired = Snapshot(target, "d" * 24, [Feature("f", "extrude", {"depth": "6 mm"}, native_id="native-f")])
    paths = []
    for name, snapshot in (("base", base), ("observed", base), ("desired", desired)):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")
        paths += [f"--{name}", str(path)]
    assert main(["plan", *paths]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["operations"][0]["action"] == "update"
    assert plan["operations"][0]["after"]["parameters"]["depth"] == "6 mm"


def test_cli_compile_reads_path_and_stages_native_rectangle(tmp_path, capsys):
    from h2cad.model import Feature
    from h2cad.native import stage_rectangle

    source = '''FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");
export function build(context is Context, id is Id)
{
    var s = newSketch(context, id + "Outline", { "sketchPlane" : qCreatedBy(makeId("Top"), EntityType.FACE) });
    skRectangle(s, "box", { "firstCorner" : vector(0, 0) * millimeter,
                            "secondCorner" : vector(40, 20) * millimeter });
    skSolve(s);
    extrude(context, id + "Solid", { "entities" : qSketchRegion(id + "Outline"),
        "endBound" : BoundingType.BLIND, "depth" : 5 * millimeter });
}
'''
    path = tmp_path / "part.fs"
    path.write_text(source, encoding="utf-8")
    assert main(["compile", str(path), "--did", "a" * 24, "--wid", "b" * 24, "--eid", "c" * 24]) == 0
    compiled = Snapshot.from_dict(json.loads(capsys.readouterr().out))
    sketch = next(f for f in compiled.features if f.kind == "newSketch")
    schema = {"name": "ui.sketch.GBTUiSketchAddRectangleCall", "defaults":
              dict.fromkeys(["firstX", "firstY", "oppositeX", "oppositeY", "sketchEntityId",
                             "inferenceSetId", "isConstruction"])}
    staged = stage_rectangle(sketch, bindings={"provenance": "live_editor", "sketch_feature_id": "fresh",
                              "sketch_entity_id": "entity", "inference_set_id": "inference",
                              "element_microversion": "d" * 24}, schema=schema)
    assert staged.body["oppositeX"] == .04
    assert staged.body["oppositeY"] == .02
