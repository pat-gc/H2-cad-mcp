"""Adversarial bootstrap check for an unrecognized clean descendant."""

import importlib.util
from pathlib import Path
import subprocess

import pytest


@pytest.mark.xfail(strict=True, reason="bootstrap accepts clean Native descendants beyond the reviewed patch")
def test_bootstrap_refuses_unrecognized_native_descendant(tmp_path):
    root = Path(__file__).resolve().parents[3]
    upstream = root / "upstream" / "onshape-native"
    assert upstream.is_dir(), "pinned Native clone required for this test"
    checkout = tmp_path / "upstream" / "onshape-native"
    checkout.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "--quiet", "--local", str(upstream), str(checkout)], check=True)
    subprocess.run(["git", "-c", "user.name=Verifier", "-c", "user.email=verifier@example.invalid",
                    "commit", "--quiet", "--allow-empty", "-m", "unrecognized descendant"],
                   cwd=checkout, check=True)
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("independent_bootstrap", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="refus|unrecognized|neither"):
        module.bootstrap(tmp_path, with_fsgen=False, dry_run=False, python="python", sources_only=True)
