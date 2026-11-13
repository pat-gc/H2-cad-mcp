# Approved car push: current status

**Status: blocked before Onshape mutation.** On 2026-11-13, the available Edge session opened `https://cad.onshape.com/documents` and Onshape redirected to `https://cad.onshape.com/signin`. The page shows an empty sign-in field and disabled Continue button. No account credentials were acquired or entered. An older unrelated Onshape tab rendered blank. No document, Feature Studio, Part Studio, or feature was created or changed.

## Supported path prepared

The pinned FSGen `paste_export` converted the accepted [`basic_car.fs`](basic_car.fs) into [Onshape Feature Studio source](onshape-custom-feature.fs). The export declares one `H2 Minimal Car` custom feature with seven editable length parameters: length, width, body height, wheelbase, wheel radius, wheel thickness, and axle radius. Its geometry uses FeatureScript sketches and `opExtrude` calls; this is actual Feature Studio source, not the FSGen input dialect.

The pinned FS-Lite engine evaluated the generated custom feature locally and reported eight solids and 525,414.5098 mm³, matching the accepted local model exactly. See [custom-feature-local-check.json](custom-feature-local-check.json). This is still **offline verification**, not proof of Onshape compilation or regeneration.

After the user signs in to Onshape, the next live steps are to create a clearly named isolated car document (or a new Part Studio and Feature Studio in the authorized disposable document), paste the generated FeatureScript into the Feature Studio, resolve any live compiler diagnostics, add the custom feature in the separate Part Studio, and verify eight regenerated parts, dimensions, and a reversible `bodyHeight` edit ending at 37 mm. Capture an actual Onshape screenshot and record document/workspace/element IDs.

**Editability class:** this route creates one editable custom feature with seven dialog parameters. It does **not** create the 22 separate native variables, planes, sketches, and extrusions from the simulated plan. `NativeBackend.apply()` still rejects generic creation and advertises no supported kinds; that route remains unimplemented. No REST or STEP fallback has been used.
