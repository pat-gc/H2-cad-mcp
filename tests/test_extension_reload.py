import json
from pathlib import Path
import subprocess

import pytest

from h2cad.cli import _bridge_action, build_parser
from h2cad.journal import Journal
from h2cad.native import NativeBridge


def setup(tmp_path):
    journal_path = tmp_path / "intent.sqlite"
    journal = Journal(journal_path)
    journal.close()
    config_path = tmp_path / "bridge.json"
    config_path.write_text(json.dumps({"host": "127.0.0.1", "port": 8766,
                                       "token": "test-pairing-" * 4,
                                       "h2cad_journal": str(journal_path)}))
    args = build_parser().parse_args(["extension-reload", "--bridge-config", str(config_path),
                                      "--journal", str(journal_path)])
    return args, journal_path


@pytest.mark.asyncio
async def test_reload_cli_refuses_unknown_journal_intent_before_bridge_call(tmp_path, monkeypatch):
    args, path = setup(tmp_path)
    journal = Journal(path)
    journal.prepare(op_id="test", target="target", expected_revision="a" * 24,
                    action="experimental_depth_edit", logical_id="feature", intent={})
    journal.transition("test", "unknown", error="response missing")
    journal.close()
    monkeypatch.setattr(NativeBridge, "from_config", lambda *a, **kw: pytest.fail("bridge must not be called"))
    result, status = await _bridge_action(args)
    assert (result["status"], result["phase"], status) == ("blocked", "journal", 2)
    journal = Journal(path)
    assert journal.get("test")["state"] == "unknown"
    journal.close()


@pytest.mark.asyncio
async def test_reload_cli_uses_exact_pinned_journal_and_structured_bridge_result(tmp_path, monkeypatch):
    args, path = setup(tmp_path)
    class Bridge:
        calls = 0
        async def reload_extension(self):
            self.calls += 1
            return {"status": "reconnected", "phase": "new_handshake_verified", "request_id": "one"}
        async def close(self):
            pass
    bridge = Bridge()
    monkeypatch.setattr(NativeBridge, "from_config", lambda *a, **kw: bridge)
    result, status = await _bridge_action(args)
    assert result["status"] == "reconnected" and status == 0 and bridge.calls == 1
    args.journal = tmp_path / "other.sqlite"
    with pytest.raises(ValueError, match="same H2 journal"):
        await _bridge_action(args)
    assert bridge.calls == 1


def test_reviewed_native_patch_replays_to_pinned_tree(tmp_path):
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    source = next((path / "upstream/onshape-native" for path in root.parents
                   if (path / "upstream/onshape-native/.git").exists()), None)
    assert source is not None
    checkout = tmp_path / "upstream/onshape-native"
    checkout.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "--quiet", "--local", str(source), str(checkout)], check=True)
    subprocess.run(["git", "checkout", "--quiet", "--detach", "6a4e157f2aa8cb781b8ba84552bd76c180374336"],
                   cwd=checkout, check=True)
    script = root / "scripts/bootstrap.py"
    spec = importlib.util.spec_from_file_location("reload_bootstrap", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.bootstrap(tmp_path, with_fsgen=False, dry_run=False, python="python", sources_only=True)
    assert result["status"] == "sources_ready"
    assert module.native_checkout_reviewed(checkout, module.git_state(checkout)) == 29
    assert subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=checkout, text=True).strip() == module.NATIVE_PATCH29_TREE
