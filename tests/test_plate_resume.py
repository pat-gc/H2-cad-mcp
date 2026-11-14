"""Resume only a proven source sketch, never a partially submitted extrusion."""

import json
from pathlib import Path

import pytest

from h2cad import cli
from h2cad.fsgen import compile_fsgen
from h2cad.journal import Journal
from h2cad.model import Target
from h2cad.native import stage_minimal_pair


SOURCE = Path(__file__).resolve().parents[1] / "fixtures/native/minimal_plate.fs"
TARGET = Target("4e078dec822b4e509616b1cb", "af0627de07264acf086e646a",
                "3a4e8933dde1c594115a657f")
KEY = f"{TARGET.did}/{TARGET.wid}/{TARGET.eid}"


def seed(path, *, state="observed", target=KEY, evidence_id="savedSketch"):
    snapshot = compile_fsgen(SOURCE, TARGET)
    blueprint = stage_minimal_pair(snapshot)
    prefix = snapshot.features[0].structure["fsgen_native"]["entities"][0]["entityId"].rsplit(".", 1)[0]
    journal = Journal(path)
    journal.prepare(op_id="sketch-original", target=target, expected_revision="a" * 24,
                    action="experimental_sketch_populate", logical_id=blueprint.sketch_logical_id,
                    intent={"feature_id": "savedSketch", "blueprint": blueprint.to_dict(),
                            "entity_prefix": prefix})
    journal.transition("sketch-original", "sent")
    if state == "observed":
        journal.transition("sketch-original", state, observation={"feature_id": evidence_id,
                           "origin_verified": True, "constraint_graph_verified": True})
    journal.close()


def args_for(tmp_path, source=SOURCE):
    journal = tmp_path / "journal.sqlite"
    config = tmp_path / "bridge.json"
    config.write_text(json.dumps({"h2cad_journal": str(journal)}))
    return cli.build_parser().parse_args([
        "experimental-create-plate", str(source), "--did", TARGET.did, "--wid", TARGET.wid,
        "--eid", TARGET.eid, "--bridge-config", str(config), "--journal", str(journal),
        "--tab-id", "17", "--resume-sketch-op-id", "sketch-original"])


def fake_backend(monkeypatch, *, existing_extrusion=False):
    calls = []

    class Bridge:
        async def close(self):
            pass

    class Backend:
        def __init__(self, bridge, *, tab_id):
            pass

        async def begin_test_source_extrude(self, target, source, *, sketch_op_id, journal):
            calls.append("begin_extrude")
            assert target == TARGET and sketch_op_id == "sketch-original"
            # The real backend independently requires a sole saved sketch in an
            # idle studio before allocation. Propagate that failure, no fallback.
            if existing_extrusion:
                raise RuntimeError("One saved source sketch in an idle test studio is required")
            return {"op_id": "begin-extrude-new"}

        async def populate_test_extrude(self, target, source, *, sketch_op_id, journal):
            calls.append("populate_extrude")
            assert sketch_op_id == "sketch-original"
            return {"op_id": "extrude-new"}

    monkeypatch.setattr(cli.NativeBridge, "from_config", classmethod(lambda cls, path: Bridge()))
    monkeypatch.setattr(cli, "NativeBackend", Backend)
    return calls


@pytest.mark.asyncio
async def test_resume_skips_both_sketch_stages(tmp_path, monkeypatch):
    args = args_for(tmp_path)
    seed(args.journal)
    calls = fake_backend(monkeypatch)
    result, status = await cli._bridge_action(args)
    assert status == 0
    assert calls == ["begin_extrude", "populate_extrude"]
    assert result["begin_sketch"] is None and result["sketch"]["resumed"] is True
    assert result["solid_geometry_verified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["depth", "dimensions", "entities"])
async def test_resume_rejects_changed_source_semantics(tmp_path, monkeypatch, change):
    altered = SOURCE.read_text()
    before, after = {"depth": ("5 * millimeter", "6 * millimeter"),
                     "dimensions": ("vector(40, 20)", "vector(45, 20)"),
                     "entities": ('"box"', '"differentBox"')}[change]
    source = tmp_path / "changed.fs"
    source.write_text(altered.replace(before, after))
    args = args_for(tmp_path, source)
    seed(args.journal)
    calls = fake_backend(monkeypatch)
    with pytest.raises(ValueError, match="source differs"):
        await cli._bridge_action(args)
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("seed_options, error", [
    ({"state": "sent"}, "Unresolved CAD write"),
    ({"target": "another/target/studio"}, "for this target"),
    ({"evidence_id": "differentSketch"}, "identity"),
])
async def test_resume_rejects_uncertainty_or_wrong_identity(tmp_path, monkeypatch, seed_options, error):
    args = args_for(tmp_path)
    seed(args.journal, **seed_options)
    calls = fake_backend(monkeypatch)
    with pytest.raises(ValueError, match=error):
        await cli._bridge_action(args)
    assert calls == []


@pytest.mark.asyncio
async def test_existing_extrusion_preflight_failure_does_not_populate_or_restart(tmp_path, monkeypatch):
    args = args_for(tmp_path)
    seed(args.journal)
    calls = fake_backend(monkeypatch, existing_extrusion=True)
    with pytest.raises(RuntimeError, match="idle test studio"):
        await cli._bridge_action(args)
    assert calls == ["begin_extrude"]
