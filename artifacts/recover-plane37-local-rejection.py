"""One-off reviewed recovery for the patch37 Python allowlist rejection.

No modeling commands, replay, marker retirement, or guard edits. Default is proof
only; tester may pass --apply after root review. Do not reuse for other failures.
"""
import argparse
import asyncio
import json
from pathlib import Path

from h2cad.journal import Journal
from h2cad.native import NativeBridge

OP = "plane-1ba6263fe9ab4acd9abd4f5159da9f9e"
ERROR = "Browser-mode adapter permits only native editor jobs"
TARGET = {"did": "4e078dec822b4e509616b1cb", "wid": "af0627de07264acf086e646a", "eid": "9b8155a2839e649138dae95f"}
REVISION = "7b1da25eab3c59d17fd3cee1"
FEATURE = "FrioRuovl3ZRMGz_0"


def prove(row, samples):
    key = "/".join(TARGET.values())
    if (not row or row["op_id"] != OP or row["state"] != "unknown"
            or row["action"] != "experimental_plane_populate" or row["target"] != key
            or row["logical_id"] != "Chassis height" or row["expected_revision"] != REVISION
            or row["error"] != ERROR or row["receipt"] is not None or row["observation"] is not None):
        raise ValueError("Exact historical local rejection row required")
    before = json.loads(row["intent"])["before_state"]
    if (before.get("target") != TARGET or before.get("element_microversion") != REVISION
            or before.get("editingFeatureId") != FEATURE or before.get("connected") is not True):
        raise ValueError("Historical plane draft binding differs")
    if len(samples) != 2:
        raise ValueError("Two independent current readbacks required")
    for sample in samples:
        state, editor, health, guard = (sample[k] for k in ("state", "editor", "health", "guard"))
        if any(state.get(k) != before.get(k) for k in ("target", "connected", "element_microversion", "editingFeatureId", "tree")):
            raise ValueError("Draft revision or whole tree changed; do not recover")
        if (health.get("extension_connected") is not True or health.get("pending") != 0
                or guard.get("schema") != 1 or guard.get("unknown_write") is not False
                or guard.get("reload") is not None and guard["reload"].get("status") != "reconnected"):
            raise ValueError("Bridge or durable guard state differs")
        reasons = editor.get("busy_reasons", {})
        if (editor.get("ready") is not True or editor.get("element_microversion") != REVISION
                or "incomplete_feature_marker" not in editor or editor["incomplete_feature_marker"] is not None
                or reasons.get("feature_edit") is not True
                or any(reasons.get(k) is not False for k in ("pending_rpc", "motion", "incomplete_feature_edit", "incomplete_transform", "drag"))):
            raise ValueError("Expected active draft without pending marker required")
    return {"classification": "rejected_before_http", "operation": OP,
            "diagnosis": "Patch37 NativeBridge.command local kind allowlist omitted plane before self.http.post",
            "source_commit": "ce1f7fcf0fdaf5fb63c597c8683701df5496abbd",
            "original_error": ERROR, "target": TARGET, "revision": REVISION, "feature_id": FEATURE,
            "whole_before_tree_unchanged": True, "independent_readbacks": 2,
            "controller_marker_absent": True, "bridge_pending": 0, "unknown_write_guard": False,
            "modeling_dispatched": False, "definition_observed": False}


async def main(args):
    config = json.loads(args.bridge_config.read_text(encoding="utf-8"))
    journal_path = Path(config["h2cad_journal"])
    if not journal_path.is_absolute() or config.get("h2cad_create_target") != TARGET:
        raise ValueError("Exact configured target and absolute pinned journal required")
    guard_path = journal_path.with_name(journal_path.name + ".extension-reload-guard.json")
    bridge = NativeBridge.from_config(args.bridge_config)
    journal = Journal(journal_path)
    try:
        with journal.target_lock("/".join(TARGET.values())):
            row = journal.get(OP)
            if [r["op_id"] for r in journal.unresolved("/".join(TARGET.values()))] != [OP]:
                raise ValueError("Exactly one historical unresolved plane operation required")
            samples = []
            for _ in range(2):
                state = await bridge.command({"kind": "state", "target": TARGET, "tab_id": args.tab_id})
                response = await bridge.http.post("/command", json={"kind": "editor_tab", "action": "status",
                    "target": TARGET, "tab_id": args.tab_id, "wait_seconds": 0})
                response.raise_for_status()
                samples.append({"state": state, "editor": response.json(), "health": await bridge.health(),
                                "guard": json.loads(guard_path.read_text(encoding="utf-8"))})
            proof = prove(row, samples)
            if journal.get(OP) != row:
                raise ValueError("Journal row changed during readback")
            if args.apply:
                journal.transition(OP, "rejected", observation=proof, error=ERROR)
            print(json.dumps({"status": "rejected" if args.apply else "proof_only", "proof": proof}, indent=2))
    finally:
        journal.close()
        await bridge.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-config", type=Path, required=True)
    parser.add_argument("--tab-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args()))
