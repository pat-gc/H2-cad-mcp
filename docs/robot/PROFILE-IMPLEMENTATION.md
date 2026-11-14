# Profile implementation audit

Scope: generic profile capability, not a dimensioned or rated vendor extrusion.
No browser experiments or runtime modifications were performed for this audit.

## Current routes

| Route | Local FSGen | Current native source writer | Consequence |
| --- | --- | --- | --- |
| Single rectangle NEW, one rectangular or circle-only REMOVE sketch | Supported | Supported with explicit observed target binding | Suitable for the hollow square-tube fixture or one group of holes; not genuine T-slot geometry |
| Rectangle NEW followed by several separate rectangular/circular REMOVE features | Supported locally | A later body lineage and complete-scope proof are missing | Coordinator now rejects a second REMOVE targeting the same source NEW body before local build or allocation |
| One closed arbitrary profile NEW | `skPolyline` and individual line segments exist | Only one four-line rectangle or circle-only sketches are mapped | Requires native contour and constraint mapping; not a fixture-only extension |
| Mixed outer polygon and inner loops in one sketch | Broader local geometry exists | No general mixed/nested profile mapper | Requires region/inner-loop semantics and independent topology proof |

The rectangle mapper requires four lines and twelve source constraints, including
nonzero first-corner coordinates. A T-slot contour cannot be passed through that
mapper by changing its label. `skPolyline` emits line entities between consecutive
points; its existence does not supply a native editable constraint mapping or
prove that an intended contour is closed.

## What patch46 actually proves about a second REMOVE

Patch46 requires the original target NEW operation to be observed, its exact
saved extrusion definition and source sketch to remain unchanged, and a selected
native body to resolve to that NEW feature ID with `fullOperationId` equal to
`<NEW featureId>.opExtrude`. It requires one selected body ID, not default scope.

An earlier REMOVE normally adds a sibling feature rather than modifying those
original saved definitions. Consequently, patch46 does **not categorically reject
a second REMOVE**. The second would pass its lineage guard only if the current
body query still reports the original NEW feature and operation. That behavior
after a prior cut has not been independently observed here. If Onshape reports
a later feature instead, the current guard rejects it; do not loosen that guard
or substitute guessed IDs.

More importantly, unchanged original definitions do not prove the current number
of bodies. A first cut can split an initially single-profile NEW body into two.
Selecting one descendant can still appear to have the original creator identity,
while source `qCreatedBy(NEW, BODY)` denotes all descendants. Matching a feature
ID for one selected body therefore does not prove complete source scope.
FSGen local subtraction explicitly creates each result solid with the prior
body's creator, so this distinction matters locally as well.

**Conservative coordinator guard added:** one REMOVE per source NEW target.
It rejects repeated targeting before local validation, checkpoint creation, or
Browser allocation, including a split-producing first cut. First-cut carrier
and hollow-tube workflows remain allowed. This is a coordinator restriction;
the direct extrusion writer and Native runtime were not changed and must not be
advertised as proven repeated-cut support.

## Smallest next implementation step

Keep the existing first-cut workflow. Before enabling sequential cuts, create a
bounded two-cut evidence fixture and implement a current, complete target-body
set proof tied to the exact target/revision and observed modification chain.
Capture normal-UI body selection/query evidence after the first cut. Initially
accept only a proven single surviving body; reject split, deleted, or ambiguous
descendants. Do not infer current cardinality from the original source sketch,
whole-studio part count, or unchanged deterministic IDs alone. Preserve exact
saved definitions and journal recovery barriers.

Required tests and live acceptance:

1. Two disjoint holes in a rectangular blank: first cut preserves one body;
   second cut resolves its actual lineage and matches local volume and bounds.
2. First cut splits the blank into two solids: selecting one must reject before
   SpecifyFeature; the original creator reference must not silently narrow.
3. Untouched witness solid: neither cut may modify it; validate each body, not
   just combined volume or part count.
4. Wrong creator, changed target sketch, intervening unjournaled modification,
   stale revision, default all-body scope, and missing lineage evidence reject.
5. Save/unknown/reconciliation and an ordinary dimension edit/restore preserve
   exact identities and the complete scope proof.

If lineage evidence cannot support that bounded path, the alternative is a
reviewed orthogonal closed-polyline mapper. Start with one simple non-self-
intersecting contour, exact coincident endpoints, horizontal/vertical constraints
and retained source dimensions, then mandatory active solver coordinate proof
before Commit. Inner loops and mixed profiles should be a separate acceptance
step. Neither route establishes genuine manufacturer T-slot dimensions or
mechanical ratings; those require the selected drawing and separate engineering
validation.

## Code inspected

- `src/h2cad/source_run.py`: `_plan`, source dependency order and repeated-target guard.
- `src/h2cad/native_source_extrusions.py`: observed target NEW/sketch binding.
- `src/h2cad/native_extrusions.py`: `verify_target_body_query`, one-ID source scope.
- Native patch46 `onshape_native/source_extrusion.py`: independent saved-sketch guard.
- `src/h2cad/native_sketches.py`, `native_rectangles.py`, `native_circles.py`: profile limits.
- `upstream/onshape-fsgen/fsgen/native/script.py`: `skPolyline` emits consecutive lines.
- `upstream/onshape-fsgen/fsgen/native/local.py`: subtraction retains creator on resulting solids.
