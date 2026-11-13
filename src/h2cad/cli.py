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
    blueprint_cmd = commands.add_parser("native-blueprint", help="normalize a literal sketch and extrusion plan offline")
    blueprint_cmd.add_argument("source")
    _add_target(blueprint_cmd)
    blueprint_cmd.add_argument("--output", type=Path)
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
    creation_probe = commands.add_parser("native-create-probe", help="read editor allocation method names without creating CAD")
    _add_target(creation_probe)
    creation_probe.add_argument("--bridge-config", type=Path, required=True)
    creation_probe.add_argument("--tab-id", type=int, required=True)
    creation_probe.add_argument("--output", type=Path)
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
    sketch_cmd = commands.add_parser("experimental-sketch-populate", help="populate one UI-allocated blank sketch in the temporary native test studio")
    sketch_cmd.add_argument("source", type=Path)
    _add_target(sketch_cmd)
    sketch_cmd.add_argument("--bridge-config", type=Path, required=True)
    sketch_cmd.add_argument("--tab-id", type=int, required=True)
    sketch_cmd.add_argument("--journal", type=Path, required=True)
    begin_cmd = commands.add_parser("experimental-begin-top-sketch", help="start one blank Top sketch using normal editor controls")
    _add_target(begin_cmd)
    begin_cmd.add_argument("--bridge-config", type=Path, required=True)
    begin_cmd.add_argument("--tab-id", type=int, required=True)
    begin_cmd.add_argument("--journal", type=Path, required=True)
    extrude_cmd = commands.add_parser("experimental-extrude-populate", help="set source depth on one UI-bound native extrusion")
    extrude_cmd.add_argument("source", type=Path)
    _add_target(extrude_cmd)
    extrude_cmd.add_argument("--bridge-config", type=Path, required=True)
    extrude_cmd.add_argument("--tab-id", type=int, required=True)
    extrude_cmd.add_argument("--journal", type=Path, required=True)
    extrude_cmd.add_argument("--sketch-op-id", required=True)
    begin_extrude_cmd = commands.add_parser("experimental-begin-source-extrude",
                                           help="select the sole saved source sketch and start its native Extrude")
    begin_extrude_cmd.add_argument("source", type=Path)
    _add_target(begin_extrude_cmd)
    begin_extrude_cmd.add_argument("--bridge-config", type=Path, required=True)
    begin_extrude_cmd.add_argument("--tab-id", type=int, required=True)
    begin_extrude_cmd.add_argument("--journal", type=Path, required=True)
    begin_extrude_cmd.add_argument("--sketch-op-id", required=True)
    plate_cmd = commands.add_parser("experimental-create-plate",
                                    help="validate source locally, then create its native Sketch and Extrude in an empty test studio")
    plate_cmd.add_argument("source", type=Path)
    _add_target(plate_cmd)
    plate_cmd.add_argument("--bridge-config", type=Path, required=True)
    plate_cmd.add_argument("--tab-id", type=int, required=True)
    plate_cmd.add_argument("--journal", type=Path, required=True)
    recover_cmd = commands.add_parser("experimental-reconcile-known-sketch-rejection",
                                      help="resolve the one proven pre-dispatch sketch constructor rejection")
    recover_cmd.add_argument("op_id")
    recover_cmd.add_argument("--bridge-config", type=Path, required=True)
    recover_cmd.add_argument("--tab-id", type=int, required=True)
    recover_cmd.add_argument("--journal", type=Path, required=True)
    recover_begin_cmd = commands.add_parser("experimental-reconcile-completed-top-begin",
                                            help="verify a manually completed Top selection for one unknown begin intent")
    recover_begin_cmd.add_argument("op_id")
    recover_begin_cmd.add_argument("--bridge-config", type=Path, required=True)
    recover_begin_cmd.add_argument("--tab-id", type=int, required=True)
    recover_begin_cmd.add_argument("--journal", type=Path, required=True)
    recover_source_cmd = commands.add_parser("experimental-reconcile-completed-source-sketch",
                                             help="verify one saved source sketch after normal UI completion")
    recover_source_cmd.add_argument("op_id")
    recover_source_cmd.add_argument("--bridge-config", type=Path, required=True)
    recover_source_cmd.add_argument("--tab-id", type=int, required=True)
    recover_source_cmd.add_argument("--journal", type=Path, required=True)
    recover_extrude_cmd = commands.add_parser("experimental-reconcile-saved-source-extrude",
                                              help="verify one eventually saved source extrusion without replay")
    recover_extrude_cmd.add_argument("op_id")
    recover_extrude_cmd.add_argument("--bridge-config", type=Path, required=True)
    recover_extrude_cmd.add_argument("--tab-id", type=int, required=True)
    recover_extrude_cmd.add_argument("--journal", type=Path, required=True)
    classify_cmd = commands.add_parser("experimental-classify-known-invalid-sketch",
                                       help="read-only classify the one applied-invalid temporary sketch")
    classify_cmd.add_argument("op_id")
    classify_cmd.add_argument("--bridge-config", type=Path, required=True)
    classify_cmd.add_argument("--tab-id", type=int, required=True)
    classify_cmd.add_argument("--journal", type=Path, required=True)
    finalize_cmd = commands.add_parser("experimental-finalize-known-invalid-sketch-cancel",
                                       help="verify normal UI cancellation of the one applied-invalid sketch")
    finalize_cmd.add_argument("op_id")
    finalize_cmd.add_argument("--bridge-config", type=Path, required=True)
    finalize_cmd.add_argument("--tab-id", type=int, required=True)
    finalize_cmd.add_argument("--journal", type=Path, required=True)
    reload_cmd = commands.add_parser("extension-reload", help="request one paired Native extension reload after journal preflight")
    reload_cmd.add_argument("--bridge-config", type=Path, required=True)
    reload_cmd.add_argument("--journal", type=Path, required=True)
    return parser


