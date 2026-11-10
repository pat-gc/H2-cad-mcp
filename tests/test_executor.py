from dataclasses import replace

import pytest

from h2cad.backend import Capabilities, Receipt, UncertainWrite
from h2cad.executor import Executor
from h2cad.journal import Journal
from h2cad.model import Feature, Operation, Plan, Snapshot, Target


T = Target("a" * 24, "b" * 24, "c" * 24)
BASE = Feature("old", "sketch", {"width": "20 mm"}, native_id="native-old", ownership="ai", regeneration="OK")
NEW = Feature("new", "extrude", {"depth": "5 mm"}, dependencies=("old",), ownership="ai")


class FakeBackend:
    def __init__(self, *, atomic=True, failure=False, alter_unrelated=False):
        self.atomic = atomic
        self.failure = failure
        self.alter_unrelated = alter_unrelated
        self.submissions = 0
        self.current = Snapshot(T, "1" * 24, (BASE,))

    async def capabilities(self):
        return Capabilities("fake", frozenset({"extrude"}), self.atomic, frozenset({"identity", "parameters", "regeneration"}))

    async def read(self, target):
        return self.current

    async def apply(self, operation, target, expected_revision):
        self.submissions += 1
        if self.failure:
            raise UncertainWrite("reply lost")
        old = replace(BASE, parameters={"width": "21 mm"}) if self.alter_unrelated else BASE
        result = replace(NEW, native_id="native-new", regeneration="OK")
        self.current = Snapshot(T, "2" * 24, (old, result))
        return Receipt("native-new", "2" * 24, {"accepted": True})


def make_plan():
    operation = Operation("op-1", "create", "new", None, NEW)
    return Plan(T, "1" * 24, (operation,), (), Snapshot(T, "1" * 24, (BASE, NEW)))


@pytest.mark.asyncio
async def test_executor_journals_and_verifies_semantics(tmp_path):
    journal = Journal(tmp_path / "journal.db")
    backend = FakeBackend()
    result = await Executor(backend, journal).execute(make_plan())
    assert result.status == "verified"
    assert result.steps[0].evidence["native_id"] == "native-new"
    assert journal.get("op-1")["state"] == "observed"
    assert backend.submissions == 1
    journal.close()


@pytest.mark.asyncio
async def test_preflight_only_rejected_unless_experimental_and_unknown_never_replayed(tmp_path):
    journal = Journal(tmp_path / "journal.db")
    backend = FakeBackend(atomic=False, failure=True)
    executor = Executor(backend, journal)
    assert (await executor.execute(make_plan())).status == "atomic_revision_required"
    assert backend.submissions == 0
    assert (await executor.execute(make_plan(), experimental_isolated=True)).status == "stopped"
    assert journal.get("op-1")["state"] == "unknown"
    assert (await executor.execute(make_plan(), experimental_isolated=True)).status == "unresolved_prior_write"
    assert backend.submissions == 1
    journal.close()


@pytest.mark.asyncio
async def test_unrelated_change_prevents_verified_status(tmp_path):
    journal = Journal(tmp_path / "journal.db")
    result = await Executor(FakeBackend(alter_unrelated=True), journal).execute(make_plan())
    assert result.steps[0].status == "unknown"
    assert "unrelated" in result.steps[0].reason
    assert journal.get("op-1")["state"] == "unknown"
    journal.close()


@pytest.mark.asyncio
async def test_human_feature_update_rejected_before_backend_apply(tmp_path):
    journal = Journal(tmp_path / "journal.db")
    human = replace(BASE, ownership="human")
    after = replace(human, parameters={"width": "22 mm"})
    operation = Operation("bad", "update", "old", human, after)
    plan = Plan(T, "1" * 24, (operation,), (), Snapshot(T, "1" * 24, (after,)))
    backend = FakeBackend()
    assert (await Executor(backend, journal).execute(plan)).status == "invalid_plan"
    assert backend.submissions == 0
    journal.close()


