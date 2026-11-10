# Native editor integration status

The local backend speaks only the separately installed companion's authenticated
`/health` and `/command` (`state`, `schema`, `native`) routes. It rejects REST jobs.
The companion source and captured workflow are not included in this project.

`NativeBackend.raw_state()` exposes the exact editor tree for inspection. Its
normalized `read()` deliberately reports `complete=False`, because the observed
tree has no proven, stable mapping to complete feature definitions, statuses,
sketch constraints, and solid geometry. `capabilities()` therefore advertises no
supported write kinds or atomic revision enforcement. The executor rejects
normal existing-document mutations on this backend.

`stage_rectangle()` can compile semantic rectangle coordinates in meters to the
observed typed sketch entity command after checking the active runtime schema
and **live-editor** entity/inference IDs. It is only one step of a transaction;
it does not create a sketch. `stage_extrusion()` validates depth and sketch
dependency, then lists missing bindings. Neither function replays captured IDs.

The following live observations are required before enabling a disposable-test
document vertical slice:

1. How the active editor allocates feature, node, parameter, sketch entity, and
   inference IDs, and how each ID is scoped across commands and revisions.
2. A fresh insertion location, sketch plane query, feature settings response,
   and exact parameter IDs from the active runtime, rather than a recording.
3. The response and state transition after each sketch/rectangle/dimension/
   extrusion call, including failure and interrupted transaction behavior.
4. A stable native readback of complete feature definitions, sketch constraints,
   feature regeneration status, and resulting solid geometry. An RPC acknowledgement
   or changed microversion alone is insufficient.
5. An atomic server-side revision guard for existing collaborative models. The
   current element microversion check is client preflight only.

The SQLite journal persists intent before submission, never retries an uncertain
write, and stores the last **actual verified** remote Snapshot as a sync base.
Read-only reconciliation can confirm a prior write only with complete positive
identity and semantic evidence; a create without a confirmed native ID stays
unknown. No-op execution refreshes the sync base only from complete readback.

Offline tests use an HTTP fake bridge with the real adapter serialization path,
plus fake backend state transitions for executor failure cases. They do not claim
live Onshape sketch or extrusion acceptance.
