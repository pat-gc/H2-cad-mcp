"""Adversarial bootstrap check for an unrecognized clean descendant."""

import importlib.util
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("extra", ["empty", "content"])
def test_bootstrap_refuses_unrecognized_native_descendant(tmp_path, extra):
    ancestors = Path(__file__).resolve().parents
    upstream = next((root / "upstream" / "onshape-native" for root in ancestors
                     if (root / "upstream" / "onshape-native" / ".git").exists()), None)
    assert upstream is not None, "pinned Native clone required for this test"
    assert upstream.is_dir(), "pinned Native clone required for this test"
    checkout = tmp_path / "upstream" / "onshape-native"
    checkout.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "--quiet", "--local", str(upstream), str(checkout)], check=True)
    subprocess.run(["git", "checkout", "--quiet", "--detach", "f5304ed0aa49347dec40911af9c2018d81012604"],
                   cwd=checkout, check=True)
    patch = Path(__file__).resolve().parents[1] / "patches" / "onshape-native" / "0001-feat-add-fail-closed-H2-native-readback-probe.patch"
    subprocess.run(["git", "-c", "user.name=Verifier", "-c", "user.email=verifier@example.invalid",
                    "am", "--quiet", str(patch)], cwd=checkout, check=True)
    if extra == "content":
        (checkout / "unreviewed.txt").write_text("unexpected content\n", encoding="utf-8")
        subprocess.run(["git", "add", "unreviewed.txt"], cwd=checkout, check=True)
    subprocess.run(["git", "-c", "user.name=Verifier", "-c", "user.email=verifier@example.invalid",
                    "commit", "--quiet", "--allow-empty", "-m", "unrecognized descendant"],
                   cwd=checkout, check=True)
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("independent_bootstrap", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="[Uu]nrecognized|[Rr]efusing"):
        module.bootstrap(tmp_path, with_fsgen=False, dry_run=False, python="python", sources_only=True)
