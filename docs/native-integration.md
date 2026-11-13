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

## Reload the paired extension worker

After the reviewed Native patch is installed, pin the existing H2 journal in
the Native bridge configuration with `scripts/configure.py --h2cad-journal
PATH_TO_JOURNAL_DB` and restart the bridge. The same journal must be supplied
to H2's experimental depth edit and reload commands. This setup preserves
pairing; it does not create a new token. A missing or unresolved journal blocks
the reload command.

Run `h2cad extension-reload --bridge-config PATH_TO_BRIDGE_JSON --journal
PATH_TO_JOURNAL_DB` for a bounded, structured result. The loaded older worker
does not contain the handler and reports `needs_manual_bootstrap`; one normal
manual Reload of the Onshape Native extension is then required. Later calls use
only that extension worker's `chrome.runtime.reload()` and require a new
matching worker identity, build, capability, and pairing handshake. An
uncertain result must be inspected manually; neither H2 journal state nor a
potentially committed CAD mutation is cleared by reload.
The bridge also keeps a local safety record beside the pinned journal. A
pending or uncertain reload or CAD write remains blocked after a bridge
restart; the record must not be deleted to force another attempt.