async def _bridge_action(args: argparse.Namespace) -> tuple[object, int]:
    if args.command in {"extension-reload", "experimental-depth-edit", "experimental-begin-top-sketch",
                        "experimental-sketch-populate",
                        "experimental-extrude-populate", "experimental-begin-source-extrude",
                        "experimental-create-plate",
                        "experimental-classify-known-invalid-sketch",
                        "experimental-finalize-known-invalid-sketch-cancel",
                        "experimental-reconcile-completed-top-begin",
                        "experimental-reconcile-completed-source-sketch",
                        "experimental-reconcile-saved-source-extrude",
                        "experimental-reconcile-known-sketch-rejection"}:
        config = json.loads(args.bridge_config.read_text(encoding="utf-8"))
        pinned = config.get("h2cad_journal")
        if (not isinstance(pinned, str) or
                Path(pinned).resolve() != args.journal.resolve()):
            raise ValueError("Bridge must pin the same H2 journal used by this command")
        if args.command == "extension-reload":
            if not args.journal.is_file():
                raise ValueError("Configured H2 journal is missing")
            journal = Journal(args.journal)
            try:
                if journal.has_unresolved():
                    return {"status": "blocked", "phase": "journal",
                            "reason": "Unresolved CAD write intent remains in the H2 journal"}, 2
            finally:
                journal.close()
    bridge = NativeBridge.from_config(args.bridge_config)
    try:
        if args.command == "extension-reload":
            result = await bridge.reload_extension()
            return result, 0 if result.get("status") == "reconnected" else 2
        if args.command == "experimental-reconcile-known-sketch-rejection":
            return await bridge.reconcile_known_sketch_rejection(args.op_id, args.tab_id), 0
        if args.command == "experimental-reconcile-completed-top-begin":
            result = await bridge.reconcile_completed_top_begin(args.op_id, args.tab_id)
            return result, 2 if result.get("status") == "observed_partial_top_begin" else 0
        if args.command == "experimental-reconcile-completed-source-sketch":
            return await bridge.reconcile_completed_source_sketch(args.op_id, args.tab_id), 0
        if args.command == "experimental-reconcile-saved-source-extrude":
            return await bridge.reconcile_saved_source_extrude(args.op_id, args.tab_id), 0
        if args.command == "experimental-finalize-known-invalid-sketch-cancel":
            return await bridge.finalize_known_invalid_sketch_cancel(args.op_id, args.tab_id), 0
        if args.command == "doctor":
            health = await bridge.health()
            return {"bridge_protocol": health.get("protocol"), "extension_connected": health.get("extension_connected"),
                    "extension": health.get("extension")}, 0
        backend = NativeBackend(bridge, tab_id=args.tab_id)
        if args.command == "inspect":
            return await backend.raw_state(_target(args)), 0
        if args.command == "native-probe":
            return await backend.modeling_probe(_target(args)), 0
        if args.command == "native-create-probe":
            return await backend.creation_probe(_target(args)), 0
        if args.command == "experimental-depth-edit":
            journal = Journal(args.journal)
            try:
                return await backend.edit_disposable_extrude_depth(
                    _target(args), feature_id=args.feature_id,
                    from_mm=args.from_mm, to_mm=args.to_mm, journal=journal), 0
            finally:
                journal.close()
        if args.command == "experimental-sketch-populate":
            journal = Journal(args.journal)
            try:
                return await backend.populate_test_sketch(_target(args), args.source, journal), 0
            finally:
                journal.close()
        if args.command == "experimental-begin-top-sketch":
            journal = Journal(args.journal)
            try:
                return await backend.begin_test_top_sketch(_target(args), journal), 0
            finally:
                journal.close()
        if args.command == "experimental-classify-known-invalid-sketch":
            journal = Journal(args.journal)
            try:
                return await backend.classify_known_invalid_sketch(args.op_id, journal), 0
            finally:
                journal.close()
        if args.command == "experimental-extrude-populate":
            journal = Journal(args.journal)
            try:
                return await backend.populate_test_extrude(_target(args), args.source,
                                                           sketch_op_id=args.sketch_op_id, journal=journal), 0
            finally:
                journal.close()
        if args.command == "experimental-begin-source-extrude":
            journal = Journal(args.journal)
            try:
                return await backend.begin_test_source_extrude(_target(args), args.source,
                                                               sketch_op_id=args.sketch_op_id, journal=journal), 0
            finally:
                journal.close()
        if args.command == "experimental-create-plate":
            from .fsgen import compile_fsgen
            from .native import stage_minimal_pair
            from .validation import validate_fsgen
            source_text = args.source.read_text(encoding="utf-8")
            target = _target(args)
            local = validate_fsgen(source_text)
            if local.status != "passed":
                raise ValueError(f"Local FSGen validation must pass before native creation: {local.error or local.status}")
            blueprint = stage_minimal_pair(compile_fsgen(source_text, target))
            if blueprint.depth_mm == 25:
                raise ValueError("Source depth equals the observed editor default; commit-only extrusion is not yet supported")
            journal = Journal(args.journal)
            try:
                begin = await backend.begin_test_top_sketch(target, journal)
                sketch = await backend.populate_test_sketch(target, source_text, journal)
                extrusion = await backend.begin_test_source_extrude(
                    target, source_text, sketch_op_id=sketch["op_id"], journal=journal)
                saved = await backend.populate_test_extrude(
                    target, source_text, sketch_op_id=sketch["op_id"], journal=journal)
                return {"status": "native_definitions_observed", "target": target.to_dict(),
                        "local_validation": local.to_dict(), "begin_sketch": begin,
                        "sketch": sketch, "begin_extrude": extrusion, "extrude": saved,
                        "solid_geometry_verified": False, "ui_editability_verified": False}, 0
            finally:
                journal.close()
        from .executor import Executor
        journal = Journal(args.journal)
        try:
            row = journal.get(args.op_id)
            if row and row["action"] == "experimental_sketch_populate":
                outcome = await backend.reconcile_test_sketch(args.op_id, journal)
                return outcome, 0 if outcome["status"] == "verified" else 2
            if row and row["action"] == "experimental_begin_top_sketch":
                if row["state"] == "observed":
                    return {"op_id": args.op_id, "status": "verified",
                            "evidence": json.loads(row["observation"] or "{}")}, 0
                return {"op_id": args.op_id, "status": "unknown",
                        "reason": "Top-sketch initiation needs exact read-only editor review; no action was replayed"}, 2
            if row and row["action"] == "experimental_extrude_populate":
                outcome = await backend.reconcile_test_extrude(args.op_id, journal)
                return outcome, 0 if outcome["status"] == "verified" else 2
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
        elif args.command == "native-blueprint":
            from .fsgen import compile_fsgen
            from .native import stage_minimal_pair
            value = stage_minimal_pair(compile_fsgen(Path(args.source), _target(args))).to_dict()
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
