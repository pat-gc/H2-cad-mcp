#!/usr/bin/env python3
"""Reproducible offline compiler, planner, and OCC timings; no network calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from h2cad.fsgen import compile_fsgen
from h2cad.model import Target
from h2cad.planner import plan_changes
from h2cad.validation import validate_fsgen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args(argv)
    if not 1 <= args.iterations <= 100:
        parser.error("iterations must be 1..100")
    source = args.source.read_text(encoding="utf-8")
    target = Target("a" * 24, "b" * 24, "c" * 24)
    times = {"compile_ms": [], "plan_ms": [], "local_validation_ms": []}
    feature_count = None
    geometry = None
    for _ in range(args.iterations):
        start = perf_counter()
        snapshot = compile_fsgen(source, target)
        times["compile_ms"].append((perf_counter() - start) * 1000)
        feature_count = len(snapshot.features)
        start = perf_counter()
        plan = plan_changes(snapshot, snapshot, snapshot)
        times["plan_ms"].append((perf_counter() - start) * 1000)
        if plan.conflicts or plan.operations:
            raise RuntimeError("Identical snapshots unexpectedly produce changes")
        start = perf_counter()
        report = validate_fsgen(source)
        times["local_validation_ms"].append((perf_counter() - start) * 1000)
        if report.status != "passed":
            raise RuntimeError(f"Local validation {report.status}: {report.error}")
        geometry = report.geometry
    result = {"source": str(args.source.resolve()), "iterations": args.iterations,
              "feature_count": feature_count, "geometry": geometry,
              "median_ms": {key: round(statistics.median(values), 3) for key, values in times.items()},
              "samples_ms": {key: [round(value, 3) for value in values] for key, values in times.items()},
              "remote": "not_run", "native_editability": "not_run"}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
