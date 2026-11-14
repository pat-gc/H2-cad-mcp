# Native car origin circle and first source plane trial — 2026-11-14

## Local point and signed circle constraints

In H2 CAD Test Project, schema sample Part Studio `eb0d7b23baa21737e89c0464`, normal Browser UI saved Sketch 2 `FcXyeKJXSbVjLuD_0` on Plane 1. The saved definition has two entities: a local user point `uHPqukDYyUe7` at (0, 0), and circle `vXzowy40LLWZ` centered at (-65, +15) mm with 14 mm radius. The point's serialized `isConstruction` is **false** despite the initial construction toggle. The point is fixed by constraint `JKRxA9EPVKyg` (type 16) and also has Onshape's automatic origin position snap `uHPqukDYyUe7.positionSnap0` (type 1) whose external query has empty deterministic IDs. Fix alone has not been tested without the snap.

Diameter constraint `WezxA57nORSX` is type 25, localFirst `vXzowy40LLWZ`, length expression `2*#wheelRadius`, value 28 mm. The two type 12 constraints both reference `localFirst=vXzowy40LLWZ.center`, `localSecond=uHPqukDYyUe7`:

| Constraint | Direction | Length | Alignment | Center result |
| --- | --- | ---: | --- | --- |
| `588EZJbgrXLB` | VERTICAL | 15 mm | ANTI_ALIGNED | +15 mm Y |
| `oc5jElje2xcS` | HORIZONTAL | 65 mm | ALIGNED | -65 mm X |

The active supported constraint graph reported all five constraints at status 4, `worstSolveStatus=1`, `sketchError.statusEnum=0`; the local point anchor was (0,0) and circle center (-0.065,+0.015,0) m. Browser Save produced saved idle state with the same two entities and five constraints at element revision `2d307f32e3ae5734432972a2`; Parts 0. [Actual screenshot](native-car-origin-circle-sample.jpg). Private exact raw states and graph are in `upstream/onshape-native/.runtime/car-local-anchor-complete-{active,graph,saved}.json`.

## First source plane, bounded failure

Patch 37 was staged through pinned bootstrap; paired broker restarted with private config SHA256 `8dd8ab0fb3424cd4619c91a604c56af2f4511fd10604a155cc90dd0e232a9954`, journal preserved. Official extension reload yielded `new_handshake_verified`, instance `a61b867f-a129-4cdb-97d0-76785f2cbf8e`; server and page `h2_native_plane_populate_*_v1` capabilities were present. The exact source-variable studio `9b8155a2839e649138dae95f` was connected and saved idle at revision `edcafef0d9c9834489776105` with the seven source variables and Parts 0; journal unresolved 0, reload guard false.

Normal Browser UI allocated Plane 1 draft `FrioRuovl3ZRMGz_0`, node `MjYB89cFDjanjwluU`, `cPlane`, bound visibly to Top, `OFFSET` 25 mm. The active prewrite revision was `7b1da25eab3c59d17fd3cee1`; its sole `entities` query ID `JDC` resolved by supported `ui.GBTUiGetQueryDataCall` to `featureId=Top`, `fullOperationId=Top.planeOp`, `selectionName=Face`, `entityType=2`, status 0, no error.

One `experimental-populate-plane fixtures/car/basic_car.fs --logical-id 'Chassis height'` invocation returned exit 1 / **unknown**, operation `plane-1ba6263fe9ab4acd9abd4f5159da9f9e`. The journal error is exactly `Browser-mode adapter permits only native editor jobs`, with no receipt or observation. Guard remained false and broker pending 0. One read-only fresh state still showed the same active draft, seven variables, default 25 mm offset, and identical element revision `7b1da25eab3c59d17fd3cee1`. This suggests a local route rejection before model dispatch; that stage has not yet been established through reviewed code-level recovery. No retry, cancel, or reload followed. [Actual unchanged draft screenshot](native-car-plane37-pre-dispatch-draft.jpg). Private exact baseline, binding, query and after-state files are under `upstream/onshape-native/.runtime/car-plane37-*`.

The first source plane has **not** been saved or validated. The prior seven source variables remain intact. Root and plane worker received the exact failure for a scoped route and journal repair.
