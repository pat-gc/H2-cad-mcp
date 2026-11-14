# Native car plane samples, 2026-11-14

Test document: `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`, isolated Part Studio `eb0d7b23baa21737e89c0464` (`Native Car Variables Test 01`). Normal signed-in Onshape Browser UI created and edited the samples. The existing `wheelRadius = 14 mm` variable `FO9H6xKSYi7mymK_0` was preserved. This is lifecycle evidence for the native writer, not source-driven car creation.

## Top offset

Ordinary Plane tool allocated feature `F6FT8cvyG3nShVG_0`, tree node `M2GBKdQ+vb3YCmPNm`, type `cPlane`. Clicking the observed default Top row bound `entities` to one `GBTMIndividualQuery` with deterministic ID `JDC`. Supported read-only `ui.GBTUiGetQueryDataCall` resolved it to `featureId=Top`, `fullOperationId=Top.planeOp`, `selectionName=Face`, `entityType=2`, `status=0`, no error. The saved typed definition has `cplaneType=OFFSET`, `offset.value=20`, `offset.expression='20 mm'`, `offset.units='millimeter'`, and `oppositeDirection=false`, `flipNormal=false`, `flipAlignment=false`.

Normal UI edited the saved offset **20 → 28 → 20 mm**. The feature and node IDs stayed the same, the studio returned to saved idle, and the final feature definition was byte-equal to the initial saved 20 mm definition. Revisions: initial `721a541b9a9ed37195338fdc`, 28 mm `35b65f5dd2482046e006ab82`, restored `31c2c0cd83df89db5039baf2`.

## Right opposite offset

Ordinary Plane tool allocated feature `Fj8ALfHkHvRI9Rk_0`, node `M61dl6HRgdmwVXBX9`, type `cPlane`. Clicking the observed Right row bound `entities` to one query `JEC`; supported query data resolved `featureId=Right`, `fullOperationId=Right.planeOp`, `selectionName=Face`, `entityType=2`, `status=0`, no error.

Entering literal `-55 mm` made Onshape's input invalid and disabled Save. Its tooltip stated the allowed offset range is **0 to 500000**. The ordinary direction button has DOM selector `[data-parameter-id="oppositeDirection"] [data-automation="flip-direction-opposite"]` and tooltip `Opposite direction`. Setting the valid magnitude `55 mm` and clicking that button produced saved `offset.value=55`, `offset.expression='55 mm'`, `oppositeDirection=true`, `flipNormal=false`, `flipAlignment=false`. This is the observed representation for the negative side in this sample; the editor UI also showed the plane on the opposite side. Saved revision `988acf95ebdbf4cb72a1ce6d`, saved idle, zero parts. The variable and Top plane feature identities remained intact.

The query data proves reference-plane identity and status. It does **not** expose a numeric spatial frame, and no independent frame/coordinate measurement was made. A source expression such as `-#width/2-#wheelThickness` will need a semantics-preserving magnitude/direction mapping; this sample does not prove that expression path.

Evidence: [Top saved screenshot](native-car-plane-top20-saved.jpg), [Right active direction screenshot](native-car-plane-right-reversed55-active.jpg), [saved overview](native-car-planes-saved.jpg). Private raw bridge readbacks: `upstream/onshape-native/.runtime/car-plane-active-default.json`, `car-plane-active-top-20mm.json`, `car-plane-saved-top-20mm.json`, `car-plane-saved-top-28mm.json`, `car-plane-restored-top-20mm.json`, `car-plane-active-right-minus55mm.json`, `car-plane-active-right-plus55mm.json`, `car-plane-active-right-reversed55mm.json`, `car-plane-saved-right-reversed55mm.json`, and `car-plane-{top,right}-query-data.json`.
