"""History-order guard against semantically equivalent but unsafe tree changes."""

import pytest

from h2cad.backend import Capabilities, Receipt
from h2cad.executor import Executor
from h2cad.journal import Journal
from h2cad.model import Feature, Operation, Plan, Snapshot, Target


T = Target("a" * 24, "b" * 24, "c" * 24)
OLD = Feature("old", "sketch", {}, native_id="old-native", regeneration="OK")
H1 = Feature("human1", "sketch", {}, native_id="human-1", ownership="human", regeneration="OK")
H2 = Feature("human2", "sketch", {}, native_id="human-2", ownership="human", regeneration="OK")
NEW = Feature("new", "extrude", {"depth": "5 mm"}, dependencies=("old",))


class ReorderingBackend:
    def __init__(self):
        self.state = Snapshot(T, "r1", [OLD, H1, H2])
        self.submissions = 0

    async def capabilities(self):
        return Capabilities("fake", frozenset({"extrude"}), True)

    async def read(self, target):
        return self.state

    async def apply(self, operation, target, revision):
        self.submissions += 1
        observed_new = Feature("new", "extrude", {"depth": "5 mm"},
                               dependencies=("old",), native_id="new-native", regeneration="OK")
        self.state = Snapshot(T, "r2", [OLD, H2, H1, observed_new])
        return Receipt("new-native", "r2")


@pytest.mark.asyncio
async def test_reordered_human_features_fail_readback(tmp_path):
    backend = ReorderingBackend()
    journal = Journal(tmp_path / "journal.db")
    plan = Plan(T, "r1", [Operation("order-readback", "create", "new", None, NEW)], [],
                Snapshot(T, "r1", [OLD, H1, H2, NEW]))
    result = await Executor(backend, journal).execute(plan)
    assert result.status != "verified"
    assert journal.get("order-readback")["state"] == "unknown"
    journal.close()


@pytest.mark.asyncio
async def test_reordered_merged_plan_rejected_before_submission(tmp_path):
    backend = ReorderingBackend()
    journal = Journal(tmp_path / "journal.db")
    plan = Plan(T, "r1", [Operation("order-plan", "create", "new", None, NEW)], [],
                Snapshot(T, "r1", [OLD, H2, H1, NEW]))
    result = await Executor(backend, journal).execute(plan)
    assert result.status == "invalid_plan"
    assert backend.submissions == 0
    journal.close()
