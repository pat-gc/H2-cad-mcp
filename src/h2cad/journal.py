"""SQLite intent journal. A pending or unknown write is a hard execution stop."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("""CREATE TABLE IF NOT EXISTS writes (
            op_id TEXT PRIMARY KEY, target TEXT NOT NULL, expected_revision TEXT NOT NULL,
            action TEXT NOT NULL, logical_id TEXT NOT NULL, intent TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('prepared','sent','unknown','observed','rejected')),
            receipt TEXT, observation TEXT, error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS sync_snapshots (
            target TEXT PRIMARY KEY, revision TEXT NOT NULL, snapshot TEXT NOT NULL,
            verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

    def close(self) -> None:
        self._db.close()

    def get(self, op_id: str) -> dict[str, Any] | None:
        self._db.row_factory = sqlite3.Row
        row = self._db.execute("SELECT * FROM writes WHERE op_id=?", (op_id,)).fetchone()
        return dict(row) if row else None

    def unresolved(self, target: str) -> list[dict[str, Any]]:
        self._db.row_factory = sqlite3.Row
        rows = self._db.execute("SELECT * FROM writes WHERE target=? AND state IN ('prepared','sent','unknown') ORDER BY created_at", (target,)).fetchall()
        return [dict(row) for row in rows]

    def save_sync_snapshot(self, target: str, snapshot: dict[str, Any]) -> None:
        if not snapshot.get("complete"):
            raise ValueError("Cannot persist incomplete readback as a sync base")
        with self._lock:
            self._db.execute("""INSERT INTO sync_snapshots(target,revision,snapshot) VALUES(?,?,?)
                ON CONFLICT(target) DO UPDATE SET revision=excluded.revision,snapshot=excluded.snapshot,
                verified_at=CURRENT_TIMESTAMP""",
                (target, snapshot["revision"], json.dumps(snapshot, sort_keys=True)))

    def load_sync_snapshot(self, target: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT snapshot FROM sync_snapshots WHERE target=?", (target,)).fetchone()
        return json.loads(row[0]) if row else None

    def prepare(self, *, op_id: str, target: str, expected_revision: str,
                action: str, logical_id: str, intent: dict[str, Any]) -> None:
        with self._lock:
            try:
                self._db.execute("INSERT INTO writes (op_id,target,expected_revision,action,logical_id,intent,state) VALUES (?,?,?,?,?,?,'prepared')",
                                 (op_id, target, expected_revision, action, logical_id, json.dumps(intent, sort_keys=True)))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Operation {op_id} already journaled; inspect it before another submission") from exc

    def transition(self, op_id: str, state: str, *, receipt: dict[str, Any] | None = None,
                   observation: dict[str, Any] | None = None, error: str | None = None) -> None:
        allowed = {"prepared": {"sent", "unknown", "rejected"}, "sent": {"observed", "unknown"},
                   "unknown": {"observed", "rejected"}, "observed": set(), "rejected": set()}
        with self._lock:
            current = self.get(op_id)
            if current is None or state not in allowed[current["state"]]:
                raise ValueError(f"Illegal journal transition for {op_id}: {current and current['state']} -> {state}")
            self._db.execute("UPDATE writes SET state=?, receipt=COALESCE(?,receipt), observation=COALESCE(?,observation), error=?, updated_at=CURRENT_TIMESTAMP WHERE op_id=?",
                             (state, json.dumps(receipt, sort_keys=True) if receipt is not None else None,
                              json.dumps(observation, sort_keys=True) if observation is not None else None, error, op_id))
