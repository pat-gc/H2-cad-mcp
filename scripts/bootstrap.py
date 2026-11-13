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
NATIVE_PATCH_TREE = "d121da374a4a8a5c5d0df89748e5ad4593a2f14f"
NATIVE_PATCH2_TREE = "de833d74a6b6841b0ce12f9200b7171596f1ce62"
NATIVE_PATCH3_TREE = "299e8b02e85db5f59e66fddc6c33504cd1ef3bc0"
NATIVE_PATCH4_TREE = "0c96b1bf06273de1ee8043bc45a867d07cf44a89"
NATIVE_PATCH5_TREE = "0f89502a9661f2191a712756775403cbadde06df"
NATIVE_PATCH6_TREE = "f7ef32dc792191ad1fc2da79a0bc8333df4e528f"
NATIVE_PATCH7_TREE = "8f5b4ff2009cec50830be8c75ef41980213abe9d"
NATIVE_PATCH8_TREE = "653ae7c71c702b8ad4f0167201120f87d524cef3"
PATCH = ROOT / "patches" / "onshape-native" / "0001-feat-add-fail-closed-H2-native-readback-probe.patch"
PATCH2 = ROOT / "patches" / "onshape-native" / "0002-fix-bound-native-state-readback-inspection.patch"
PATCH3 = ROOT / "patches" / "onshape-native" / "0003-fix-release-hung-read-only-bridge-work-safely.patch"
PATCH4 = ROOT / "patches" / "onshape-native" / "0004-feat-guard-isolated-Part-Studio-extrusion-depth-edit.patch"
PATCH5 = ROOT / "patches" / "onshape-native" / "0005-feat-advertise-loaded-depth-edit-capability.patch"
PATCH6 = ROOT / "patches" / "onshape-native" / "0006-feat-add-guarded-paired-extension-reload.patch"
PATCH7 = ROOT / "patches" / "onshape-native" / "0007-fix-persist-reload-safety-and-validate-new-worker-in.patch"
PATCH8 = ROOT / "patches" / "onshape-native" / "0008-feat-inspect-native-creation-allocator-surfaces-read.patch"


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
            "native_patches": [str(PATCH), str(PATCH2), str(PATCH3), str(PATCH4), str(PATCH5), str(PATCH6), str(PATCH7), str(PATCH8)],
            "native_patches_present": [PATCH.is_file(), PATCH2.is_file(), PATCH3.is_file(), PATCH4.is_file(), PATCH5.is_file(), PATCH6.is_file(), PATCH7.is_file(), PATCH8.is_file()],
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


def native_checkout_reviewed(path: Path, state: dict) -> int:
    """Return reviewed patch count, independent of local git-am committer SHA."""
    if not state.get("present"):
        return 0
    if not state["clean"]:
        raise RuntimeError("Refusing dirty Native checkout")
    if state["head"] == NATIVE_SHA:
        return 0
    count = run("git", "rev-list", "--count", f"{NATIVE_SHA}..HEAD", cwd=path)
    if count not in {"1", "2", "3", "4", "5", "6", "7", "8"}:
        raise RuntimeError("Unrecognized Native descendant: expected reviewed patch stack only")
    if count == "1":
        if run("git", "rev-parse", "HEAD^", cwd=path) != NATIVE_SHA or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH_TREE:
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 1")
        return 1
    if count == "2":
        if (run("git", "rev-parse", "HEAD^^", cwd=path) != NATIVE_SHA
                or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH2_TREE
                or run("git", "rev-parse", "HEAD^^{tree}", cwd=path) != NATIVE_PATCH_TREE):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 2")
        return 2
    if count == "3" and (run("git", "rev-parse", "HEAD~3", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 3")
    if count == "3":
        return 3
    if count == "4" and (run("git", "rev-parse", "HEAD~4", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH4_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~3^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 4")
    if count == "4":
        return 4
    if count == "5" and (run("git", "rev-parse", "HEAD~5", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH5_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH4_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~3^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~4^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 5")
    if count == "5":
        return 5
    if count == "6" and (run("git", "rev-parse", "HEAD~6", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH6_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH5_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH4_TREE
            or run("git", "rev-parse", "HEAD~3^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~4^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~5^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 6")
    if count == "6":
        return 6
    if count == "7" and (run("git", "rev-parse", "HEAD~7", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH7_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH6_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH5_TREE
            or run("git", "rev-parse", "HEAD~3^{tree}", cwd=path) != NATIVE_PATCH4_TREE
            or run("git", "rev-parse", "HEAD~4^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~5^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~6^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 7")
    if count == "7":
        return 7
    if (run("git", "rev-parse", "HEAD~8", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH8_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH7_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH6_TREE
            or run("git", "rev-parse", "HEAD~3^{tree}", cwd=path) != NATIVE_PATCH5_TREE
            or run("git", "rev-parse", "HEAD~4^{tree}", cwd=path) != NATIVE_PATCH4_TREE
            or run("git", "rev-parse", "HEAD~5^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~6^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~7^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 8")
    return 8


def bootstrap(root: Path, *, with_fsgen: bool, dry_run: bool, python: str, sources_only: bool = False) -> dict:
    if not shutil.which("git"):
        raise RuntimeError("Git is required")
    if not all(path.is_file() for path in (PATCH, PATCH2, PATCH3, PATCH4, PATCH5, PATCH6, PATCH7, PATCH8)):
        raise RuntimeError("Native compatibility patch stack is incomplete")
    if with_fsgen and (struct.calcsize("P") != 8 or platform.machine().lower() not in {"amd64", "x86_64"}):
        raise RuntimeError("FSGen OpenCascade needs an x64 Python process; run this script with x64 Python")
    native = root / "upstream" / "onshape-native"
    fsgen = root / "upstream" / "onshape-fsgen"
    native_state = git_state(native)
    reviewed = native_checkout_reviewed(native, native_state)
    if reviewed == 0:
        ensure_checkout(native, NATIVE_URL, NATIVE_SHA, dry_run=dry_run)
        if not dry_run:
            run("git", "am", str(PATCH), cwd=native)
            if native_checkout_reviewed(native, git_state(native)) != 1:
                raise RuntimeError("Native patch 1 verification failed")
    if reviewed < 2 and not dry_run:
        run("git", "am", str(PATCH2), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 2:
            raise RuntimeError("Native patch 2 verification failed")
    if reviewed < 3 and not dry_run:
        run("git", "am", str(PATCH3), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 3:
            raise RuntimeError("Native patch 3 verification failed")
    if reviewed < 4 and not dry_run:
        run("git", "am", str(PATCH4), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 4:
            raise RuntimeError("Native patch 4 verification failed")
    if reviewed < 5 and not dry_run:
        run("git", "am", str(PATCH5), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 5:
            raise RuntimeError("Native patch 5 verification failed")
    if reviewed < 6 and not dry_run:
        run("git", "am", str(PATCH6), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 6:
            raise RuntimeError("Native patch 6 verification failed")
    if reviewed < 7 and not dry_run:
        run("git", "am", str(PATCH7), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 7:
            raise RuntimeError("Native patch 7 verification failed")
    if reviewed < 8 and not dry_run:
        run("git", "am", str(PATCH8), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 8:
            raise RuntimeError("Native patch 8 verification failed")
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
            "native_patches": [PATCH.name, PATCH2.name, PATCH3.name, PATCH4.name, PATCH5.name, PATCH6.name, PATCH7.name, PATCH8.name], "fsgen_base": FS_SHA if with_fsgen else None,
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
