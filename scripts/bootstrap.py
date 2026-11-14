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
NATIVE_PATCH9_TREE = "e3316d2622145a46f5854b84c33f8e4cf8b5b624"
NATIVE_PATCH10_TREE = "6510ded9f88ebaab38f1990664bfb4067c76a73d"
NATIVE_PATCH11_TREE = "61c1a100a3f98072ed97c9fe94a6aedc0fa46ab0"
NATIVE_PATCH12_TREE = "5e81f5ef20db7d29bcb7cc62728d318fb78efcfa"
NATIVE_PATCH13_TREE = "ebe1c517ed9e3340f1877738bc65298efcd1c409"
NATIVE_PATCH14_TREE = "d1e5fade7ba3ccd29119d4484a5e15ff77a47f9c"
NATIVE_PATCH15_TREE = "f1798b9733b115a2e850676c6465711155e0e73f"
NATIVE_PATCH16_TREE = "a61b53db4daa164399694216134bf0724b7f0821"
NATIVE_PATCH17_TREE = "3b431b5b9c03026e6c74e5e6e5c8cffdc072e00f"
NATIVE_PATCH18_TREE = "5d67b75bcbe8908319ae3576e6a342ce8e91f163"
NATIVE_PATCH19_TREE = "227c8dd6ba59877e1bf2e006d690ef5d7bb5aef8"
NATIVE_PATCH20_TREE = "f2e900c49c3c8deca2267e9ab39fdfbde0717457"
NATIVE_PATCH21_TREE = "eaf10023097414ac6f588f304ea5e0cdfe59e4ad"
NATIVE_PATCH22_TREE = "b874c28ec8238ba93d721810f4803614ee9eff45"
NATIVE_PATCH23_TREE = "9b19efc4bba70a1ad281033e681c2bed3784e529"
NATIVE_PATCH24_TREE = "c6681ede64ebfb6c46ab7f5faf3df07eba1d8a27"
NATIVE_PATCH25_TREE = "bce495e1be2f31d5b8f5566ed3de8d284e3b7412"
NATIVE_PATCH26_TREE = "4851c459e6576672b6d0e73c3e1dfa87f4e4f930"
NATIVE_PATCH27_TREE = "4e97dee2c565fdf8c2c4d2a39fe0c7fe55f30091"
NATIVE_PATCH28_TREE = "5a7eea3d14f6e991d5011bb40cdfbfdc2b528c09"
NATIVE_PATCH29_TREE = "895390d5bdf06bc05ce9a09ee0b8b2d0e1c3a159"
NATIVE_PATCH30_TREE = "a1c2f9c9a98566b6ac66859654a7ddd5b692a08d"
NATIVE_PATCH31_TREE = "fd27c241e25af3c6e38f6cc968c0c42c5273ba93"
PATCH = ROOT / "patches" / "onshape-native" / "0001-feat-add-fail-closed-H2-native-readback-probe.patch"
PATCH2 = ROOT / "patches" / "onshape-native" / "0002-fix-bound-native-state-readback-inspection.patch"
PATCH3 = ROOT / "patches" / "onshape-native" / "0003-fix-release-hung-read-only-bridge-work-safely.patch"
PATCH4 = ROOT / "patches" / "onshape-native" / "0004-feat-guard-isolated-Part-Studio-extrusion-depth-edit.patch"
PATCH5 = ROOT / "patches" / "onshape-native" / "0005-feat-advertise-loaded-depth-edit-capability.patch"
PATCH6 = ROOT / "patches" / "onshape-native" / "0006-feat-add-guarded-paired-extension-reload.patch"
PATCH7 = ROOT / "patches" / "onshape-native" / "0007-fix-persist-reload-safety-and-validate-new-worker-in.patch"
PATCH8 = ROOT / "patches" / "onshape-native" / "0008-feat-inspect-native-creation-allocator-surfaces-read.patch"
PATCH9 = ROOT / "patches" / "onshape-native" / "0009-fix-remove-broad-editor-traversal-from-creation-prob.patch"
PATCH10 = ROOT / "patches" / "onshape-native" / "0010-feat-populate-one-UI-allocated-native-sketch-from-so.patch"
PATCH11 = ROOT / "patches" / "onshape-native" / "0011-fix-classify-pre-dispatch-native-rejection-and-bound.patch"
PATCH12 = ROOT / "patches" / "onshape-native" / "0012-fix-finalize-applied-invalid-sketch-only-after-exact.patch"
PATCH13 = ROOT / "patches" / "onshape-native" / "0013-fix-ignore-only-per-tab-tolerance-node-during-exact-.patch"
PATCH14 = ROOT / "patches" / "onshape-native" / "0014-fix-anchor-source-rectangle-with-an-internal-fixed-p.patch"
PATCH15 = ROOT / "patches" / "onshape-native" / "0015-fix-gate-fixed-origin-sketch-on-loaded-page-capabili.patch"
PATCH16 = ROOT / "patches" / "onshape-native" / "0016-feat-reconcile-manually-completed-Top-sketch-begin-f.patch"
PATCH17 = ROOT / "patches" / "onshape-native" / "0017-fix-wait-for-sketch-plane-editor-readiness-before-To.patch"
PATCH18 = ROOT / "patches" / "onshape-native" / "0018-feat-reconcile-saved-source-sketch-after-normal-edit.patch"
PATCH19 = ROOT / "patches" / "onshape-native" / "0019-feat-verify-source-extrusion-face-and-finish-normal-.patch"
PATCH20 = ROOT / "patches" / "onshape-native" / "0020-fix-recheck-exact-editor-after-extrusion-reads-and-b.patch"
PATCH21 = ROOT / "patches" / "onshape-native" / "0021-feat-reconcile-delayed-saved-native-source-extrusion.patch"
PATCH22 = ROOT / "patches" / "onshape-native" / "0022-fix-retain-source-write-intent-through-delayed-edito.patch"
PATCH23 = ROOT / "patches" / "onshape-native" / "0023-fix-retain-guard-until-every-source-candidate-is-obs.patch"
PATCH24 = ROOT / "patches" / "onshape-native" / "0024-fix-retire-confirmed-page-marker-and-fail-fast-on-ed.patch"
PATCH25 = ROOT / "patches" / "onshape-native" / "0025-feat-finish-source-sketch-through-normal-editor-Save.patch"
PATCH26 = ROOT / "patches" / "onshape-native" / "0026-feat-start-source-bound-native-extrusion-in-explicit.patch"
PATCH27 = ROOT / "patches" / "onshape-native" / "0027-feat-bind-Top-sketch-through-verified-native-query.patch"
PATCH28 = ROOT / "patches" / "onshape-native" / "0028-feat-expose-guarded-H2-plate-CLI-through-existing-MCP.patch"
PATCH29 = ROOT / "patches" / "onshape-native" / "0029-fix-read-Top-query-dependency-flag-from-evaluation.patch"
PATCH30 = ROOT / "patches" / "onshape-native" / "0030-report-bounded-native-read-phase.patch"
PATCH31 = ROOT / "patches" / "onshape-native" / "0031-describe-feature-save-control.patch"


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
            "native_patches": [str(PATCH), str(PATCH2), str(PATCH3), str(PATCH4), str(PATCH5), str(PATCH6), str(PATCH7), str(PATCH8), str(PATCH9), str(PATCH10), str(PATCH11), str(PATCH12), str(PATCH13), str(PATCH14), str(PATCH15), str(PATCH16), str(PATCH17), str(PATCH18), str(PATCH19), str(PATCH20), str(PATCH21), str(PATCH22), str(PATCH23), str(PATCH24), str(PATCH25), str(PATCH26), str(PATCH27), str(PATCH28), str(PATCH29), str(PATCH30), str(PATCH31)],
            "native_patches_present": [PATCH.is_file(), PATCH2.is_file(), PATCH3.is_file(), PATCH4.is_file(), PATCH5.is_file(), PATCH6.is_file(), PATCH7.is_file(), PATCH8.is_file(), PATCH9.is_file(), PATCH10.is_file(), PATCH11.is_file(), PATCH12.is_file(), PATCH13.is_file(), PATCH14.is_file(), PATCH15.is_file(), PATCH16.is_file(), PATCH17.is_file(), PATCH18.is_file(), PATCH19.is_file(), PATCH20.is_file(), PATCH21.is_file(), PATCH22.is_file(), PATCH23.is_file(), PATCH24.is_file(), PATCH25.is_file(), PATCH26.is_file(), PATCH27.is_file(), PATCH28.is_file(), PATCH29.is_file(), PATCH30.is_file(), PATCH31.is_file()],
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
    if count not in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31"}:
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
    if count == "8" and (run("git", "rev-parse", "HEAD~8", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH8_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH7_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH6_TREE
            or run("git", "rev-parse", "HEAD~3^{tree}", cwd=path) != NATIVE_PATCH5_TREE
            or run("git", "rev-parse", "HEAD~4^{tree}", cwd=path) != NATIVE_PATCH4_TREE
            or run("git", "rev-parse", "HEAD~5^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~6^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~7^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 8")
    if count == "8":
        return 8
    if count == "31":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE,
                 NATIVE_PATCH25_TREE, NATIVE_PATCH26_TREE, NATIVE_PATCH27_TREE,
                 NATIVE_PATCH28_TREE, NATIVE_PATCH29_TREE, NATIVE_PATCH30_TREE,
                 NATIVE_PATCH31_TREE]
        if run("git", "rev-parse", "HEAD~31", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{30-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 31")
        return 31
    if count == "30":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE,
                 NATIVE_PATCH25_TREE, NATIVE_PATCH26_TREE, NATIVE_PATCH27_TREE,
                 NATIVE_PATCH28_TREE, NATIVE_PATCH29_TREE, NATIVE_PATCH30_TREE]
        if run("git", "rev-parse", "HEAD~30", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{29-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 30")
        return 30
    if count == "29":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE,
                 NATIVE_PATCH25_TREE, NATIVE_PATCH26_TREE, NATIVE_PATCH27_TREE,
                 NATIVE_PATCH28_TREE, NATIVE_PATCH29_TREE]
        if run("git", "rev-parse", "HEAD~29", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{28-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 29")
        return 29
    if count == "28":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE,
                 NATIVE_PATCH25_TREE, NATIVE_PATCH26_TREE, NATIVE_PATCH27_TREE,
                 NATIVE_PATCH28_TREE]
        if run("git", "rev-parse", "HEAD~28", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{27-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 28")
        return 28
    if count == "27":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE,
                 NATIVE_PATCH25_TREE, NATIVE_PATCH26_TREE, NATIVE_PATCH27_TREE]
        if run("git", "rev-parse", "HEAD~27", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{26-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 27")
        return 27
    if count == "26":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE,
                 NATIVE_PATCH25_TREE, NATIVE_PATCH26_TREE]
        if run("git", "rev-parse", "HEAD~26", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{25-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 26")
        return 26
    if count == "25":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE,
                 NATIVE_PATCH25_TREE]
        if run("git", "rev-parse", "HEAD~25", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{24-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 25")
        return 25
    if count == "24":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE, NATIVE_PATCH24_TREE]
        if run("git", "rev-parse", "HEAD~24", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{23-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 24")
        return 24
    if count == "23":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE, NATIVE_PATCH23_TREE]
        if run("git", "rev-parse", "HEAD~23", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{22-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 23")
        return 23
    if count == "22":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE,
                 NATIVE_PATCH22_TREE]
        if run("git", "rev-parse", "HEAD~22", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{21-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 22")
        return 22
    if count == "21":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE, NATIVE_PATCH21_TREE]
        if run("git", "rev-parse", "HEAD~21", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{20-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 21")
        return 21
    if count == "20":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE, NATIVE_PATCH20_TREE]
        if run("git", "rev-parse", "HEAD~20", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{19-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 20")
        return 20
    if count == "19":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE,
                 NATIVE_PATCH19_TREE]
        if run("git", "rev-parse", "HEAD~19", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{18-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 19")
        return 19
    if count == "18":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE, NATIVE_PATCH18_TREE]
        if run("git", "rev-parse", "HEAD~18", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{17-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 18")
        return 18
    if count == "17":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE, NATIVE_PATCH17_TREE]
        if run("git", "rev-parse", "HEAD~17", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{16-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 17")
        return 17
    if count == "16":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE,
                 NATIVE_PATCH16_TREE]
        if run("git", "rev-parse", "HEAD~16", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{15-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 16")
        return 16
    if count == "15":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE, NATIVE_PATCH15_TREE]
        if run("git", "rev-parse", "HEAD~15", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{14-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 15")
        return 15
    if count == "14":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE, NATIVE_PATCH14_TREE]
        if run("git", "rev-parse", "HEAD~14", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{13-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 14")
        return 14
    if count == "13":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE,
                 NATIVE_PATCH13_TREE]
        if run("git", "rev-parse", "HEAD~13", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{12-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 13")
        return 13
    if count == "12":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE, NATIVE_PATCH12_TREE]
        if run("git", "rev-parse", "HEAD~12", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{11-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 12")
        return 12
    if count == "11":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE,
                 NATIVE_PATCH10_TREE, NATIVE_PATCH11_TREE]
        if run("git", "rev-parse", "HEAD~11", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{10-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 11")
        return 11
    if count == "10":
        trees = [NATIVE_PATCH_TREE, NATIVE_PATCH2_TREE, NATIVE_PATCH3_TREE,
                 NATIVE_PATCH4_TREE, NATIVE_PATCH5_TREE, NATIVE_PATCH6_TREE,
                 NATIVE_PATCH7_TREE, NATIVE_PATCH8_TREE, NATIVE_PATCH9_TREE, NATIVE_PATCH10_TREE]
        if run("git", "rev-parse", "HEAD~10", cwd=path) != NATIVE_SHA or any(
                run("git", "rev-parse", f"HEAD~{9-index}^{{tree}}", cwd=path) != tree
                for index, tree in enumerate(trees)):
            raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 10")
        return 10
    if (run("git", "rev-parse", "HEAD~9", cwd=path) != NATIVE_SHA
            or run("git", "rev-parse", "HEAD^{tree}", cwd=path) != NATIVE_PATCH9_TREE
            or run("git", "rev-parse", "HEAD~1^{tree}", cwd=path) != NATIVE_PATCH8_TREE
            or run("git", "rev-parse", "HEAD~2^{tree}", cwd=path) != NATIVE_PATCH7_TREE
            or run("git", "rev-parse", "HEAD~3^{tree}", cwd=path) != NATIVE_PATCH6_TREE
            or run("git", "rev-parse", "HEAD~4^{tree}", cwd=path) != NATIVE_PATCH5_TREE
            or run("git", "rev-parse", "HEAD~5^{tree}", cwd=path) != NATIVE_PATCH4_TREE
            or run("git", "rev-parse", "HEAD~6^{tree}", cwd=path) != NATIVE_PATCH3_TREE
            or run("git", "rev-parse", "HEAD~7^{tree}", cwd=path) != NATIVE_PATCH2_TREE
            or run("git", "rev-parse", "HEAD~8^{tree}", cwd=path) != NATIVE_PATCH_TREE):
        raise RuntimeError("Unrecognized Native content or ancestry at reviewed patch 9")
    return 9


def bootstrap(root: Path, *, with_fsgen: bool, dry_run: bool, python: str, sources_only: bool = False) -> dict:
    if not shutil.which("git"):
        raise RuntimeError("Git is required")
    if not all(path.is_file() for path in (PATCH, PATCH2, PATCH3, PATCH4, PATCH5, PATCH6, PATCH7, PATCH8, PATCH9, PATCH10, PATCH11, PATCH12, PATCH13, PATCH14, PATCH15, PATCH16, PATCH17, PATCH18, PATCH19, PATCH20, PATCH21, PATCH22, PATCH23, PATCH24, PATCH25, PATCH26, PATCH27, PATCH28, PATCH29, PATCH30, PATCH31)):
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
    if reviewed < 9 and not dry_run:
        run("git", "am", str(PATCH9), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 9:
            raise RuntimeError("Native patch 9 verification failed")
    if reviewed < 10 and not dry_run:
        run("git", "am", str(PATCH10), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 10:
            raise RuntimeError("Native patch 10 verification failed")
    if reviewed < 11 and not dry_run:
        run("git", "am", str(PATCH11), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 11:
            raise RuntimeError("Native patch 11 verification failed")
    if reviewed < 12 and not dry_run:
        run("git", "am", str(PATCH12), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 12:
            raise RuntimeError("Native patch 12 verification failed")
    if reviewed < 13 and not dry_run:
        run("git", "am", str(PATCH13), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 13:
            raise RuntimeError("Native patch 13 verification failed")
    if reviewed < 14 and not dry_run:
        run("git", "am", str(PATCH14), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 14:
            raise RuntimeError("Native patch 14 verification failed")
    if reviewed < 15 and not dry_run:
        run("git", "am", str(PATCH15), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 15:
            raise RuntimeError("Native patch 15 verification failed")
    if reviewed < 16 and not dry_run:
        run("git", "am", str(PATCH16), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 16:
            raise RuntimeError("Native patch 16 verification failed")
    if reviewed < 17 and not dry_run:
        run("git", "am", str(PATCH17), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 17:
            raise RuntimeError("Native patch 17 verification failed")
    if reviewed < 18 and not dry_run:
        run("git", "am", str(PATCH18), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 18:
            raise RuntimeError("Native patch 18 verification failed")
    if reviewed < 19 and not dry_run:
        run("git", "am", str(PATCH19), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 19:
            raise RuntimeError("Native patch 19 verification failed")
    if reviewed < 20 and not dry_run:
        run("git", "am", str(PATCH20), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 20:
            raise RuntimeError("Native patch 20 verification failed")
    if reviewed < 21 and not dry_run:
        run("git", "am", str(PATCH21), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 21:
            raise RuntimeError("Native patch 21 verification failed")
    if reviewed < 22 and not dry_run:
        run("git", "am", str(PATCH22), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 22:
            raise RuntimeError("Native patch 22 verification failed")
    if reviewed < 23 and not dry_run:
        run("git", "am", str(PATCH23), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 23:
            raise RuntimeError("Native patch 23 verification failed")
    if reviewed < 24 and not dry_run:
        run("git", "am", str(PATCH24), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 24:
            raise RuntimeError("Native patch 24 verification failed")
    if reviewed < 25 and not dry_run:
        run("git", "am", str(PATCH25), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 25:
            raise RuntimeError("Native patch 25 verification failed")
    if reviewed < 26 and not dry_run:
        run("git", "am", str(PATCH26), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 26:
            raise RuntimeError("Native patch 26 verification failed")
    if reviewed < 27 and not dry_run:
        run("git", "am", str(PATCH27), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 27:
            raise RuntimeError("Native patch 27 verification failed")
    if reviewed < 28 and not dry_run:
        run("git", "am", str(PATCH28), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 28:
            raise RuntimeError("Native patch 28 verification failed")
    if reviewed < 29 and not dry_run:
        run("git", "am", str(PATCH29), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 29:
            raise RuntimeError("Native patch 29 verification failed")
    if reviewed < 30 and not dry_run:
        run("git", "am", str(PATCH30), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 30:
            raise RuntimeError("Native patch 30 verification failed")
    if reviewed < 31 and not dry_run:
        run("git", "am", str(PATCH31), cwd=native)
        if native_checkout_reviewed(native, git_state(native)) != 31:
            raise RuntimeError("Native patch 31 verification failed")
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
            "native_patches": [PATCH.name, PATCH2.name, PATCH3.name, PATCH4.name, PATCH5.name, PATCH6.name, PATCH7.name, PATCH8.name, PATCH9.name, PATCH10.name, PATCH11.name, PATCH12.name, PATCH13.name, PATCH14.name, PATCH15.name, PATCH16.name, PATCH17.name, PATCH18.name, PATCH19.name, PATCH20.name, PATCH21.name, PATCH22.name, PATCH23.name, PATCH24.name, PATCH25.name, PATCH26.name, PATCH27.name, PATCH28.name, PATCH29.name, PATCH30.name, PATCH31.name], "fsgen_base": FS_SHA if with_fsgen else None,
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


