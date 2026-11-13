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
