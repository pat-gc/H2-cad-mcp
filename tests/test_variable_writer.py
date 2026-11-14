"""Source-driven variable writer against a sanitized captured native default."""
import asyncio
import copy
import json
from pathlib import Path

import pytest

from h2cad.backend import Unsupported, UncertainWrite
from h2cad.fsgen import compile_fsgen
from h2cad.journal import Journal
from h2cad.model import Target
from h2cad.native import NativeBackend, _variable_expected_tree, stage_length_variable

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/car/basic_car.fs"
TARGET = Target("4e078dec822b4e509616b1cb", "af0627de07264acf086e646a", "e" * 24)
TD = dict(did=TARGET.did, wid=TARGET.wid, eid=TARGET.eid)


def draft(number=0):
    feature = json.loads((ROOT / "tests/fixtures/native_variable_default.json").read_text())
    feature["featureId"] = f"freshVariable_{number}"
    feature["nodeId"] = f"feature-node-{number}"
    return {"target": TD, "connected": True, "editingFeatureId": feature["featureId"],
            "element_microversion": "a" * 24,
            "tree": {"$type": "bsedit.GBTMModel", "children": [feature,
                     {"$type": "bsedit.GBTMRollback", "nodeId": "rollback"}]}}


def stages():
    return [stage_length_variable(f) for f in compile_fsgen(SOURCE, TARGET).features
            if f.kind == "assignVariable"]


def test_expected_tree_preserves_ids_defaults_and_source_expression():
    before = draft()
    original = copy.deepcopy(before)
    expected = _variable_expected_tree(before, stages()[0])
    assert before == original
    a, b = before["tree"]["children"][0], expected["children"][0]
    changed = [x["parameterId"] for x, y in zip(a["parameters"], b["parameters"]) if x != y]
    assert changed == ["name", "lengthValue", "value"]
    assert a["nodeId"] == b["nodeId"]
    assert all(x["nodeId"] == y["nodeId"] for x, y in zip(a["parameters"], b["parameters"]))
    assert expected["children"][1:] == before["tree"]["children"][1:]


@pytest.mark.parametrize("parameter,value", [("mode", "MEASURED"), ("variableType", "ANY"),
    ("name", "existing"), ("lengthValue", 5), ("conversionFactor", 2), ("rowRegexp", True)])
def test_changed_or_nonblank_drafts_rejected(parameter, value):
    before = draft()
    next(p for p in before["tree"]["children"][0]["parameters"] if p["parameterId"] == parameter)["value"] = value
    with pytest.raises(Unsupported):
        _variable_expected_tree(before, stages()[0])


class Bridge:
    create_target = TD

    def __init__(self, journal):
        self.journal, self.state, self.writes = journal, draft(), []
        self.fail = False

    async def health(self):
        return {"extension_connected": True, "capabilities": ["h2_native_variable_populate_server_v1"],
                "extension": {"capabilities": ["h2_native_variable_populate_page_v1", "h2_native_completion_receipt_page_v1"]}}

    async def command(self, job):
        if job["kind"] == "state":
            return copy.deepcopy(self.state)
        self.writes.append(job)
        if self.fail:
            raise TimeoutError("test timeout")
        return {"op_id": job["op_id"], "definition_candidate": True, "completion_pending": True}

    async def reconcile_saved_source_variable(self, op_id, tab_id):
        row = self.journal.get(op_id)
        intent = json.loads(row["intent"])
        evidence = {"op_id": op_id, "feature_id": self.state["editingFeatureId"], "definition_observed": True,
                    "regeneration_verified": False}
        self.journal.transition(op_id, "observed", observation=evidence)
        self.state["tree"] = intent["expected_tree"]
        self.state["editingFeatureId"] = None
        return {"op_id": op_id, "evidence": evidence}


def test_seven_variables_require_exact_order_and_keep_distinct_identities(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    bridge = Bridge(journal)
    backend = NativeBackend(bridge, tab_id=7)
    previous = []
    try:
        for index, stage in enumerate(stages()):
            if index:
                feature = draft(index)["tree"]["children"][0]
                bridge.state["tree"]["children"].insert(-1, feature)
                bridge.state["editingFeatureId"] = feature["featureId"]
            result = asyncio.run(backend.populate_test_variable(TARGET, SOURCE,
                logical_id=stage["logical_id"], previous_op_ids=previous, journal=journal))
            previous.append(result["op_id"])
        assert len(bridge.writes) == 7
        assert len({job["variable_edit"]["feature_id"] for job in bridge.writes}) == 7
        assert [job["variable_edit"]["expression"] for job in bridge.writes] == [s["expression"] for s in stages()]
        assert not journal.has_unresolved()
    finally:
        journal.close()


def test_skipped_source_or_changed_semantics_and_unknown_write_never_replay(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    bridge = Bridge(journal)
    backend = NativeBackend(bridge, tab_id=7)
    try:
        with pytest.raises(Unsupported, match="order"):
            asyncio.run(backend.populate_test_variable(TARGET, SOURCE, logical_id="#width", previous_op_ids=[], journal=journal))
        bridge.fail = True
        with pytest.raises(UncertainWrite):
            asyncio.run(backend.populate_test_variable(TARGET, SOURCE, logical_id="#length", previous_op_ids=[], journal=journal))
        with pytest.raises(UncertainWrite, match="Prior write"):
            asyncio.run(backend.populate_test_variable(TARGET, SOURCE, logical_id="#length", previous_op_ids=[], journal=journal))
        assert len(bridge.writes) == 1
    finally:
        journal.close()


def test_previous_source_change_or_unrelated_tree_change_is_rejected(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    bridge = Bridge(journal)
    backend = NativeBackend(bridge, tab_id=7)
    try:
        first = asyncio.run(backend.populate_test_variable(TARGET, SOURCE, logical_id="#length", previous_op_ids=[], journal=journal))
        bridge.state["tree"]["children"].insert(-1, draft(1)["tree"]["children"][0])
        bridge.state["editingFeatureId"] = "freshVariable_1"
        changed = SOURCE.read_text().replace('variable(context, "length", 180 * millimeter)', 'variable(context, "length", 181 * millimeter)')
        with pytest.raises(Unsupported, match="source"):
            asyncio.run(backend.populate_test_variable(TARGET, changed, logical_id="#width", previous_op_ids=[first["op_id"]], journal=journal))
        bridge.state["tree"]["children"][-1]["nodeId"] = "changed-rollback"
        with pytest.raises(Unsupported, match="unrelated"):
            asyncio.run(backend.populate_test_variable(TARGET, SOURCE, logical_id="#width", previous_op_ids=[first["op_id"]], journal=journal))
        assert len(bridge.writes) == 1
    finally:
        journal.close()


def test_variable_bridge_classifies_pre_dispatch_without_unknown_retry():
    import httpx
    from h2cad.native import NativeBridge, PreDispatchRejected
    async def run():
        async def handler(request):
            return httpx.Response(200, json={"error": "blank draft required", "write_stage": "pre_dispatch"})
        bridge = NativeBridge("a" * 32, transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(PreDispatchRejected):
                await bridge.command({"kind": "partstudio_populate_variable"})
        finally:
            await bridge.http.aclose()
    asyncio.run(run())
