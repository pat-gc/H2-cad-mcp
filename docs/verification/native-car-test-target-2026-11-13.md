# Native car test target and read-only readiness — 2026-11-13

The user authorized development and testing of an actual native editable feature tree in the existing **H2 CAD Test Project**, with the current custom-feature car preserved until a full native replacement is independently verified. This record covers target setup and read-only probing only. No native feature creation, deletion, or modification was attempted in this phase.

## Exact document inventory

Document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`:

| Element | Element ID | Observed contents |
| --- | --- | --- |
| [Existing car Part Studio](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/45730d1931712e2c548fae00) | `45730d1931712e2c548fae00` | Four default features plus one `H2 Minimal Car 1` custom feature; `Parts (8)`. Preserve while testing. |
| [Feature Studio](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/39a2e2afc5bc43eea167e938) | `39a2e2afc5bc43eea167e938` | Generated car FeatureScript; preserve while testing. |
| [Native Adapter Test — Temporary](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/9a062f0eef8bb961f8c84f8e) | `9a062f0eef8bb961f8c84f8e` | Newly created isolated test studio; only Origin, Top, Front, Right; `Features (4)`, `Parts (0)`. Native adapter test target. |
| Default Assembly 1 | `cb5c127f6a4b4eb2ab5838c9` | `Instances (0)`, `Mate features (0)`. No associated car assembly observed. |

The previous disposable control document is outside this target and was not changed.

## Read-only native evidence

The paired bridge reported protocol 1, extension connected, version 0.4.4, with the existing native-modeling and element-revision capabilities. For the temporary Part Studio on exact Edge tab `941740711`, `native_state` returned `connected=true`, `editingFeatureId=null`, element microversion `a2efdd3e750edc90f6f84034`, `bsedit.GBTMModel`, and four default feature candidates. The live root has `ModelTreeId`, one rollback child, and Top under `defaultFeatures` with `featureId=Top` and node ID `MMaGxUk2pFcXnJ+V3`. Its `h2Readback.complete=false`; the tree contains no established complete feature/regeneration/geometry readback.

The runtime serializer resolved `ui.GBTUiAddFeatureCall`, `ui.GBTUiCommit`, `ui.GBTUiSpecifyFeature`, `ui.sketch.GBTUiSketchAddRectangleCall`, `diff.GBTTreeEditList`, `diff.GBTTreeEditInsertion`, `diff.GBTTreeEditChange`, `tree.GBTInsertionLocation`, `tree.GBTNodeReference`, `bsedit.GBTMSketch`, `bsedit.GBTMFeature`, sketch/feature parameter classes, and the listed read commands. `bsedit.GBTMExtrude` was rejected because extrusion uses `bsedit.GBTMFeature` with `featureType=extrude` in the captured workflow. Schema defaults supplied node IDs but no feature IDs, parameter IDs, insertion node reference, plane query, or region selection. Feature settings for `::newSketch` and `::extrude` returned UI preferences, not feature templates.

Official read-only Native `ui_inspect` on the exact tab listed Search tools but no labeled Sketch toolbar control. The ordinary browser accessibility tree and screenshot did show Sketch as toolbar text/icon. `ui.GBTUiGetQueryDataCall` is structurally discoverable with empty `qFunction`/`queries` defaults; the captured sample uses an opaque recording-specific deterministic ID. No supported read was found that resolves the live Top feature/node to a valid plane query. No query ID was guessed or replayed.

Private raw readbacks are in the ignored installed companion runtime directory (`upstream/onshape-native/.runtime/`): `h2cad-native-car-empty-state.json`, `h2cad-native-car-probe.json`, `h2cad-native-car-nested-schemas.json`, `h2cad-native-car-feature-schemas.json`, `h2cad-native-car-read-schemas.json`, and `h2cad-native-car-ui-inspect.json`. They are not claimed as acceptance of native writes.

The temporary tab was returned to the empty native-test studio and left open for the next verified adapter trial. Before any later write, read a fresh target revision and re-check feature/part inventory; the recorded microversion is only historical evidence.

## Patch 8 bounded read-only probe and clean recovery

The reviewed eighth Native patch was staged through `scripts/bootstrap.py --sources-only` into the clean pinned checkout. The existing paired local broker was restarted, with its configured H2 journal intact and no unresolved writes. The official own-extension self-reload returned `reconnected/new_handshake_verified` with a new worker instance. A single `native-create-probe` call on the existing test tab then ended after approximately 306 seconds with HTTP 400 and no method-name result. The H2 client did not retain the 400 body. A separate read-only tab status reported that a previous read-only command was still running in that editor. Health showed extension connected and `pending=0`; the persistent guard showed `unknown_write=false`. The probe was **not** retried on the stuck tab.

The owned stuck tab `941740711` was closed to terminate its page context. A fresh exact target tab `941740731` opened the same temporary Part Studio. Browser UI showed `Features (4)` and `Parts (0)`. Read-only native state returned `connected=true`, no active edit, and element microversion `a2efdd3e750edc90f6f84034`. Full raw before state is `upstream/onshape-native/.runtime/h2cad-native-car-before-sketch.json`.

## Ordinary editor sketch allocation observation

With explicit user authorization for this isolated test, the normal Onshape Sketch toolbar control (`div.tool[command-id="newSketch"]` observed in the live DOM) was clicked once, then Top was selected from the default feature tree. No rectangle, extrusion, or car geometry was drawn. The sketch remained active and uncommitted at the handoff.

The resulting native state returned `connected=true`, `editingFeatureId=FuOP7N2XtGyhaTz_0`, element microversion `60a8a42ddbbc99a9921b4888`, and a `bsedit.GBTMSketch` node `MDKJR9IkaqO8+o581` named `Sketch 1`. Its entity and constraint lists were empty. The `sketchPlane` query-list node was `S11Vu1Q+5JMdHd43`; its individual query node was `Fely2sHuFCs73HQ` with deterministic ID `JDC` and empty query string. The `disableImprinting` Boolean node was `1XwO8cfXL/eRO8my`, value false. The rollback node remained `MLBhwEW8Xslt2V7jc`. Browser UI showed `Features (5)` and `Parts (0)`. Full raw state is `upstream/onshape-native/.runtime/h2cad-native-car-active-sketch-top.json`.

After this ordinary UI action, the bridge guard still reported `unknown_write=false` and the H2 journal had no unresolved writes. Those facts do not verify remote feature completion: the sketch was an active editor transaction. The native implementation owner received the exact bindings for a reviewed typed continuation. The preexisting custom-feature car remained untouched.
