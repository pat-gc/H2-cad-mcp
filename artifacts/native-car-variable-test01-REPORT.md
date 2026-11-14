# Native `wheelRadius` variable sample — 2026-11-14

**Target:** isolated `Native Car Variables Test 01` Part Studio in `H2 CAD Test Project`, document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`, element `eb0d7b23baa21737e89c0464`, official Edge Browser tab `941741361`. Normal Onshape UI created and named the studio. Its baseline was connected and idle at revision `0bf611d8221ceb1aa298e189`, with only a rollback child and default geometry; no parts. The paired bridge's private target binding was updated to this exact studio while retaining the same token and pinned journal. No existing plate, car or unrelated feature was changed.

The ordinary **Search tools → Variable** action allocated feature `FO9H6xKSYi7mymK_0`, node `MQL75t8jiJyPM54Bt`, before input at revision `3e660f852d1689678204a648`. Its `featureType` is `assignVariable`. The UI default was **Assigned / Length / 0 mm**. Setting name `wheelRadius` and value `14 mm` produced active revision `69e2f0327220773e30278593` and a saved idle definition with one variable before the rollback marker. The saved definition includes:

| Parameter | Native type | Value | Node ID |
| --- | --- | --- | --- |
| `mode` | `GBTMParameterEnum`, `VariableMode` | `ASSIGNED` | `PNbq7qLDMg3ghbRu` |
| `variableType` | `GBTMParameterEnum`, `VariableType` | `LENGTH` | `WcCnh/SnUeaDf5WU` |
| `name` | `GBTMParameterString` | `wheelRadius` | `rgKkrdmwMwLyNnXc` |
| `lengthValue` | `GBTMParameterQuantity` | `14`, expression `14 mm`, units `millimeter` | `rqXT0InfK/364fJF` |
| `value` | `GBTMParameterQuantity` | `14`, expression `14 mm`, units `millimeter` | `EqujtKWq1KgCg1KD` |

The live serializer's read-only `native_schema` returned class ID `987` for `ui.GBTUiCreateVariable`, whose defaults contain `editDescription`, `elementId`, `messageId`, and `newFeature: GBTMFeature`. It returned class IDs `145`, `147`, `149` for enum, quantity and string parameter types. These are schema shapes, **not** proof that direct `GBTUiCreateVariable` submission works. The normal UI allocated the feature and parameter IDs. No explicit source dependency was present in this literal variable sample (`sourceParseTreeNodes` empty). Initial insertion was the sole user feature immediately before rollback.

The ordinary UI reopened and saved the **same** variable at **14 → 16 → 14 mm**. Revisions at 16 and restored 14 were `b8e3743ebbccaed0541257c6` and `c86036d15296b3a83e778564`. The feature/node and parameter node IDs stayed fixed; the final definition was byte-identical to the first saved 14 mm definition. The final editor is connected and idle, journal unresolved count zero, guard false, Parts (0).

Screenshots: [active at 14 mm](native-car-variable-test01-active-14mm.jpg), [saved 14 mm](native-car-variable-test01-saved-14mm.jpg), [saved 16 mm](native-car-variable-test01-saved-16mm.jpg), [restored 14 mm](native-car-variable-test01-restored-14mm.jpg). Private raw baseline, active, saved and edited states are `upstream/onshape-native/.runtime/car-variable-test01-*.json`; live serializer defaults are `.runtime/car-variable-schema-*.json` in the main checkout.

**Limit:** this is one manually initiated native variable lifecycle sample to implement a deterministic source-driven writer. It does not prove automated creation of all seven car variables, dependent expressions or any car solid.
