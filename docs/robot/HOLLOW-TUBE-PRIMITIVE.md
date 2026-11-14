# Hollow square-tube modeling primitive

`fixtures/robot/hollow_square_tube.fs` is an editable-source capability fixture:
20 x 20 mm outside, 2 mm walls, 220 mm long. It is **not genuine 2020 T-slot
extrusion**, has no slot-nut interface, and does not replace the HFS5-2020
components or section properties specified in DESIGN.md. No material or load
rating is assigned. The robot's mechanical selection and calculations remain
unchanged.

The source uses eight currently supported operations: three literal length
variables, a Top-offset plane, an outside rectangle and NEW extrusion, then an
inside rectangle and explicit-body REMOVE extrusion. Length remains symbolic in
both extrusions; outside size and wall thickness remain symbolic in the bore
sketch. Required parameter domain: `0 < wallThickness < outerSize / 2`, positive
outside size, and `0 < tubeLength <= 1000 mm`. Restage and locally validate after
changing source values.

Run `.venv/Scripts/python.exe scripts/validate_hollow_tube.py` to regenerate
`artifacts/robot/hollow-tube-local-validation.json`. OpenCascade verifies one
valid solid, analytical volume **31,680 mm3**, and bounds
`[-10,-10,0] -> [10,10,220] mm`. Point classification checks an open bore at both
ends and midspan, and material in each of the four walls. Tests additionally
verify 160 mm length and 3 mm wall variants. Native source-plan validation passes;
this fixture has **not been pushed to or independently verified in Onshape**.

No runtime extension is needed for this square tube. FSGen already has
`skPolyline`, but the native source writer accepts one four-line rectangle or
circle-only sketches, not a general T-slot contour. A genuine manufacturer-derived
T-slot section would require a reviewed contour/constraint mapping, closed-profile
and inner-loop handling, and active native solver proof before Commit. That is a
separate core-writer extension, not an assumption that a hollow tube or a square
bar is equivalent to the selected extrusion.
