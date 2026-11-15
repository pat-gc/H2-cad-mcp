"""CLI boundary tests: pinning must precede any source-run dispatch."""
import json
from types import SimpleNamespace

import pytest

from h2cad import cli, source_run, native_body_scope


@pytest.mark.parametrize("action", ["init", "next", "apply", "record-measurements", "measure-native", "inspect-scope"])
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

    async def record(path, backend, source, given_target, given_journal, evidence):
        assert evidence == tmp_path / "measurements.json"
        await next_step(path, backend, source, given_target, given_journal)
        events[-1] = "record-measurements"
        return {"action": "measurements_recorded"}

    async def measure(path, backend, source, given_target, given_journal):
        await next_step(path, backend, source, given_target, given_journal)
        events[-1] = "measure-native"
        return {"action": "measurements_recorded"}

    async def scope(path, backend, source, given_target, given_journal, logical_id):
        assert logical_id == "Carrier blank"
        await next_step(path, backend, source, given_target, given_journal)
        events[-1] = "inspect-scope"
        return {"action": "scope_inspected", "write_ready": False, "geometry": {"raw": "evidence"}, "history_proofs": {"observed": True}}

    monkeypatch.setattr(cli, "NativeBridge", Bridge)
    monkeypatch.setattr(cli, "NativeBackend", backend)
    monkeypatch.setattr(source_run, "initialize_run", initialize)
    monkeypatch.setattr(source_run, "next_action", next_step)
    monkeypatch.setattr(source_run, "apply_staged", apply)
    monkeypatch.setattr(source_run, "record_measurements", record)
    monkeypatch.setattr(source_run, "measure_native", measure)
    monkeypatch.setattr(native_body_scope, "inspect_current_body_scope", scope)
    argv = ["experimental-source-run", action, str(tmp_path / "source.fs"),
            "--run-state", str(tmp_path / "run.json"), "--journal", str(journal),
            "--bridge-config", str(config), "--tab-id", "123"]
    if action == "record-measurements":
        argv.extend(["--measurements",str(tmp_path / "measurements.json")])
    if action == "inspect-scope":
        argv.extend(["--logical-id", "Carrier blank", "--output", str(tmp_path / "scope.json")])
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
        assert json.loads(output.out)["action"] in {"stage", "browser_allocate", "measurements_recorded", "scope_inspected"}
        if action == "inspect-scope":
            printed = json.loads(output.out)
            saved = json.loads((tmp_path / "scope.json").read_text())
            assert printed["write_ready"] is False and "geometry" not in printed and "history_proofs" not in printed
            assert saved["geometry"] == {"raw": "evidence"} and saved["history_proofs"] == {"observed": True}


@pytest.mark.parametrize("body_op",[None,"extrude-"+"d"*32])
def test_source_extrusion_cli_passes_explicit_target_body_operation(tmp_path,monkeypatch,capsys,body_op):
    from h2cad import native_source_extrusions
    target={"did":"a"*24,"wid":"b"*24,"eid":"c"*24}
    journal=tmp_path/"journal.sqlite";config=tmp_path/"bridge.json";baseline=tmp_path/"baseline.json"
    config.write_text(json.dumps({"h2cad_journal":str(journal)}));baseline.write_text('{"saved":"baseline"}')
    events=[]
    class Bridge:
        @classmethod
        def from_config(cls,path):return cls()
        async def close(self):events.append("closed")
    monkeypatch.setattr(cli,"NativeBridge",Bridge)
    monkeypatch.setattr(cli,"NativeBackend",lambda bridge,tab_id:SimpleNamespace(create_target=target,tab_id=tab_id))
    async def populate(backend,given_target,source,**kw):
        assert kw["target_body_op_id"]==body_op
        assert kw["sketch_op_id"]=="source-sketch-proof" and kw["baseline"]=={"saved":"baseline"}
        assert kw["journal"].path==journal and given_target.to_dict()==target
        events.append("populate")
        return {"status":"observed_source_extrusion"}
    monkeypatch.setattr(native_source_extrusions,"populate_source_extrusion",populate)
    argv=["experimental-populate-source-extrusion",str(tmp_path/"source.fs"),"--journal",str(journal),
        "--bridge-config",str(config),"--tab-id","123","--logical-id","Cut","--sketch-op-id","source-sketch-proof",
        "--baseline",str(baseline)]
    for k,v in target.items():argv.extend(["--"+k,v])
    if body_op:argv.extend(["--target-body-op-id",body_op])
    assert cli.main(argv)==0,capsys.readouterr().err
    assert events==["populate","closed"]


@pytest.mark.parametrize("protected", ["source.fs", "run.json", "journal.sqlite", "bridge.json", "measurements.json"])
def test_source_run_evidence_cannot_overwrite_inputs(tmp_path, monkeypatch, capsys, protected):
    for name in ("source.fs", "run.json", "journal.sqlite", "bridge.json", "measurements.json"):
        (tmp_path / name).write_bytes(b"original")
    async def forbidden(_):
        pytest.fail("Output collision must be rejected before opening the bridge")
    monkeypatch.setattr(cli, "_bridge_action", forbidden)
    argv = ["experimental-source-run", "inspect-scope", str(tmp_path / "source.fs"),
            "--run-state", str(tmp_path / "run.json"), "--journal", str(tmp_path / "journal.sqlite"),
            "--bridge-config", str(tmp_path / "bridge.json"), "--tab-id", "123", "--logical-id", "Carrier blank",
            "--measurements", str(tmp_path / "measurements.json"), "--output", str(tmp_path / protected),
            "--did", "a"*24, "--wid", "b"*24, "--eid", "c"*24]
    assert cli.main(argv) == 1
    assert "must not overwrite" in capsys.readouterr().err
    assert (tmp_path / protected).read_bytes() == b"original"
