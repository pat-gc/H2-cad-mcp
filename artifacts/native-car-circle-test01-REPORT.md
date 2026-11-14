# Native car circle and variable dependency sample, 2026-11-14

Normal signed-in Onshape Browser UI in the isolated `Native Car Variables Test 01` Part Studio (`4e078dec822b4e509616b1cb` / `af0627de07264acf086e646a` / `eb0d7b23baa21737e89c0464`). This was an ordinary editor lifecycle sample for the native writer, **not** automated car creation. Existing variable `FO9H6xKSYi7mymK_0` and offset planes `F6FT8cvyG3nShVG_0` / `Fj8ALfHkHvRI9Rk_0` were preserved.

## Source references and sketch entity

The ordinary Sketch toolbar `div.tool[command-id="newSketch"]` allocated sketch `FBpkwTrs1JtHnh3_0`, tree node `M8SVt+1L4xWnjjblq`. Clicking saved Plane 1 bound `sketchPlane` to one individual query with deterministic ID `JFC`. The ordinary center point circle tool `div.tool[command-id="CIRCLE_CENTER_RADIUS"]` and two canvas clicks created one `bsedit.GBTMSketchCurve` entity `0S4BahFP39LE`, node `M2gbMJGb/tktrt9SS`, center point ID `0S4BahFP39LE.center`, geometry type `bsedit.GBTCurveGeometryCircle`. Initial seed geometry center `(0.0467491187, 0.0151656372)` m, radius `0.0136351585` m, `xDir=1`, `yDir=0`, `clockwise=false`.

Normal Dimension on the circle created constraint `blLktPwQhmgY`, type **25**, `localFirst=0S4BahFP39LE`, `length.expression='2*#wheelRadius'`, stored length value `28` mm. The solved circle seed radius became `0.014` m.

Normal Dimension between the circle center and canvas origin point produced Onshape's `A dimension cannot be created between these items` alert in both selection orders. Point-to-axis dimensions succeeded:

- X distance constraint `3vvwUGmULn4H`, type **12**, `localSecond=0S4BahFP39LE.center`, `externalFirst` individual query with empty deterministic IDs in saved definition, `direction=MINIMUM`, `halfSpace0=LEFT`, `length=65 mm`.
- Y distance constraint `CXdO3QjHajQj`, type **12**, same local center, `externalFirst` query with empty deterministic IDs, `direction=MINIMUM`, `halfSpace0=RIGHT`, `length=15 mm`.

Saved seed circle center is exactly `(0.065, 0.015)` m, radius `0.014` m, with the three constraints and unchanged plane query. The supported active `ui.sketch.GBTUiSketchGetConstraintGraphCall` resolved the external axis references to `JEC` and `JCC`; all three constraints had `(status, displayStatus)=(4,1)`, `worstSolveStatus=1`, and no sketch error (`statusEnum=0`). This is direct active solver evidence. Saved studio had four user features, zero parts, and no active edit.

## Dependent variable edit

Ordinary edit of the same `wheelRadius` feature **14 → 16 → 14 mm** changed the reopened sketch's visible diameter **Ø28 → Ø32 → Ø28**, with X/Y dimensions 65/15 unchanged. At 16 mm, the supported active solver graph gave center anchor X `0.065` m and circle reference anchor X `0.049` m: evaluated radius `0.016` m. At 14 mm, those anchors were `0.065` and `0.051` m: evaluated radius `0.014` m. Both graph reads had no sketch error.

The serialized saved sketch definition retained its original circle seed radius `0.014` m and stored diameter constraint value `28` while the variable was 16; its expression `2*#wheelRadius` remained intact. **Stored definition values must not be treated as evaluated geometry.** The normal editor and active solver graph independently confirmed regeneration. Final saved idle revision `1ff66ebd8a168fec3fa5ae8b`: variable 14 mm, sketch definition byte-equal to its first saved state, all feature/node identities preserved, Parts 0, journal unresolved 0 and guard false.

Screenshots: [active dimensions](native-car-circle-active-dimensions.jpg), [variable 16 / diameter 32](native-car-circle-variable16-diameter32.jpg), [restored diameter 28](native-car-circle-restored-diameter28.jpg). Private readbacks: `upstream/onshape-native/.runtime/car-circle-sketch-{empty-plane1,drawn,diameter-expression,diameter-x65,fully-dimensioned-active,constraint-graph-active,saved-14mm,saved-radius16-variable16,active-variable16,graph-variable16,restored-variable14}.json`.
