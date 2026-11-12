"""Offline planning and explicit native inspection commands."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from .journal import Journal
from .model import Snapshot, Target
from .native import NativeBackend, NativeBridge


def _target(args: argparse.Namespace) -> Target:
    return Target(args.did, args.wid, args.eid)


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def _snapshot(path: str) -> Snapshot:
    return Snapshot.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _add_target(parser: argparse.ArgumentParser) -> None:
    for name in ("did", "wid", "eid"):
        parser.add_argument(f"--{name}", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="h2cad", description="Guarded browser-native CAD planning")
    commands = parser.add_subparsers(dest="command", required=True)
    compile_cmd = commands.add_parser("compile", help="compile an FSGen script offline to a semantic snapshot")
    compile_cmd.add_argument("source")
    _add_target(compile_cmd)
    compile_cmd.add_argument("--revision", default="local")
    compile_cmd.add_argument("--output", type=Path)
    validate_cmd = commands.add_parser("validate", help="run FSGen local geometry validation")
    validate_cmd.add_argument("source")
    plan_cmd = commands.add_parser("plan", help="three-way dry-run plan from JSON snapshots")
    for name in ("base", "observed", "desired"):
        plan_cmd.add_argument(f"--{name}", required=True)
    plan_cmd.add_argument("--output", type=Path)
    doctor_cmd = commands.add_parser("doctor", help="report local setup and optional bridge health")
    doctor_cmd.add_argument("--bridge-config", type=Path)
    inspect_cmd = commands.add_parser("inspect", help="read exact native editor state without mutation")
    _add_target(inspect_cmd)
    inspect_cmd.add_argument("--bridge-config", type=Path, required=True)
    inspect_cmd.add_argument("--tab-id", type=int)
    probe_cmd = commands.add_parser("native-probe", help="read sketch/extrusion runtime schemas and settings only")
    _add_target(probe_cmd)
    probe_cmd.add_argument("--bridge-config", type=Path, required=True)
    probe_cmd.add_argument("--tab-id", type=int)
    probe_cmd.add_argument("--output", type=Path)
    reconcile_cmd = commands.add_parser("reconcile", help="read-only check of an uncertain journal operation")
    reconcile_cmd.add_argument("op_id")
    reconcile_cmd.add_argument("--journal", type=Path, required=True)
    reconcile_cmd.add_argument("--bridge-config", type=Path, required=True)
    reconcile_cmd.add_argument("--tab-id", type=int)
    depth_cmd = commands.add_parser("experimental-depth-edit", help="edit one saved extrusion in the authorized disposable Part Studio")
    _add_target(depth_cmd)
    depth_cmd.add_argument("--bridge-config", type=Path, required=True)
    depth_cmd.add_argument("--tab-id", type=int, required=True)
    depth_cmd.add_argument("--journal", type=Path, required=True)
    depth_cmd.add_argument("--feature-id", required=True)
    depth_cmd.add_argument("--from-mm", type=float, required=True)
    depth_cmd.add_argument("--to-mm", type=float, required=True)
    return parser


async def _bridge_action(args: argparse.Namespace) -> tuple[object, int]:
    bridge = NativeBridge.from_config(args.bridge_config)
    try:
        if args.command == "doctor":
            health = await bridge.health()
            return {"bridge_protocol": health.get("protocol"), "extension_connected": health.get("extension_connected"),
                    "extension": health.get("extension")}, 0
        backend = NativeBackend(bridge, tab_id=args.tab_id)
        if args.command == "inspect":
            return await backend.raw_state(_target(args)), 0
        if args.command == "native-probe":
            return await backend.modeling_probe(_target(args)), 0
        if args.command == "experimental-depth-edit":
            journal = Journal(args.journal)
            try:
                return await backend.edit_disposable_extrude_depth(
                    _target(args), feature_id=args.feature_id,
                    from_mm=args.from_mm, to_mm=args.to_mm, journal=journal), 0
            finally:
                journal.close()
        from .executor import Executor
        journal = Journal(args.journal)
        try:
            row = journal.get(args.op_id)
            if row and row["action"] == "experimental_depth_edit":
                outcome = await backend.reconcile_disposable_extrude_depth(args.op_id, journal)
                return outcome, 0 if outcome["status"] == "verified" else 2
            outcome = await Executor(backend, journal).reconcile(args.op_id)
            return {"op_id": outcome.op_id, "status": outcome.status, "reason": outcome.reason,
                    "evidence": outcome.evidence}, 0 if outcome.status == "verified" else 2
        finally:
            journal.close()
    finally:
        await bridge.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result_status = 0
        if args.command == "compile":
            from .fsgen import compile_fsgen
            value = compile_fsgen(Path(args.source), _target(args), revision=args.revision).to_dict()
        elif args.command == "validate":
            from .validation import validate_fsgen
            value = validate_fsgen(Path(args.source)).to_dict()
            result_status = 0 if value["status"] == "passed" else 2
        elif args.command == "plan":
            from .planner import plan_changes
            value = plan_changes(_snapshot(args.base), _snapshot(args.observed), _snapshot(args.desired)).to_dict()
            result_status = 2 if value["conflicts"] else 0
        elif args.command == "doctor" and args.bridge_config is None:
            value = {"python": sys.version.split()[0], "package": "h2cad",
                     "bridge": "not checked; supply --bridge-config to inspect an installed companion",
                     "browser_write": "disabled until live native bindings and complete readback are proven"}
        else:
            value, status = asyncio.run(_bridge_action(args))
            if getattr(args, "output", None):
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            _print(value)
            return status
        if getattr(args, "output", None):
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        _print(value)
        return result_status
    except (OSError, ValueError, RuntimeError, KeyError, ImportError) as exc:
        print(f"h2cad: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
