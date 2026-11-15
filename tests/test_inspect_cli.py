import json

from h2cad import cli


def test_inspect_exports_exact_baseline_and_preserves_unicode(tmp_path, monkeypatch, capsys):
    state = {"editingFeatureId": None, "element_microversion": "d"*24,
             "microversion": "e"*24, "tree": {"name": "Carrier – baseline", "children": []}}
    async def inspect(args):
        assert args.command == "inspect" and args.tab_id == 123
        return state, 0
    monkeypatch.setattr(cli, "_bridge_action", inspect)
    config = tmp_path / "bridge.json"
    config.write_text('{"private": "preserve"}')
    output = tmp_path / "evidence" / "baseline.json"
    args = ["inspect", "--did", "a"*24, "--wid", "b"*24, "--eid", "c"*24,
            "--tab-id", "123", "--bridge-config", str(config), "--output", str(output)]
    assert cli.main(args) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == state == json.loads(capsys.readouterr().out)
    args[-1] = str(config)
    assert cli.main(args) == 1
    assert "must not overwrite" in capsys.readouterr().err
    assert json.loads(config.read_text()) == {"private": "preserve"}
