"""Join current native body inventory to observed source history, read-only.

This inspection provides exact-set selection requirements, not permission to
perform a cut. Existing writer and coordinator restrictions remain unchanged.
"""
from __future__ import annotations

import copy

from .backend import Unsupported
from .native_body_history import inspect_source_body_histories
from .native_geometry import _stable, collect_native_geometry


async def inspect_current_body_scope(runpath, backend, source, target, journal, logical_id):
    geometry = await collect_native_geometry(backend, target)
    before = geometry["raw_provenance"]["before_state"]
    after = geometry["raw_provenance"]["after_state"]
    _stable(before, after, target)
    histories = inspect_source_body_histories(runpath, source, target, journal, current_state=before)
    originals = list(histories)
    if logical_id not in histories:
        raise Unsupported("Requested scope must be an observed original source NEW body")
    if inspect_source_body_histories(runpath, source, target, journal, current_state=after) != histories:
        raise Unsupported("Source history changed during body scope inspection")
    by_creator = {history["target_feature_id"]: name for name, history in histories.items()}
    if len(by_creator) != len(histories):
        raise Unsupported("Original source creator identities are not unique")
    inventory = geometry["inventory_proof"]
    if (inventory.get("server_enumeration_verified") is not True or inventory.get("target") != target.to_dict()
            or inventory.get("element_microversion") != before["element_microversion"]
            or inventory.get("document_microversion") != before["microversion"]):
        raise Unsupported("Current server body enumeration must match the exact history snapshot")
    ids = [body["body_id"] for body in geometry["bodies"]]
    if len(ids) != len(set(ids)) or sorted(ids) != inventory["body_ids"]:
        raise Unsupported("Geometry reads must cover each server-inventoried body exactly once")
    partitions = {name: [] for name in originals}
    allowed = {}
    for name, history in histories.items():
        allowed[name] = {history["target_feature_id"] + ".opExtrude"}
        allowed[name].update(cut["feature_id"] + ".boolean.opBoolean" for cut in history["observed_removes"])
    for body in geometry["bodies"]:
        creator = body["creator_feature_id"]
        name = by_creator.get(creator)
        if name is None or body["full_operation_id"] not in allowed[name]:
            raise Unsupported("Body operation is not its original NEW or an observed REMOVE of that same source target")
        partitions[name].append(body["body_id"])
    for bodies in partitions.values():
        bodies.sort()
    required = partitions[logical_id]
    if not required:
        raise Unsupported("Requested source body has no current inventoried descendants")
    final = await backend.raw_state(target)
    _stable(before, final, target)
    # Recheck durable provenance after the final live read; do not cache an old
    # observed operation across a concurrent journal or checkpoint change.
    if inspect_source_body_histories(runpath, source, target, journal, current_state=final) != histories:
        raise Unsupported("Source journal history changed before scope inspection completed")
    history = histories[logical_id]
    return {"target": target.to_dict(), "source_sha256": history["source_sha256"],
            "element_microversion": final["element_microversion"], "document_microversion": final["microversion"],
            "snapshot_sha256": history["snapshot_sha256"], "target_logical_id": logical_id,
            "target_op_id": history["target_op_id"], "target_feature_id": history["target_feature_id"],
            "scope_body_ids": list(required), "single_survivor": len(required) == 1,
            "selected_scope_requirement": {"match": "exact_set", "body_ids": list(required), "defaultScope": False},
            "allowed_operation_ids": sorted(allowed[logical_id]), "body_partitions": partitions,
            "observed_removes": copy.deepcopy(history["observed_removes"]),
            "independently_verified": True, "write_ready": False,
            "verification_scope": "current inventory, explicit observed operation lineage and source definitions at one saved snapshot",
            "missing_evidence": ["fresh active-draft scope resolution and native write/reconciliation integration"],
            "history_proofs": histories, "geometry": geometry}
