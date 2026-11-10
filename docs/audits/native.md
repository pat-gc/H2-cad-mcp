# Onshape Native audit (2026-11-10)

## Provenance and redistribution

- Upstream: `https://github.com/godbrigero/onshape-native`, pinned commit `f5304ed0aa49347dec40911af9c2018d81012604` (cloned to ignored `upstream/onshape-native`).
- The root has no `LICENSE`, `COPYING`, or `NOTICE`; `pyproject.toml` declares no license. `data/LICENSE-APACHE` is an Apache 2.0 license text inside `data`, but does not establish permission to redistribute the entire repository. Treat source and captured fixtures as unlicensed until the owner clarifies. This project should depend on a separately installed copy, not vendor its code or workflow capture.
- `AGENTS.md` permits coherent local commits, not publication. No live Onshape document was accessed in this audit.

## Actual transport and scope

`extension/connection.js` opens `ws://127.0.0.1:8766/extension`, sends pairing token plus extension capabilities, and never replays commands after a drop. `onshape_native/bridge.py` accepts only a Chrome extension origin, checks the token, serializes commands and routes them to `extension/worker.js`. The worker selects the exact `cad.onshape.com` tab and injects `pageCommand` into Chrome's MAIN world. `extension/page-adapter.js` loads one of three hard-coded Onshape webpack module profiles, hydrates nested typed messages with the active serializer, and calls `controller.elementConnection.callAndPromise(message)`. Runtime profile failure closes native operation availability. This is an undocumented, version-sensitive Onshape editor interface.

There is a distinct browser-session REST channel in the same project. `page-adapter.js` uses same-origin `fetch` with the signed-in browser cookie and CSRF token; `rest-get.js` handles GETs and redirects. The higher-level `Service.inspect`, `Service.feature`, and `Service.eval` use REST endpoints. Thus `feature(...)` and `inspect_model(...)` cannot be claimed as pure native-editor RPC operations, even though they use no developer API key. The integrated backend must never silently fall back to these for its normal native path.

`native_catalog` reads `data/native-commands.json` and `docs/evidence/workflow.json`; `native_schema` queries defaults from the currently loaded serializer. A schema entry means structurally discoverable, not behaviorally supported. `native_catalog.VERIFIED` excludes native `GBTUiAddFeatureCall`, sketch creation/entity calls, and extrusion `GBTUiSpecifyFeature`; those appear only as observed capture. `native_modeling_v1` advertises assembly feature edits, transform and measurement support, not sketch/extrusion replay validation.

## Editable sketch and extrusion evidence

The captured workflow records `GBTUiGetFeatureSettingsCall` (sequence 19), `GBTUiUpdateEditRollbackState` (20), `GBTUiAddFeatureCall` with a typed `bsedit.GBTMSketch` node (21), and `GBTUiCommit` (78). It then records sketch rectangle (101), circle (114), dimension add (124), dimension modify (128), and another commit (132). Extrusion uses settings (497), rollback (498), `GBTUiAddFeatureCall` with `bsedit.GBTMFeature`/`featureType="extrude"` (499), three `GBTUiSpecifyFeature` calls (502–504), and `GBTUiCommit` (508). All IDs, tree insertion location, sketch plane reference, selection queries, dimensional expressions, and transaction sequence values must be derived from fresh state or the active editor, never replayed from the capture. Captured messages contain example IDs and session-specific state.

Current `native_write` merely dispatches one schema-discovered message, returns the reply and before/after document microversion, and recommends `native_state` afterward. It does not compile a feature plan, manage a complete sketch/extrusion transaction, check feature regeneration, or verify geometry. A native sketch/extrusion vertical slice remains experimental until tested in an explicitly disposable document.

## Readback, revision, and failure behavior

- `native_state` returns exact target, document `microversion`, element `element_microversion`, connection/editing state, and a plain serializer-expanded model tree from `documentClientCache` or the active assembly definition. It does not return the full Part Studio feature definition, sketch constraints, feature-status proof, or evaluated solid geometry as a stable contract.
- `native_read` is restricted to `READS` in `native_catalog.py`. `GBTUiSketchGetConstraintGraphCall` and `GBTUiSketchGetProjectionCall` are available as read commands, but their response semantics are not tested as a general post-write verifier. `native_schema` returns defaults and class ID only.
- The bridge validates a 24-hex expected document or element microversion. The page compares it immediately before `callAndPromise`; an element guard tolerates unrelated document edits. This is a client preflight, **not atomic compare-and-swap**. A collaborator can edit between comparison and commit. For existing collaborative models, native mutation must fail closed until an atomic guard exists. Explicit disposable-target testing may accept the residual race with disclosure.
- The bridge timeout/disconnect marks outcome unknown; neither broker nor extension retries the write. Error replies are bounded, but an acknowledgement does not establish committed geometry. A caller must journal pending intent, then reconcile against fresh state before deciding whether to proceed. Existing `Service.feature` has `sourceMicroversion`/`rejectMicroversionSkew=true`, but that guard belongs to the browser-session REST feature API, not native RPC.

## Minimal integration contract

Use an independently installed Onshape Native companion as an optional transport dependency, with an adapter speaking its documented local bridge commands. Keep its pairing token private and never expose arbitrary REST jobs through the CAD executor. The adapter should expose only:

1. `health()` / `capabilities()` including extension version and required `element_revision_v1`, `native_modeling_v1`, and an exact supported command/profile set. No capability claim based solely on schema presence.
2. `state(target, tab_id)` returning raw state plus an adapter-normalized target/revision/tree view and an explicit completeness flag. Reject configured, version, or microversion URLs for native writes.
3. `schema(command)` and `read(command, body)` for typed native discovery and deterministic reference resolution. Unknown frontend profiles, constructors, fields, response shapes, and command versions fail closed.
4. `write_once(command, body, expected_element_microversion, tab_id, journal_id)` only for a verified operation and explicitly disposable target until atomic concurrency support exists. Never auto-retry or infer success from RPC acknowledgement. Record `prepared -> sent/unknown -> observed` locally; reconcile exact feature IDs, properties, revision, regeneration and geometry after each commit. A complete sketch/extrusion executor must manage all intermediate commands and fresh IDs itself.

Compiler input should be semantic operations (plane, rectangle/circle with dimensions and constraints, extrusion depth/operation, stable logical IDs), not captured native message JSON. The adapter compiles to runtime-specific typed messages only after fresh state/schema checks; return `unsupported` if a semantic field cannot be represented or verified. Geometry and feature-status verification currently require additional validated native readback; the REST `inspect_model` path is not acceptable as an invisible substitute.

## Baseline on Windows

Environment: Windows PowerShell, Python 3.14.6, uv 0.11.32, Node 24.18.0. `uv sync --frozen --group dev` succeeded. `uv run --frozen python scripts/package.py` succeeded and produced ignored `dist/onshape-native-0.5.0.zip` (audit did not redistribute it). `node --test tests/*.test.mjs`: **82 passed**.

`uv run --frozen pytest -q`: **217 passed, 4 failed, 1 skipped**. Two failures are default Windows cp1252 decoding of UTF-8 Markdown in `tests/test_install_local.py`. Setting `PYTHONUTF8=1` yields **219 passed, 2 failed, 1 skipped**. Remaining failures: `test_artifact_download` cannot create a symlink under this Windows account (`WinError 1314`); `test_portable_install` expects `repo/back\\slash` archive member rejection, but `installer.unpack` accepts it. The latter is a substantive Windows archive path validation gap, not an environment-only failure. No live integration tests or Onshape build/profile verification were run.