@pytest.mark.asyncio
async def test_update_receipt_cannot_replace_native_identity(tmp_path):
    before = BASE
    after = replace(BASE, parameters={"width": "22 mm"}, regeneration="unknown")
    operation = Operation("update-1", "update", "old", before, after)
    plan = Plan(T, "1" * 24, (operation,), (), Snapshot(T, "1" * 24, (after,)))

    class ChangedId(FakeBackend):
        async def capabilities(self):
            return Capabilities("fake", frozenset({"sketch"}), True)

        async def apply(self, operation, target, expected_revision):
            self.submissions += 1
            self.current = Snapshot(T, "2" * 24, (replace(after, native_id="wrong-id", regeneration="OK"),))
            return Receipt("wrong-id", "2" * 24)

    journal = Journal(tmp_path / "journal.db")
    result = await Executor(ChangedId(), journal).execute(plan)
    assert "changed native feature ID" in result.steps[0].reason
    assert journal.get("update-1")["state"] == "unknown"
    journal.close()


@pytest.mark.asyncio
async def test_dependency_regeneration_failure_is_not_verified(tmp_path):
    class BrokenDependent(FakeBackend):
        async def apply(self, operation, target, expected_revision):
            receipt = await super().apply(operation, target, expected_revision)
            self.current = replace(self.current, features=(replace(BASE, regeneration="ERROR"), self.current.features[1]))
            return receipt

    journal = Journal(tmp_path / "journal.db")
    result = await Executor(BrokenDependent(), journal).execute(make_plan())
    assert "regeneration" in result.steps[0].reason
    journal.close()


@pytest.mark.asyncio
async def test_read_only_reconcile_requires_positive_identity(tmp_path):
    journal = Journal(tmp_path / "journal.db")
    backend = FakeBackend(failure=True)
    executor = Executor(backend, journal)
    await executor.execute(make_plan())
    assert (await executor.reconcile("op-1")).status == "unknown"
    assert backend.submissions == 1
    journal.close()


@pytest.mark.asyncio
async def test_verified_remote_snapshot_survives_restart_with_human_values(tmp_path):
    path = tmp_path / "journal.db"
    journal = Journal(path)
    backend = FakeBackend()
    human = Feature("human", "sketch", {"radius": "8 mm"}, native_id="human-id", ownership="human", regeneration="OK")
    backend.current = Snapshot(T, "1" * 24, (BASE, human))
    no_op = Plan(T, "1" * 24, (), (), backend.current)
    assert (await Executor(backend, journal).execute(no_op)).status == "verified"
    journal.close()
    reopened = Journal(path)
    saved = Snapshot.from_dict(reopened.load_sync_snapshot("/".join((T.did, T.wid, T.eid))))
    assert saved.features[1].native_id == "human-id"
    assert saved.features[1].parameters == {"radius": "8 mm"}
    assert saved.features[1].ownership == "human"
    reopened.close()


@pytest.mark.asyncio
async def test_reordered_human_features_rejected_preflight_and_readback(tmp_path):
    h1 = Feature("h1", "sketch", {}, native_id="h1-id", ownership="human", regeneration="OK")
    h2 = Feature("h2", "sketch", {}, native_id="h2-id", ownership="human", regeneration="OK")
    backend = FakeBackend()
    backend.current = Snapshot(T, "1" * 24, (BASE, h1, h2))
    op = Operation("order-op", "create", "new", None, NEW)
    bad = Plan(T, "1" * 24, (op,), (), Snapshot(T, "1" * 24, (BASE, h2, h1, NEW)))
    journal = Journal(tmp_path / "journal.db")
    assert (await Executor(backend, journal).execute(bad)).status == "invalid_plan"
    assert backend.submissions == 0

    class Reorders(FakeBackend):
        async def apply(self, operation, target, expected_revision):
            self.submissions += 1
            self.current = Snapshot(T, "2" * 24, (BASE, h2, h1, replace(NEW, native_id="native-new", regeneration="OK")))
            return Receipt("native-new", "2" * 24)

    backend2 = Reorders()
    backend2.current = Snapshot(T, "1" * 24, (BASE, h1, h2))
    good = Plan(T, "1" * 24, (op,), (), Snapshot(T, "1" * 24, (BASE, h1, h2, NEW)))
    result = await Executor(backend2, journal).execute(good)
    assert result.steps[0].status == "unknown" and "order" in result.steps[0].reason
    journal.close()
