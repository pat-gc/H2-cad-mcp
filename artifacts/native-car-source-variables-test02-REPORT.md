# Source-driven native variables, live trial 2026-11-14

Authorized H2 Test Project document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`, isolated `Native Car Source Variables Test 02` Part Studio `9b8155a2839e649138dae95f`, Browser tab `941741361`. All other studios were preserved. Normal Onshape UI allocated blank features; reviewed patch 35 typed writer populated them from [basic_car.fs](../../fixtures/car/basic_car.fs), with patch 36 correcting saved-variable page-marker retirement. This trial **proves seven source-ordered native variable definitions and one ordinary same-ID edit**, not downstream car geometry or the full 22-feature car.

Before the first write, source SHA-256 was `C7C397354394C91F5648667BFF9D48A63757105C331DB83E283B469D69245EE8`. Local `h2cad validate` passed with no warnings: eight OpenCascade solids, bbox `[-57,-90,1]..[57,90,65]` mm (114 × 180 × 64 mm), volume `525414.5098` mm³; remote/native geometry was not tested by that command. Reviewed Native patch stack 35 tree `c1adbfd1e16178813c63a99181756d308f2791b8` was staged; paired broker and official extension reconnect yielded worker instance `0c001239-09b3-4ba8-b457-f2f4ab5856b7`, with variable writer page/server capabilities. The private config changed only its create target; pairing and journal/guard bytes were preserved across broker restart.

The new studio baseline was connected, saved idle, default tree/Parts 0, element revision `2aac1dfc4f0843c09dcac4a7`, journal unresolved 0 and guard false. Ordinary Variable tool `div.tool[command-id="assignVariable"]` allocated blank `ASSIGNED/LENGTH`, empty name, `0 mm`, feature `FvIo7QnbIH9Twm5_0`, node `MRHraxBurBAmxLqP5`, revision `fbcb7953a6b0738f9e4c6174`.

One `experimental-populate-variable fixtures/car/basic_car.fs --logical-id '#length'` succeeded: operation `variable-c8defd9fb08b4961849b84f5b7a176f3`, saved revision `91f68a2872bc117b355a8382`, same feature/node IDs. Independent tree read was idle with one `assignVariable`, `name=length`, `mode=ASSIGNED`, `variableType=LENGTH`, `lengthValue=value=180`, expressions `180 mm`, Parts 0. Onshape showed `#length = 180 mm`. Journal state `observed`, unresolved 0, guard false. The command explicitly reported regeneration and UI editability **unverified**. [Saved result screenshot](native-car-source-length-first-saved.jpg).

The next ordinary Variable tool allocated blank width draft `FNfswgz3O1s4Mxl_0`, empty name/0 mm, preserving `#length`. The `#width` CLI attempt with the prior observed operation ID was **pre-dispatch rejected** as `Exact fresh variable editor unavailable.` New operation `variable-99515a0254ca4e5a95070e0a6bee4c33` is `rejected`; unresolved 0, guard false. Read-only `editor_tab status` was `ready=true`, `pending_rpc=false`, `motion=false`, `drag=false`, `feature_edit=true` for the expected blank draft, and `incomplete_feature_edit=true` from a page marker `stage=await-saved-readback`, `op_id=variable-c8defd9fb08b4961849b84f5b7a176f3` (the **previous observed** length operation). No replay or manual marker clearing occurred. [Historical blocked draft screenshot](native-car-source-width-blocked-draft.jpg).

Private exact readbacks are under `upstream/onshape-native/.runtime/car-source-variables-test02-empty-baseline.json`, `car-source-variable-length-{blank-draft,saved}.json`, and `car-source-variable-width-predispatch-block.json`.

**Bounded recovery diagnostic:** after manager review, ordinary Cancel removed only the known blank rejected width draft. The native tree returned to sole saved `#length`, idle, exactly its prior revision `91f68a2872bc117b355a8382`; journal and guard remained clear. One supported read-only `state` job with `retire_acknowledged_op_id=variable-c8defd9fb08b4961849b84f5b7a176f3` returned HTTP 200 and the same saved tree, but `editor_tab status` before/after still showed the previous page marker. After Cancel, `feature_edit=false` and only `incomplete_feature_edit=true` kept the page busy. This matches the separately reviewed page retirement predicate defect; no second retirement call or new variable draft was attempted. Private captures: `car-source-variable-width-blank-cancelled.json` and `car-source-variable-length-retirement-check.json`.

## Patch 36 recovery and all seven source variables

At sole saved `#length`, idle and clear journal, reviewed patch 36 Native tree `6b8433e7168ead94f6d765e4a5573d17f5413fdf` was staged. The paired broker restarted and official extension reload completed a new handshake (worker instance `f47706fb-4688-410d-9e5f-338f611e4e21`). One supported state retirement call for the already observed `#length` operation now removed its stale marker; all editor busy reasons were false. The saved feature and revision were unchanged. No source operation was replayed.

For each remaining variable, the normal toolbar allocated a fresh empty `ASSIGNED/LENGTH` draft. One CLI call populated it using the exact source and all preceding **observed** variable operation IDs in source order. After every save, independent tree read showed the intended expression, idle editor, page marker absent, operation observed, journal unresolved zero and guard false.

| Source variable | Saved value | Native feature ID | Journal operation ID |
| --- | ---: | --- | --- |
| `#length` | 180 mm | `FvIo7QnbIH9Twm5_0` | `variable-c8defd9fb08b4961849b84f5b7a176f3` |
| `#width` | 90 mm | `FObM8qWn7mC42E4_0` | `variable-997182ef860d4e3faafbe035d420ef5c` |
| `#bodyHeight` | 37 mm | `FZUu5M40O7pn3U4_0` | `variable-30bbe689a2f142129df2574335f6626d` |
| `#wheelbase` | 130 mm | `FEEfR9mxGBHcU7G_0` | `variable-8f8e6f7bee654598b399022d4ba9e2cc` |
| `#wheelRadius` | 14 mm | `FKG42Nv7IZttnca_0` | `variable-d3f46969b69e452c8b38167516fb3903` |
| `#wheelThickness` | 12 mm | `FZPoOHSrcO2SZbb_0` | `variable-03719a55a5b5467f8b1df221a59d6795` |
| `#axleRadius` | 4 mm | `FFG2XwpICQ9c21X_0` | `variable-6cfc85720f704709882fc4e3b2f3e45b` |

Seven saved `assignVariable` features are in that exact order, all `mode=ASSIGNED`, `variableType=LENGTH`, with `lengthValue` and duplicate `value` quantities matching each source expression. Final source population revision `a09be4b9ad499a8f298263d0`, Parts 0. [Actual seven-variable screenshot](native-car-source-seven-variables.jpg).

The source-created `#wheelRadius` feature was then opened through the normal Onshape tree, edited **14 → 16 → 14 mm**, and saved after each value. At 16 mm, native readback showed the same feature ID and expression `16 mm`, with the six other variables unchanged (revision `c34be06ba8451007ed6b9297`). Final restored revision `edcafef0d9c9834489776105`: the entire seven-feature definition list was byte-equal to the pre-edit saved list, all IDs preserved, idle/marker absent, journal unresolved 0, guard false. [Restored screenshot](native-car-source-seven-variables-restored.jpg). This proves human editability of the source-written variable; no dependent geometry existed in this studio, so its regeneration effect was not tested here.

Private exact snapshots: `upstream/onshape-native/.runtime/car-source-seven-variables-{saved,wheelradius16,restored-edit}.json`.
