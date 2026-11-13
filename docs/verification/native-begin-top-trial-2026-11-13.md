# Native begin-Top trial — 2026-11-13

Target: H2 CAD Test Project, isolated temporary Part Studio `4e078dec822b4e509616b1cb/af0627de07264acf086e646a/9a062f0eef8bb961f8c84f8e`, tester-owned Edge tab `941740749`. The existing eight-solid car Part Studio, Feature Studio, and Assembly were not changed.

## Clean start and loaded code

The previously observed manual Fix sample was the sole active feature `FxUejuiFCPljFf4_0` at revision `a02e55af652303a531f63d9a`, with zero parts. Its ordinary Sketch dialog Cancel removed it; independent native state returned the exact default empty tree, no active edit, zero sketches/parts, revision `d9f69655d46807c4f72168e7`. The prior failed population journal had no unresolved intent and the persistent guard's `unknown_write` was false before the new command.

Reviewed Native patches 14 and 15 were staged with `scripts/bootstrap.py --sources-only`; the clean Native checkout tree was `f1798b9733b115a2e850676c6465711155e0e73f`. The paired Python broker was restarted with the same pairing and pinned journal. Official own-extension self-reload returned `reconnected/new_handshake_verified`, changing worker instance from `e6ee72e2-bef4-4f46-b504-73b843acfa90` to `bcdb4ceb-1ae9-4256-ab96-25855c469cff`. Authenticated health showed `pending=0`, connected=true, the begin/populate/extrude server capabilities, and the newly required page capability `h2_native_fixed_origin_page_v1`.

## One deterministic begin attempt

One `h2cad experimental-begin-top-sketch` invocation targeted that exact empty studio/tab with the paired bridge config and pinned H2 journal. It exited 1 after about 8.5 seconds: `Top sketch initiation outcome unknown; journal operation begin-sketch-365408e635454cd792f8074acb16c06c`. No retry or source population was sent.

The immediate UI showed active red `Sketch 1`, empty Sketch plane field, and `Select a sketch plane`. Fresh native state showed one new feature `FEXx3kqSZU32rt4_0`, active edit on the same ID, zero entities and constraints, zero sketchPlane queries, zero parts, element revision `3ca62d01df8577a399e29e17`. The journal operation remained unknown, `has_unresolved=true`, and the persisted bridge guard `unknown_write=true`. Health remained connected with `pending=0`; that pending count does not establish that the page-side incomplete-edit marker is clear.

The Top row was visible and unobstructed under stable selector `div.os-list-item[feature-id="Top"][feature-type="defaultPlane"]`; its center hit the child `Top` text, while the feature dialog occupied a separate area. The reviewed page command uses `HTMLElement.click()` on that row, which appears not to have completed plane binding. This is an inference from the subsequent ordinary click and should be confirmed by a repaired automatic command.

## One ordinary Top selection for recovery

After manager authorization, one normal browser locator click on that exact visible Top row selected the plane for the **already active** CLI-created blank sketch. The first UI frame highlighted Top; the next displayed `Top plane` in the Sketch plane field and enabled the green check. This was manual recovery, not automatic begin acceptance.

Independent state after the click retained feature/edit ID `FEXx3kqSZU32rt4_0`, four default features and the same unrelated model content, zero entities/constraints/parts, with exactly one `sketchPlane` individual query whose deterministic ID is `JDC`. Element revision became `067dc0664629241c05686f7b`. The dialog token is `.feature-dialog li.os-param-selection-list-entry > span.os-selection-item-line[data-automation-tooltip-text="Top plane"] > span.os-param-query-list-entry-text`, visible text `Top plane`. Read-only `ui.GBTUiGetQueryDataCall` on the **live query object** returned one `display.GBTQueryData`: `featureId=Top`, `selectionName=Face`, `fullOperationId=Top.planeOp`, deterministic ID `JDC`, no error entity.

Read-only `editor_tab(status)` returned ready=true, stale=false, reason=connected, busy=true due active sketch, and the same element revision. It did not expose `incomplete_edit`, `rpc_pending`, or `motion_active`. The journal and guard remain unknown/blocked, pending a reviewed evidence-based begin reconciliation and page-side lifecycle check. No manual journal edit, guard clearing, source population, or extrusion occurred. The recovered blank Top sketch is left active in the tester-owned tab for inspection.

Raw exact states, status, and query response are in `artifacts/native-begin-top-evidence/`. This trial demonstrates a gap in automatic Top selection; it does not establish source-driven sketch or car creation.

## Queued future requirement

Root should create a separate Astra agent named `cadder` **only after** repeatable native source-driven full generation, editability, end-to-end validation, and the existing car's native rebuild are achieved. It must not serve as an adapter debugging role. Its queued brief is: “Design a buildable, professional 4-axis robotic arm, using native, human-editable sketches and features: base rotation, vertical rail lift replacing shoulder pitch, elbow rotation, and wrist rotation. Use NEMA 17 motors, belts and pulleys, 2020 aluminum extrusions, and suitable rails and bearings. Achieve 400 mm reach and 400 mm side-to-side coverage while carrying a 200 g payload plus its own weight. Plan the geometry before modeling and calculate loads and drive requirements to verify feasibility.” No robotics modeling or calculations started in this trial.
