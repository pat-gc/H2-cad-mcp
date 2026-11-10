# Evidence-based acceptance gates

Passing a local test never marks a live Onshape criterion complete. Each report
must name the implementation commit, backend, fixture or explicit document target,
validation layer, exact command, and outcome.

## Initial vertical slice

1. Compile a dimensioned closed rectangular sketch and dependent extrusion into
   deterministic native feature definitions. Preserve separate native feature IDs.
2. Reject unsupported operations and unresolved references before mutation.
3. Bind every command and readback to document/workspace/element identity.
4. Negotiate backend capabilities; a write requires a documented, implemented
   compatibility path. No silent official developer REST fallback.
5. Read current remote revision before planning and guard execution against stale
   state. Where server-side compare-and-set is unavailable, disclose the residual
   race and fail closed for unsafe existing-document editing.
6. Persist submission intent before sending. A lost response is an unknown outcome;
   reconcile using remote feature identity and content instead of replaying create.
7. Verify the remote feature definition, dependency target, and regeneration state.
   Transport success alone must not produce a successful CAD result.
8. With an authorized disposable Part Studio, inspect and open the resulting sketch
   and extrusion in Onshape, modify a dimension, and verify regeneration. Until
   access exists, this live gate remains blocked rather than passed by mocks.

## Incremental collaboration scenarios

- A base bracket has thickness 3 mm and hole diameter 6 mm. A human changes
  thickness to 4 mm; desired changes only diameter to 8 mm. The merged result must
  retain 4 mm thickness and 8 mm diameter without replacing unrelated feature IDs.
- Both parties modify the same parameter differently: produce a structured
  conflict and send zero writes.
- Human adds, reorders, or modifies unknown features: preserve them or report an
  explicit unsupported structural conflict. Never adopt by matching names alone.
- Upstream geometry changes while a dependent topology reference is ambiguous:
  stop with a diagnostic; never choose the first edge or face.
- Revision changes between plan and execution: reject stale plan. Race behavior
  must be stated accurately for the actual protocol, not only for a fake backend.

## Failure injection

- Timeout before submission, during submission, after remote commit, and during
  verification must have distinguishable durable states.
- Restart after a potentially committed write must not duplicate the feature.
- Wrong document or element returned by bridge must fail before mutation.
- Failed regeneration must not be reported as confirmed CAD success.
- Malformed native payload, unsupported command, unauthorized local bridge caller,
  or unavailable compatibility profile must fail closed.
- Mid-plan failure must report confirmed operations and unresolved outcomes; do
  not promise an atomic rollback that Onshape does not provide.

## Validation levels

Report independently: static representation checks; local OpenCascade geometry;
remote regeneration; semantic equivalence; human editability. Not-run and blocked
are first-class results distinct from pass and fail.

## Benchmarks

Commit reproducible fixtures for a basic parametric plate, bracket, existing-model
edit, independent human/AI changes, ambiguous reference, interrupted execution,
and larger graph. Record planning duration, local validation duration, operation
counts, remote/readback latency where measured, and reconciliation counts.
No throughput or quota exemption claim is accepted without measurement.
