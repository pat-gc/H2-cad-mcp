# Source sketch editability and Extrude region binding

**Target:** `H2 CAD Test Project`, document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`, isolated temporary Part Studio `9a062f0eef8bb961f8c84f8e`, tester tab `941740752`. The main car Part Studio and Feature Studio were not changed.

## Reconciliation and sketch edits

Patch 18 was staged by the reviewed source-only bootstrap; the paired broker was restarted with its existing config and journal. `experimental-reconcile-completed-source-sketch sketch-53e56d44e3024215bae918590a343ea4` returned `observed_manual_source_completion` for source sketch `FDwrlDX9Oobgytk_0`. The journal was observed with no unresolved operation and persistent `unknown_write=false`. This is **manual completion of a source-generated sketch**, not proof that the population command autonomously saved it.

The saved sketch was reopened through Onshape's ordinary feature tree. The live `ui.sketch.GBTUiSketchGetConstraintGraphCall` returned 11 constraints and 12 references, `worstSolveStatus=1`, no sketch error, all 11 constraints `(status, displayStatus)=(4,1)`, and internal Fix constraint `box.fixedOrigin` of type 16 anchored `box.bottom.start` at `(0,0,0)`. This is direct active-editor solver evidence.

The ordinary dimension UI allowed width `40 → 45 → 40 mm` and height `20 → 25 → 20 mm`. Each altered state retained four source line IDs and 11 constraints. The fixed point remained at `(0,0,0)`. The final active definition was 40×20 mm; the green Sketch dialog checkmark `.feature-dialog .ns-dialog-button-ok` saved it and closed the editor. The saved element revision stayed `fa22a1a00256fe722b39fc2d`, the same as immediately before that Save, and `editingFeatureId` became null. No extra feature was created. The restored active graph again showed 11 constraints, 12 references, no sketch error, and fixed origin `(0,0,0)`.

## Ordinary Extrude setup, uncommitted

The toolbar `div.tool[command-id="extrude"]` created an active `Extrude 1` feature `FjpogXiV3yGx0YH_0`. A single ordinary click in the sole filled source rectangle selected `Face of Sketch 1`. The native definition has `domain=MODEL`, `bodyType=SOLID`, `operationType=NEW`, `endBound=BLIND`, and initial `depth=25 mm`. Its `entities` parameter contains one live `bsedit.GBTMIndividualQuery`, deterministic ID `JGC`.

The supported read-only `ui.GBTUiGetQueryDataCall` on that **live** query returned one `display.GBTQueryData`: `featureId=FDwrlDX9Oobgytk_0`, `selectionName=Face`, `evaluationDetails.fullOperationId=FDwrlDX9Oobgytk_0.imprint`, `entityType=2`, `status=0`, `hasErrorEntity=false`. This binds the selected profile to the source sketch. The active element revision was `0f4a6a1fe7e95da1409fd169`. Onshape displayed a green Extrude checkmark and preview; the feature remains **active and uncommitted** in tester tab `941740752` for the reviewed source-driven extrusion candidate. Preview is not saved-solid acceptance.

The browser screenshots observed the 40×20 filled sketch with origin at its lower-left corner and then `Face of Sketch 1` selected in the Extrude dialog. CUA did not provide a local screenshot file in this pass; the live tab is marked for handoff. The JSON files beside this report are exact read-only state and graph captures. Automated begin, autonomous sketch Save, source-driven extrusion, and the full eight-part native car remain separate acceptance gates.
