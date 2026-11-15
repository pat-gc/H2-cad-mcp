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


def _resume_plate_sketch(journal: Journal, op_id: str, target: Target, blueprint,
                         entity_prefix: str) -> dict:
    """Select a proven source sketch; never reconcile or replay an uncertain write."""
    if journal.has_unresolved():
        raise ValueError("Unresolved CAD write remains; reconcile before resuming the plate")
    row = journal.get(op_id)
    key = f"{target.did}/{target.wid}/{target.eid}"
    if (not row or row["target"] != key or row["state"] != "observed"
            or row["action"] != "experimental_sketch_populate"
            or row["logical_id"] != blueprint.sketch_logical_id):
        raise ValueError("Plate resume requires an observed source sketch operation for this target")
    intent = json.loads(row["intent"])
    evidence = json.loads(row["observation"] or "{}")
    if (intent.get("blueprint") != blueprint.to_dict()
            or intent.get("entity_prefix") != entity_prefix):
        raise ValueError("Resume source differs from the journaled plate blueprint")
    feature_id = intent.get("feature_id")
    if (not isinstance(feature_id, str) or not feature_id
            or evidence.get("feature_id") != feature_id
            or evidence.get("origin_verified") is not True
            or evidence.get("constraint_graph_verified") is not True):
        raise ValueError("Resume sketch identity, origin and solver proof must match the journal")
    return {"op_id": op_id, "resumed": True, "evidence": evidence}


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
    preview_cmd = commands.add_parser("preview", help="render actual local solids and save a provenance report; no Onshape writes")
    preview_cmd.add_argument("source", type=Path)
    preview_cmd.add_argument("--output", type=Path, required=True)
    source_run_cmd = commands.add_parser("experimental-source-run", help="checkpoint source-order execution; Browser still allocates drafts")
    source_run_cmd.add_argument("action", choices=("init", "next", "apply", "record-measurements", "measure-native", "inspect-scope", "inspect-draft-scope"))
    source_run_cmd.add_argument("--baseline", type=Path, help="Saved pre-allocation state JSON; required for inspect-draft-scope")
    source_run_cmd.add_argument("--logical-id", help="Observed source NEW body to inspect; required for inspect-scope")
    source_run_cmd.add_argument("--output", type=Path, help="Save full evidence; inspect-scope prints a compact summary")
    source_run_cmd.add_argument("--measurements", type=Path, help="Browser mass-property evidence JSON for record-measurements")
    source_run_cmd.add_argument("source", type=Path)
    source_run_cmd.add_argument("--run-state", type=Path, required=True)
    _add_target(source_run_cmd)
    source_run_cmd.add_argument("--bridge-config", type=Path, required=True)
    source_run_cmd.add_argument("--tab-id", type=int, required=True)
    source_run_cmd.add_argument("--journal", type=Path, required=True)
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
    geometry_cmd = commands.add_parser("inspect-geometry", help="read native solid inventory, volume and area through the session bridge")
    _add_target(geometry_cmd)
    geometry_cmd.add_argument("--bridge-config", type=Path, required=True)
    geometry_cmd.add_argument("--tab-id", type=int, required=True)
    geometry_cmd.add_argument("--output", type=Path)
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
    source_sketch_cmd = commands.add_parser("experimental-populate-source-sketch", help="populate a blank source-plane sketch with solver-verified source geometry")
    source_sketch_cmd.add_argument("source", type=Path)
    _add_target(source_sketch_cmd)
    source_sketch_cmd.add_argument("--bridge-config", type=Path, required=True)
    source_sketch_cmd.add_argument("--tab-id", type=int, required=True)
    source_sketch_cmd.add_argument("--journal", type=Path, required=True)
    source_sketch_cmd.add_argument("--logical-id", required=True)
    source_sketch_cmd.add_argument("--baseline", type=Path, required=True)
    source_sketch_cmd.add_argument("--plane-op-id", required=True)
    source_sketch_cmd.add_argument("--variable-operations", type=Path, required=True)
    source_sketch_reconcile = commands.add_parser("experimental-reconcile-saved-source-sketch")
    source_sketch_reconcile.add_argument("op_id")
    source_sketch_reconcile.add_argument("--bridge-config", type=Path, required=True)
    source_sketch_reconcile.add_argument("--tab-id", type=int, required=True)
    source_sketch_reconcile.add_argument("--journal", type=Path, required=True)
    source_extrusion = commands.add_parser("experimental-populate-source-extrusion", help="populate a UI-bound source extrusion from its observed sketch")
    source_extrusion.add_argument("source", type=Path)
    _add_target(source_extrusion)
    source_extrusion.add_argument("--bridge-config", type=Path, required=True)
    source_extrusion.add_argument("--tab-id", type=int, required=True)
    source_extrusion.add_argument("--journal", type=Path, required=True)
    source_extrusion.add_argument("--logical-id", required=True)
    source_extrusion.add_argument("--sketch-op-id", required=True)
    source_extrusion.add_argument("--baseline", type=Path, required=True)
    source_extrusion.add_argument("--variable-op-id")
    source_extrusion.add_argument("--target-body-op-id", help="observed single-body NEW operation required for scoped REMOVE")
    plane_cmd = commands.add_parser("experimental-populate-plane", help="populate a UI-allocated reference-bound OFFSET plane")
    plane_cmd.add_argument("source", type=Path)
    _add_target(plane_cmd)
    plane_cmd.add_argument("--bridge-config", type=Path, required=True)
    plane_cmd.add_argument("--tab-id", type=int, required=True)
    plane_cmd.add_argument("--journal", type=Path, required=True)
    plane_cmd.add_argument("--logical-id", required=True)
    plane_cmd.add_argument("--previous-plane-op-id", action="append", default=[])
    plane_cmd.add_argument("--baseline", type=Path, required=True)
    plane_cmd.add_argument("--reference-binding", type=Path, required=True)
    plane_cmd.add_argument("--variable-operations", type=Path, required=True, help="JSON source variable name to observed journal operation map")
    plane_reconcile = commands.add_parser("experimental-reconcile-saved-source-plane")
    plane_reconcile.add_argument("op_id")
    plane_reconcile.add_argument("--bridge-config", type=Path, required=True)
    plane_reconcile.add_argument("--tab-id", type=int, required=True)
    plane_reconcile.add_argument("--journal", type=Path, required=True)
    variable_cmd = commands.add_parser("experimental-populate-variable", help="populate one blank UI-allocated LENGTH variable from source")
    variable_cmd.add_argument("source", type=Path)
    _add_target(variable_cmd)
    variable_cmd.add_argument("--bridge-config", type=Path, required=True)
    variable_cmd.add_argument("--tab-id", type=int, required=True)
    variable_cmd.add_argument("--journal", type=Path, required=True)
    variable_cmd.add_argument("--logical-id", required=True)
    variable_cmd.add_argument("--previous-variable-op-id", action="append", default=[])
    variable_reconcile = commands.add_parser("experimental-reconcile-saved-source-variable")
    variable_reconcile.add_argument("op_id")
    variable_reconcile.add_argument("--bridge-config", type=Path, required=True)
    variable_reconcile.add_argument("--tab-id", type=int, required=True)
    variable_reconcile.add_argument("--journal", type=Path, required=True)
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
    plate_cmd.add_argument("--resume-sketch-op-id",
                           help="continue after this reconciled source sketch; requires no extrusion yet")
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
    if args.command in {"extension-reload", "experimental-source-run", "experimental-depth-edit", "experimental-begin-top-sketch",
                        "experimental-sketch-populate",
                        "experimental-extrude-populate", "experimental-begin-source-extrude",
                        "experimental-populate-variable", "experimental-reconcile-saved-source-variable",
                        "experimental-populate-plane", "experimental-reconcile-saved-source-plane",
                        "experimental-populate-source-extrusion",
                        "experimental-populate-source-sketch", "experimental-reconcile-saved-source-sketch",
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
        if args.command == "experimental-reconcile-saved-source-plane":
            return await bridge.reconcile_saved_source_plane(args.op_id, args.tab_id), 0
        if args.command == "experimental-reconcile-saved-source-sketch":
            return await bridge.reconcile_saved_source_sketch(args.op_id, args.tab_id), 0
        if args.command == "experimental-reconcile-saved-source-variable":
            return await bridge.reconcile_saved_source_variable(args.op_id, args.tab_id), 0
        if args.command == "experimental-reconcile-saved-source-extrude":
            return await bridge.reconcile_saved_source_extrude(args.op_id, args.tab_id), 0
        if args.command == "experimental-finalize-known-invalid-sketch-cancel":
            return await bridge.finalize_known_invalid_sketch_cancel(args.op_id, args.tab_id), 0
        if args.command == "doctor":
            health = await bridge.health()
            return {"bridge_protocol": health.get("protocol"), "extension_connected": health.get("extension_connected"),
                    "extension": health.get("extension"),
                    "running_creation_target": health.get("h2cad_create_target")}, 0
        backend = NativeBackend(bridge, tab_id=args.tab_id)
        if args.command == "experimental-source-run":
            from .source_run import initialize_run, next_action, apply_staged, record_measurements, measure_native
            target = _target(args)
            if backend.create_target != target.to_dict():
                raise ValueError("Source run must use the bridge's configured creation target")
            health = await bridge.health()
            if health.get("h2cad_create_target") != target.to_dict():
                raise ValueError("Running bridge creation target differs or is unavailable; reload the configured companion before staging")
            journal = Journal(args.journal)
            try:
                if args.action == "init":
                    return initialize_run(args.run_state, args.source, target, journal), 0
                if args.action == "record-measurements":
                    if args.measurements is None:
                        raise ValueError("record-measurements requires --measurements")
                    return await record_measurements(args.run_state, backend, args.source, target, journal, args.measurements), 0
                if args.action == "measure-native":
                    return await measure_native(args.run_state, backend, args.source, target, journal), 0
                if args.action == "inspect-scope":
                    if not args.logical_id:
                        raise ValueError("inspect-scope requires --logical-id")
                    from .native_body_scope import inspect_current_body_scope
                    return await inspect_current_body_scope(args.run_state, backend, args.source, target, journal, args.logical_id), 0
                if args.action == "inspect-draft-scope":
                    if not args.logical_id or args.baseline is None:
                        raise ValueError("inspect-draft-scope requires --logical-id and --baseline")
                    from .native_draft_scope import inspect_draft_body_scope
                    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
                    return await inspect_draft_body_scope(args.run_state, backend, args.source, target, journal,
                        args.logical_id, baseline, require_selected_scope=True), 0
                action = next_action if args.action == "next" else apply_staged
                return await action(args.run_state, backend, args.source, target, journal), 0
            finally:
                journal.close()
        if args.command == "inspect":
            return await backend.raw_state(_target(args)), 0
        if args.command == "inspect-geometry":
            from .native_geometry import collect_native_geometry
            return await collect_native_geometry(backend, _target(args)), 0
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
        if args.command == "experimental-populate-source-sketch":
            from .native_sketches import populate_source_sketch
            journal = Journal(args.journal)
            try:
                return await populate_source_sketch(backend, _target(args), args.source, logical_id=args.logical_id,
                    baseline=json.loads(args.baseline.read_text(encoding="utf-8")), plane_op_id=args.plane_op_id,
                    variable_op_ids=json.loads(args.variable_operations.read_text(encoding="utf-8")), journal=journal), 0
            finally:
                journal.close()
        if args.command == "experimental-populate-source-extrusion":
            from .native_source_extrusions import populate_source_extrusion
            journal = Journal(args.journal)
            try:
                return await populate_source_extrusion(backend, _target(args), args.source,
                    logical_id=args.logical_id, sketch_op_id=args.sketch_op_id,
                    baseline=json.loads(args.baseline.read_text(encoding="utf-8")),
                    variable_op_id=args.variable_op_id, target_body_op_id=args.target_body_op_id, journal=journal), 0
            finally:
                journal.close()
        if args.command == "experimental-populate-plane":
            from .native_planes import populate_test_plane
            journal = Journal(args.journal)
            try:
                return await populate_test_plane(backend, _target(args), args.source,
                    logical_id=args.logical_id, previous_op_ids=args.previous_plane_op_id,
                    baseline=json.loads(args.baseline.read_text(encoding="utf-8")),
                    reference_binding=json.loads(args.reference_binding.read_text(encoding="utf-8")),
                    variable_op_ids=json.loads(args.variable_operations.read_text(encoding="utf-8")),
                    journal=journal), 0
            finally:
                journal.close()
        if args.command == "experimental-populate-variable":
            journal = Journal(args.journal)
            try:
                return await backend.populate_test_variable(_target(args), args.source,
                    logical_id=args.logical_id, previous_op_ids=args.previous_variable_op_id, journal=journal), 0
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
            snapshot = compile_fsgen(source_text, target)
            blueprint = stage_minimal_pair(snapshot)
            if blueprint.depth_mm == 25:
                raise ValueError("Source depth equals the observed editor default; commit-only extrusion is not yet supported")
            journal = Journal(args.journal)
            try:
                if args.resume_sketch_op_id:
                    entities = snapshot.features[0].structure["fsgen_native"]["entities"]
                    prefix = entities[0]["entityId"].rsplit(".", 1)[0]
                    sketch = _resume_plate_sketch(journal, args.resume_sketch_op_id, target, blueprint, prefix)
                    begin = None
                else:
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
        if args.command == "experimental-source-run" and args.output:
            protected = [args.source, args.run_state, args.journal, args.bridge_config, args.measurements, args.baseline]
            if any(path is not None and args.output.resolve() == path.resolve() for path in protected):
                raise ValueError("Evidence output must not overwrite source, run state, journal, bridge config or measurement input")
        result_status = 0
        if args.command == "compile":
            from .fsgen import compile_fsgen
            value = compile_fsgen(Path(args.source), _target(args), revision=args.revision).to_dict()
        elif args.command == "native-blueprint":
            from .fsgen import compile_fsgen
            from .native import stage_minimal_pair
            value = stage_minimal_pair(compile_fsgen(Path(args.source), _target(args))).to_dict()
        elif args.command == "preview":
            from .preview import preview_fsgen
            value = preview_fsgen(args.source, args.output)
            _print(value)
            return 0
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
            if args.command == "inspect-geometry":
                _print({k: v for k, v in value.items() if k != "raw_provenance"})
            elif args.command == "experimental-source-run" and args.action in ("inspect-scope", "inspect-draft-scope"):
                _print({k: v for k, v in value.items() if k not in ("geometry", "history_proofs", "raw_provenance", "inventory_proof")})
            else:
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
