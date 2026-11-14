"""CLI boundary tests: pinning must precede any source-run dispatch."""
import json
from types import SimpleNamespace

import pytest

from h2cad import cli, source_run


@pytest.mark.parametrize("action", ["init", "next", "apply"])
@pytest.mark.parametrize("mismatch", [None, "journal", "target", "running_target"])
def test_source_run_cli_pins_routes_and_closes(tmp_path, monkeypatch, capsys, action, mismatch):
    target = {"did": "a" * 24, "wid": "b" * 24, "eid": "c" * 24}
    journal = tmp_path / "journal.sqlite"
    config = tmp_path / "bridge.json"
    config.write_text(json.dumps({"h2cad_journal": str(journal if mismatch != "journal" else tmp_path / "other.sqlite")}))
    events = []

    class Bridge:
        @classmethod
        def from_config(cls, path):
            events.append("open")
            return cls()

        async def close(self):
            events.append("close")

        async def health(self):
            return {"h2cad_create_target": target if mismatch != "running_target" else {}}

    def backend(bridge, tab_id):
        return SimpleNamespace(create_target=target if mismatch != "target" else {}, tab_id=tab_id)

    def initialize(path, source, given_target, given_journal):
        assert given_target.to_dict() == target
        assert given_journal.path == journal
        events.append("init")
        return {"action": "stage"}

    async def next_step(path, backend, source, given_target, given_journal):
        assert backend.tab_id == 123
        initialize(path, source, given_target, given_journal)
        events[-1] = "next"
        return {"action": "browser_allocate"}

    async def apply(path, backend, source, given_target, given_journal):
        await next_step(path, backend, source, given_target, given_journal)
        events[-1] = "apply"
        return {"action": "stage"}

    monkeypatch.setattr(cli, "NativeBridge", Bridge)
    monkeypatch.setattr(cli, "NativeBackend", backend)
    monkeypatch.setattr(source_run, "initialize_run", initialize)
    monkeypatch.setattr(source_run, "next_action", next_step)
    monkeypatch.setattr(source_run, "apply_staged", apply)
    argv = ["experimental-source-run", action, str(tmp_path / "source.fs"),
            "--run-state", str(tmp_path / "run.json"), "--journal", str(journal),
            "--bridge-config", str(config), "--tab-id", "123"]
    for key, value in target.items():
        argv.extend(["--" + key, value])
    assert cli.main(argv) == (1 if mismatch else 0)
    output = capsys.readouterr()
    if mismatch:
        assert "pin" in output.err or "creation target" in output.err
        assert events == ([] if mismatch == "journal" else ["open", "close"])
        assert not journal.exists()
    else:
        assert events == ["open", action, "close"]
        assert json.loads(output.out)["action"] in {"stage", "browser_allocate"}
