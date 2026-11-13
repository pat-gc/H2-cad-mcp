"""Offline contract tests for the isolated source-driven sketch write."""

import copy
from pathlib import Path

import pytest

from h2cad.backend import UncertainWrite, Unsupported
from h2cad.journal import Journal
from h2cad.model import Target
from h2cad.native import NativeBackend
from h2cad.cli import build_parser


TARGET = Target("4e078dec822b4e509616b1cb", "af0627de07264acf086e646a", "9a062f0eef8bb961f8c84f8e")
SOURCE = Path(__file__).resolve().parents[1] / "fixtures" / "native" / "minimal_plate.fs"


def state(*, populated=False, unrelated_changed=False):
    plane = {"$type": "bsedit.GBTMParameterQueryList", "parameterId": "sketchPlane",
             "queries": [{"$type": "bsedit.GBTMIndividualQuery", "deterministicIds": ["bound-top"]}]}
    sketch = {"featureId": "editorAllocated_0", "featureType": "newSketch", "nodeId": "fresh-node",
              "parameters": [plane], "entities": [], "constraints": []}
    if populated:
        spec = [("bottom", .02, 0, 1, 0, -.02, .02),
                ("right", .04, .01, 0, 1, -.01, .01),
                ("top", .02, .02, 1, 0, -.02, .02),
                ("left", 0, .01, 0, 1, -.01, .01)]
        sketch["entities"] = [{"$type": "bsedit.GBTMSketchCurveSegment", "entityId": "box." + side,
                               "isConstruction": False, "startParam": start, "endParam": end,
                               "geometry": {"$type": "bsedit.GBTCurveGeometryLine", "pntX": px,
                                            "pntY": py, "dirX": dx, "dirY": dy}}
                              for side, px, py, dx, dy, start, end in spec]
        def p(ident, value, type_name="String", **extra):
            return {"$type": "bsedit.GBTMParameter" + type_name, "parameterId": ident, "value": value, **extra}
        def c(ident, kind, first, second=None):
            params = [p("localFirst", "box." + first)]
            if second is not None:
                params.append(p("localSecond", "box." + second))
            return {"$type": "bsedit.GBTMSketchConstraint", "entityId": "box." + ident,
                    "constraintType": kind, "parameters": params}
        origin = c("firstSnap0", 1, "bottom.start")
        origin["parameters"].append({"$type": "bsedit.GBTMParameterQueryList", "parameterId": "externalSecond",
                                     "queries": [{"$type": "bsedit.GBTMIndividualQuery", "deterministicIds": []}]})
        def dim(ident, side, value):
            item = c(ident, 11, side)
            item["parameters"] += [p("direction", "MINIMUM", "Enum"),
                                   p("length", value, "Quantity", units="millimeter", expression=f"{value} mm"),
                                   p("alignment", "ALIGNED", "Enum"),
                                   p("labelRatio", .5, "Quantity"), p("labelDistance", .01, "Quantity")]
            return item
        sketch["constraints"] = [origin, c("perpendicular", 5, "top", "left"),
                                  c("parallel.1", 2, "bottom", "top"), c("parallel.2", 2, "left", "right"),
                                  c("horizontal", 4, "top"), c("corner0", 1, "bottom.start", "left.start"),
                                  c("corner1", 1, "bottom.end", "right.start"),
                                  c("corner2", 1, "top.start", "left.end"),
                                  c("corner3", 1, "top.end", "right.end"),
                                  dim("width", "top", 40), dim("height", "right", 20)]
    datum = {"featureId": "default-top", "featureType": "datum", "nodeId": "prior",
             "name": "changed" if unrelated_changed else "Top"}
    return {"target": {"did": TARGET.did, "wid": TARGET.wid, "eid": TARGET.eid},
            "element_microversion": "b" * 24 if populated else "a" * 24,
            "connected": True, "editingFeatureId": None if populated else "editorAllocated_0",
            "h2Readback": {"contract": "h2-readback-probe-v1", "complete": False},
            "tree": {"$type": "bsedit.GBTMModel", "children": [datum, sketch]}}


class Bridge:
    def __init__(self, *, changed=False, capabilities=True):
        self.calls = []
        self.changed = changed
        self.capabilities = capabilities

    async def health(self):
        return {"extension_connected": True,
                "capabilities": ["h2_native_sketch_populate_server_v1"] if self.capabilities else [],
                "extension": {"capabilities": ["h2_native_sketch_populate_page_v1"]}}

    async def command(self, job):
        self.calls.append(copy.deepcopy(job))
        if job["kind"] == "state":
            populated = sum(x["kind"] == "state" for x in self.calls) > 1
            return state(populated=populated, unrelated_changed=self.changed and populated)
        assert job["kind"] == "partstudio_populate_sketch"
        assert job["sketch_edit"] == {"feature_id": "editorAllocated_0", "entity_prefix": "box",
                                      "rectangle_m": [0.0, 0.0, 0.04, 0.02]}
        return {"definition_candidate": True}


@pytest.mark.asyncio
async def test_source_pair_journals_one_write_and_verifies_native_definition(tmp_path):
    bridge = Bridge()
    journal = Journal(tmp_path / "intent.sqlite")
    evidence = await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert evidence["definition_verified"] is True and evidence["geometry_verified"] is False
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch", "state"]
    assert journal.get(evidence["op_id"])["state"] == "observed"
    journal.close()


@pytest.mark.asyncio
async def test_unrelated_tree_change_remains_unknown_and_is_never_replayed(tmp_path):
    bridge = Bridge(changed=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(UncertainWrite, match="outcome unknown"):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert [x["kind"] for x in bridge.calls] == ["state", "partstudio_populate_sketch", "state"]
    assert journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_missing_loaded_capability_stops_before_journal_or_write(tmp_path):
    bridge = Bridge(capabilities=False)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(Unsupported, match="both advertise"):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    assert bridge.calls == [] and not journal.has_unresolved()
    journal.close()


@pytest.mark.asyncio
async def test_uncertain_sketch_reconcile_reads_once_and_does_not_resubmit(tmp_path):
    bridge = Bridge(changed=True)
    journal = Journal(tmp_path / "intent.sqlite")
    with pytest.raises(UncertainWrite):
        await NativeBackend(bridge, tab_id=17).populate_test_sketch(TARGET, SOURCE, journal)
    op_id = journal.unresolved(f"{TARGET.did}/{TARGET.wid}/{TARGET.eid}")[0]["op_id"]
    before = len(bridge.calls)
    outcome = await NativeBackend(bridge, tab_id=17).reconcile_test_sketch(op_id, journal)
    assert outcome["status"] == "unknown"
    assert [x["kind"] for x in bridge.calls[before:]] == ["state"]
    journal.close()


def test_cli_exposes_explicit_temp_sketch_command():
    args = build_parser().parse_args(["experimental-sketch-populate", str(SOURCE),
                                      "--did", TARGET.did, "--wid", TARGET.wid, "--eid", TARGET.eid,
                                      "--bridge-config", "bridge.json", "--tab-id", "17", "--journal", "intent.sqlite"])
    assert args.command == "experimental-sketch-populate" and args.tab_id == 17
