# Native integration readiness — 2026-11-10

## Verified offline foundation

The pinned FSGen compiler creates a semantic feature snapshot from supported
scripts, including variables, sketch geometry, and extrusion dependencies.
OpenCascade validates the plate example locally as one solid. The planner merges
independent parameter edits while preserving observed human changes and feature
order. The executor journals intent before submission, blocks unresolved writes,
and requires exact identity, semantic, regeneration, and unrelated-feature
readback before confirming an operation. No-op execution persists only complete
remote readback as a sync base.

The CLI supports compile, validate, plan, doctor, inspect, and read-only
reconcile. Bootstrap pins FSGen at
`eabcc02ba104005da3de869e613cefe53042fd98` and Native at
`f5304ed0aa49347dec40911af9c2018d81012604`, then applies the reviewed
three-commit Native patch stack. An existing Native checkout is accepted only at
the base commit or an exact prefix of that stack with its reviewed Git tree. Extra clean
commits and content are refused; dirty checkouts are never overwritten.

## Native modeling capability

| Capability | Status | Evidence |
| --- | --- | --- |
| Exact editor target and element revision read | Offline adapter tested | Fake bridge and upstream Node tests; live editor not inspected here |
| Browser transport without developer API keys | Upstream implementation audited | Extension, loopback broker, typed editor RPC |
| Semantic rectangle command staging | Offline tested | Runtime schema shape and explicit live binding checks |
| Native editable sketch/extrusion transaction | **Blocked** | Captured command sequence only; fresh IDs and full transaction not replay verified |
| Complete native feature/geometry readback | **Blocked** | Fork probe explicitly returns `complete=false` |
| Atomic collaborative revision enforcement | **Blocked** | Upstream native check is client preflight only |
| Incremental existing-document mutation | **Blocked** | Executor requires atomic revision and complete readback |

No live Onshape document was mutated. The offline tests do not establish browser
extension readiness or native feature editability. The next live test needs an
explicit disposable workspace URL, an authenticated and paired browser, and
read-only inspection of current runtime schema, model tree, and ID allocation
before any native write is considered.

## Regression evidence

Before the pinning fix, the independent test with a clean extra commit failed
under `--runxfail` because bootstrap returned successfully. The test now uses a
local clone at the exact base, applies the reviewed patch with a different
committer, and adds either an empty or content-changing commit. Both are
rejected. The base and exact reviewed patch are accepted in the bootstrap
round-trip test. The worktree suite passed **36/36**, with no skips or xfails,
using x64 CPython 3.11.9. The same two adversarial pinning cases passed from a
temporary root-style directory layout (2/2), so the fixture discovery does not
depend on `.worktrees` path depth.
