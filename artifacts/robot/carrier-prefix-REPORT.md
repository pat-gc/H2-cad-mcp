# Carrier setup: local source to native features

2026-11-14. Root owns the live browser; other agents have no live-write ownership.

The experimental source-run coordinator created all eight features preceding
the final cut in `fixtures/native/carrier_remove_scope_sample.fs`: one length
variable, two planes, three constrained sketches and two NEW extrusions. Browser
allocated blank features and selected references; the coordinator populated
source geometry, expressions and dependencies through the existing guarded
writers. No REST CAD writes, imported solids or custom FeatureScript feature.

Target: document `4e078dec822b4e509616b1cb`, workspace
`af0627de07264acf086e646a`, Part Studio `423a1c4eec848f03a9800ba5`, named
**Robot - Carrier Scope Test**. Saved revision `076e2127daeaffcc472f0fe4`.
The [identity map](carrier-prefix-coordinator.json) records every operation and
native feature ID. Local prefix source is the exact full fixture before its
final `Carrier through bores` extrusion, with the build function closed.

Independent normal Onshape Mass Properties measurements:

| Selection | Onshape volume | Local expected |
| --- | ---: | ---: |
| Carrier blank | 43,200 mm³ | 43,200 mm³ |
| Witness | 10,800 mm³ | 10,800 mm³ |
| Both parts | 54,000 mm³ | 54,000 mm³ |

Evidence: [blank](carrier-blank-volume.png), [witness](carrier-witness-volume.png),
[combined](carrier-prefix-total-volume.png). The prefix includes the hole sketch
but no saved cut; these numbers are deliberately the uncut volumes.

A normal UI REMOVE draft supplied the [scope query](native-remove-scope-query.json).
The body selection resolves `JID` to source extrusion `FZT3wk30E2c6tsM_0`, entity
type BODY (3), operation `.opExtrude`, with `defaultScope=false`. Switching the
UI to REMOVE automatically reversed direction; restoring source-positive
direction was necessary. The schema draft was canceled normally, restoring the
exact prior tree and revision. No REMOVE write is accepted yet.

This live run found and fixed a target-configuration mismatch: the CLI reread
the new target while the server retained its startup configuration. Patch44
exposes the running target in authenticated health and explicitly classifies
this broker-side rejection as pre-dispatch. The coordinator now checks running
target before creating a journal/run. The [historical rejection proof](carrier-target-rejection.json)
records unchanged draft state and no extension dispatch; it was resolved before
the companion restarted. The variable then succeeded through normal dispatch.

Still required: native scoped cut and unchanged witness proof, edit/restore,
centered/axis circle live solver proof, and the complete robot assembly.
