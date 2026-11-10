#!/usr/bin/env python3
"""Pin source dependencies and install H2 CAD without touching a browser."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FS_URL = "https://github.com/Lucasfrit/onshape-fsgen.git"
FS_SHA = "eabcc02ba104005da3de869e613cefe53042fd98"
NATIVE_URL = "https://github.com/godbrigero/onshape-native.git"
NATIVE_SHA = "f5304ed0aa49347dec40911af9c2018d81012604"
PATCH = ROOT / "patches" / "onshape-native" / "0001-feat-add-fail-closed-H2-native-readback-probe.patch"


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f"{' '.join(args[:2])} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def git_state(path: Path) -> dict:
    if not path.exists():
        return {"present": False}
    if not (path / ".git").exists():
        raise RuntimeError(f"Existing path is not a Git checkout: {path}")
    return {"present": True, "head": run("git", "rev-parse", "HEAD", cwd=path),
            "clean": not bool(run("git", "status", "--porcelain", cwd=path))}


def check(root: Path, with_fsgen: bool) -> dict:
    native = git_state(root / "upstream" / "onshape-native")
    fsgen = git_state(root / "upstream" / "onshape-fsgen") if with_fsgen else {"requested": False}
    return {"python": sys.version.split()[0], "python_machine": platform.machine(),
            "python_64_bit": struct.calcsize("P") == 8,
            "git": shutil.which("git"), "native": native, "native_base": NATIVE_SHA,
            "native_patch": str(PATCH), "native_patch_present": PATCH.is_file(),
            "fsgen": fsgen, "fsgen_base": FS_SHA if with_fsgen else None,
            "venv_present": (root / ".venv").is_dir()}


def ensure_checkout(path: Path, url: str, pin: str, *, dry_run: bool) -> None:
    state = git_state(path)
    if state.get("present"):
        if not state["clean"]:
            raise RuntimeError(f"Refusing dirty checkout: {path}")
        if state["head"] != pin:
            raise RuntimeError(f"Existing checkout is at {state['head']}, expected {pin}; refusing overwrite: {path}")
        return
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    run("git", "clone", "--filter=blob:none", url, str(path))
    run("git", "checkout", "--detach", pin, cwd=path)


def bootstrap(root: Path, *, with_fsgen: bool, dry_run: bool, python: str, sources_only: bool = False) -> dict:
    if not shutil.which("git"):
        raise RuntimeError("Git is required")
    if not PATCH.is_file():
        raise RuntimeError(f"Native compatibility patch missing: {PATCH}")
    if with_fsgen and (struct.calcsize("P") != 8 or platform.machine().lower() not in {"amd64", "x86_64"}):
        raise RuntimeError("FSGen OpenCascade needs an x64 Python process; run this script with x64 Python")
    native = root / "upstream" / "onshape-native"
    fsgen = root / "upstream" / "onshape-fsgen"
    native_state = git_state(native)
    if native_state.get("present") and native_state["head"] != NATIVE_SHA:
        if not native_state["clean"]:
            raise RuntimeError("Refusing dirty Native checkout")
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", NATIVE_SHA, "HEAD"], cwd=native,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if ancestor.returncode:
            raise RuntimeError("Existing Native checkout does not descend from the pinned base")
        # A previously applied patch is acceptable only when it reverses cleanly.
        result = subprocess.run(["git", "apply", "--reverse", "--check", str(PATCH)], cwd=native,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            raise RuntimeError("Existing Native checkout is neither pinned base nor an applied compatibility patch")
    else:
        ensure_checkout(native, NATIVE_URL, NATIVE_SHA, dry_run=dry_run)
        if not dry_run:
            run("git", "am", str(PATCH), cwd=native)
    if with_fsgen:
        ensure_checkout(fsgen, FS_URL, FS_SHA, dry_run=dry_run)
    if not dry_run and not sources_only:
        venv = root / ".venv"
        if not venv.exists():
            run(python, "-m", "venv", str(venv))
        interpreter = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        run(str(interpreter), "-m", "pip", "install", "-e", str(root))
        if with_fsgen:
            run(str(interpreter), "-m", "pip", "install", "-e", str(fsgen))
    return {"status": "dry_run" if dry_run else "sources_ready" if sources_only else "installed", "native_base": NATIVE_SHA,
            "native_patch": PATCH.name, "fsgen_base": FS_SHA if with_fsgen else None,
            "core_environment": str(root / ".venv")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="inspect prerequisites without changes")
    mode.add_argument("--dry-run", action="store_true", help="validate and show intended setup without changes")
    parser.add_argument("--with-fsgen", action="store_true", help="install pinned FSGen local geometry support")
    parser.add_argument("--sources-only", action="store_true", help="prepare pinned sources without installing a Python environment")
    parser.add_argument("--python", default=sys.executable, help="Python executable for the core environment")
    args = parser.parse_args(argv)
    try:
        if args.check:
            value = check(args.root.resolve(), args.with_fsgen)
        else:
            value = bootstrap(args.root.resolve(), with_fsgen=args.with_fsgen, dry_run=args.dry_run,
                              python=args.python, sources_only=args.sources_only)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"bootstrap: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
