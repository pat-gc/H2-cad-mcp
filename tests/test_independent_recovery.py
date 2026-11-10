"""Independent process and interruption checks against the durable executor."""

import asyncio
import subprocess
import sys

import pytest

from h2cad.backend import Capabilities, Receipt
from h2cad.executor import Executor
from h2cad.journal import Journal
from h2cad.model import Feature, Operation, Plan, Snapshot, Target


TARGET = Target("a" * 24, "b" * 24, "c" * 24)
FEATURE = Feature("part", "extrude", {"depth": "5 mm"})
PLAN = Plan(TARGET, "1" * 24, (Operation("independent-op", "create", "part", None, FEATURE),),
            (), Snapshot(TARGET, "1" * 24, (FEATURE,)))
KEY = "/".join((TARGET.did, TARGET.wid, TARGET.eid))


def test_target_lock_excludes_another_process_and_releases(tmp_path):
    db = tmp_path / "journal.db"
    code = ("import sys\nfrom h2cad.journal import Journal\n"
            "j=Journal(sys.argv[1])\n"
            "with j.target_lock(sys.argv[2]):\n"
            " print('LOCKED', flush=True)\n sys.stdin.readline()\n")
    proc = subprocess.Popen([sys.executable, "-c", code, str(db), KEY],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    try:
        assert proc.stdout.readline().strip() == "LOCKED", proc.stderr.read()
        other = Journal(db)
        try:
            with pytest.raises(RuntimeError, match="Another process"):
                with other.target_lock(KEY):
                    pass
        finally:
            other.close()
    finally:
        proc.stdin.write("\n")
        proc.stdin.flush()
        assert proc.wait(timeout=5) == 0
    after = Journal(db)
    try:
        with after.target_lock(KEY):
            pass
    finally:
        after.close()


@pytest.mark.asyncio
async def test_cancel_during_remote_handoff_stays_unresolved_after_restart(tmp_path):
    entered = asyncio.Event()

    class HangingBackend:
        calls = 0

        async def capabilities(self):
            return Capabilities("fake", frozenset({"extrude"}), True)

        async def read(self, target):
            return Snapshot(TARGET, "1" * 24, ())

        async def apply(self, operation, target, revision):
            self.calls += 1
            entered.set()
            await asyncio.Future()
            return Receipt("id", "2" * 24)

    backend = HangingBackend()
    db = tmp_path / "journal.db"
    journal = Journal(db)
    task = asyncio.create_task(Executor(backend, journal).execute(PLAN))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert journal.get("independent-op")["state"] in {"prepared", "unknown"}
    journal.close()
    reopened = Journal(db)
    try:
        result = await Executor(backend, reopened).execute(PLAN)
        assert result.status == "unresolved_prior_write"
        assert backend.calls == 1
    finally:
        reopened.close()
