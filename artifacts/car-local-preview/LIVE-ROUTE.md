# Live Onshape result: H2 CAD Test Project

**Result: created and visually verified on 2026-11-13.** The user signed in and authorized a new dedicated test document. No prior disposable control document or unrelated document was changed.

- Document: [H2 CAD Test Project](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/45730d1931712e2c548fae00)
- Document ID: `4e078dec822b4e509616b1cb`
- Workspace ID: `af0627de07264acf086e646a`
- Part Studio element ID: `45730d1931712e2c548fae00`
- [Feature Studio](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/39a2e2afc5bc43eea167e938) element ID: `39a2e2afc5bc43eea167e938`

## Creation route and evidence

The pinned FSGen `paste_export` converted the accepted [`basic_car.fs`](basic_car.fs) into [Onshape Feature Studio source](onshape-custom-feature.fs). The generated source declares one `H2 Minimal Car` custom feature with seven editable length parameters and uses FeatureScript sketches and `opExtrude` calls. The pinned FS-Lite engine evaluated that generated custom feature locally and reported eight solids and 525,414.5098 mm³, exactly matching the accepted local model; see [custom-feature-local-check.json](custom-feature-local-check.json).

Through the ordinary authenticated Onshape UI, a new document named `H2 CAD Test Project` was created with a dedicated Feature Studio and Part Studio. The generated FeatureScript was pasted and committed in the Feature Studio. Onshape made `H2 Minimal Car` available as a feature from the current workspace. Adding it to the empty Part Studio produced `Parts (8)` with one saved `H2 Minimal Car 1` feature. The 3D viewport showed the chassis, raised body, axles, and four wheels. Screenshots of the actual Onshape viewport and feature dialog were captured in the browser session; the finished Part Studio tab was left open as the deliverable.

The Onshape feature dialog showed these seven values: length 180 mm, width 90 mm, body height 37 mm, wheelbase 130 mm, wheel radius 14 mm, wheel thickness 12 mm, and axle radius 4 mm. To test editability, body height was saved at 42 mm; the viewport regenerated and still showed `Parts (8)`. It was then saved back to 37 mm. Reopening the dialog confirmed 37 mm and the final Part Studio still showed `Parts (8)`.

## Validation boundary

Onshape compilation, feature insertion, eight-part regeneration, and a reversible saved parameter edit were observed through the UI. The approved overall bounding size, **114 × 180 × 64 mm**, was measured by the local OpenCascade build. It was **not independently measured numerically in Onshape**. Onshape volume was also not independently measured. This route creates **one editable custom feature**, not the 22 separate native variables, planes, sketches, and extrusions from the simulated plan. Generic `NativeBackend.apply()` creation and an automated FSGen/bridge push remain unsupported and unverified; no REST or STEP fallback was used.
