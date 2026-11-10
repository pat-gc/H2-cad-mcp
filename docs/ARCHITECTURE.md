# Architecture decision 0001: semantic planning around existing compilers

Status: accepted for the first implementation; live native compatibility unproven.

## Evidence and choice

FSGen already has a useful `FeatureRec` tracer and native feature serializer, plus
local OpenCascade evaluation. Its current positional suffix synchronization can
replace features and has no remote three-way merge. Onshape Native exposes genuine
typed editor RPCs, but its native write revision guard is client preflight only;
the sketch/extrusion capture is observation rather than verified replay.

Choose a small Python semantic model and deterministic planner/executor around
these components. Preserve FSGen compilation and local geometry as an optional
pinned dependency. Use an independently implemented adapter against the installed
Native bridge protocol, without bundling its source or captures while its license
is unresolved. Native browser mode may never emit `kind: rest` or silently switch
to the developer API.

The semantic representation wraps complete native feature definitions and adds
logical IDs, explicit dependencies, ownership, remote IDs, revision identity, and
verification provenance. It is not a second CAD kernel or a universal geometry
language. The first compiler coverage is constrained by tested serialization and
reference support; unknown topology queries fail closed.

## Rejected alternatives

- REST client substitution preserves unsafe positional synchronization and cannot
  translate REST feature JSON directly into the different native editing lifecycle.
- A broad unified rewrite would discard working tracing and OCC code before the
  undocumented native protocol is validated.
- Replaying captured messages would reuse session-specific node IDs and selection
  references. A recording is evidence for an adapter, not an executable design.
- General semantic merge is too risky initially. Merge independent parameter keys;
  report conflicting values and unsupported structural changes explicitly.

## Execution and persistence

Use a SQLite journal with durable intent recorded before each submission and no
automatic retry of a possibly committed write. Operations are serial per target.
Readback must verify identity, semantic fields, and regeneration independently.
Unknown outcomes remain unresolved until positive remote evidence or explicit
operator resolution; absence from incomplete readback is not evidence of failure.

The first production safety boundary rejects existing-document changes on adapters
without atomic server revision enforcement. An explicit experimental isolated-test
target can exercise the preflight-only native workflow with the race disclosed;
this mode is not advertised as safe collaborative synchronization.

## Shared implementation contract

Python 3.11+, package `h2cad`. Core model is stdlib dataclasses and JSON values.

- `Target(did, wid, eid)` identifies one unconfigured workspace Part Studio.
- `Feature(logical_id, kind, parameters, dependencies=(), structure={},
  native_id=None, ownership='ai', regeneration='unknown')` holds canonical
  parameter-ID/value mappings; nonparameter sketch/native fields live in
  `structure`. Dependencies refer to logical IDs. Ownership is ai/human/shared/
  unknown. Native IDs are never inferred from display names.
- `Snapshot(target, revision, features, complete=True)` records ordered features.
- `Operation(op_id, action, logical_id, before, after)` supports create/update
  initially. Deletion is rejected by default.
- `Conflict(logical_id, path, reason, base=None, observed=None, desired=None)`.
- `Plan(target, expected_revision, operations, conflicts, merged)` is a dry-run
  artifact. `merged` is the intended merged Snapshot preserving human features.
- `plan_changes(base, observed, desired) -> Plan` performs deterministic dependency
  validation and three-way merge. Conflicts make the whole plan nonexecutable.
- Model types provide `to_dict()`/`from_dict()` and canonical semantic equality
  that excludes transient regeneration and provenance where appropriate.
- Async backend protocol: `capabilities() -> Capabilities`,
  `read(target) -> Snapshot`, `apply(operation, target, expected_revision) -> Receipt`.
  Capabilities records supported feature kinds, atomic revision support, backend
  category and verification evidence. Receipt includes any assigned native ID and
  revision, but executor always performs readback itself.
- `Executor(backend, journal).execute(plan, experimental_isolated=False)` returns
  explicit per-operation outcomes and separate verification evidence. Interface
  details may evolve jointly between workers; record changes rather than silently
  diverging.

## Revisit when

Live native schema/readback proves a safer transactional mechanism; upstream
licenses change; compiler support requires richer references; or measurements show
the small representation cannot preserve actual design intent.
