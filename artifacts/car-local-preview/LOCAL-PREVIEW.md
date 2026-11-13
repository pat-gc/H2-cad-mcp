# LOCAL PREVIEW / NOT PUSHED

This is an offline concept car built from [`basic_car.fs`](basic_car.fs) by the pinned FSGen tracer and local OpenCascade builder. The [large isometric screenshot](car-isometric-local-model.png) and [four-view screenshot](car-actual-local-model.png) depict the actual locally built solids. They are **not Onshape screenshots**.

## Model to review

The model contains eight separate solid bodies in one conceptual Part Studio: one rectangular chassis, one simple rectangular body, two plain axles, and four cylindrical wheels. It has no assembly mates and makes no roadgoing engineering claim. Main source parameters are length 180 mm, chassis width 90 mm, body height 37 mm, wheelbase 130 mm, wheel radius 14 mm, wheel thickness 12 mm, and axle radius 4 mm. Overall OpenCascade bounding size is **114 × 180 × 64 mm** (X × Y × Z), with bounds X −57 to +57, Y −90 to +90, and Z +1 to +65 mm.

Local build: **passed**. Eight solids; volume 525,414.5098 mm³; area 85,598.5828 mm²; no warnings; no partial feature build. Changing `bodyHeight` from 37 to 42 mm locally retains eight bodies and adds exactly 48,000 mm³. This verifies a local parameter effect, not native remote editability. See [validation-report.json](validation-report.json).

## Simulated empty-studio create plan

The [semantic desired graph](semantic-desired.json) compiles to 22 native feature definitions. Against an **explicitly simulated empty Part Studio** with placeholder IDs and revision, the [dry-run plan](simulated-empty-create-plan.json) contains 22 ordered `create` operations and zero semantic conflicts:

| Order | Intended features | Count |
| --- | --- | ---: |
| 1 | Variables: `length`, `width`, `bodyHeight`, `wheelbase`, `wheelRadius`, `wheelThickness`, `axleRadius` | 7 |
| 2 | Offset planes: chassis, body, axle left, wheel left, wheel right | 5 |
| 3 | Sketches: chassis rectangle, body rectangle, two axle circles, two left wheel circles, two right wheel circles | 5 |
| 4 | Extrusions: chassis, body, two axles, two left wheels, two right wheels | 5 |

The JSON records each exact logical operation, dependency, and FSGen native template. **The simulated baseline is not a fresh remote read and this plan is not executable with the current native backend.** No live document, workspace, or element has been selected or changed.

## Push gate and precise blocker

The current `NativeBackend.apply()` raises `Unsupported` for generic sketch/extrusion transactions. Its advertised `supported_kinds` is empty. Only a separately guarded existing extrusion-depth edit is implemented for a disposable Part Studio; that cannot create this car. FSGen's compiled feature JSON is a local template, not a browser RPC payload. No developer REST fallback is authorized by this path.

To make this exact 22-operation plan executable through the intended native path, the adapter must implement and verify variable creation, offset plane creation, rectangle/circle sketch creation, extrusion creation with live references, runtime allocation/binding of native IDs and plane/sketch selections, durable per-operation intent/reconciliation, current revision preflight/guard, and complete remote readback of feature definitions, dependencies, regeneration status, and solid geometry. The lack of atomic server revision enforcement also limits any future existing-document collaborative edit.

Remote regeneration: **not run**. Native editability in Onshape: **not run**. User review of these local images precedes any Onshape mutation.

## Reproduce

From this worktree, with the pinned `upstream/onshape-fsgen/.venv/Scripts/python.exe` and `PYTHONPATH=src`, run `python scripts/car_local_preview.py` to regenerate all local artifacts. Run `python -m pytest tests/test_car_fixture.py -q` for the fixture and parameter edit checks.
