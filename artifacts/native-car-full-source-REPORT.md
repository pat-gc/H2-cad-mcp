# Source-driven native car — live verification, 2026-11-14

The approved conceptual car in `fixtures/car/basic_car.fs` (SHA-256 `C7C397354394C91F5648667BFF9D48A63757105C331DB83E283B469D69245EE8`) is saved in the **new native source Part Studio** [H2 CAD Test Project](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/9b8155a2839e649138dae95f). It has 22 native editable definitions: seven assigned length variables, five offset planes, five sketches, and five NEW/SOLID/BLIND extrusions. The original custom-feature car and its assembly remain untouched. [Unobstructed actual Onshape view](native-car-complete-clean-view.jpg).

## Source-to-native identity map

| Source logical feature | Native feature ID | Observed source operation |
| --- | --- | --- |
| `#length` | `FvIo7QnbIH9Twm5_0` | `variable-c8defd9fb08b4961849b84f5b7a176f3` |
| `#width` | `FObM8qWn7mC42E4_0` | `variable-997182ef860d4e3faafbe035d420ef5c` |
| `#bodyHeight` | `FZUu5M40O7pn3U4_0` | `variable-30bbe689a2f142129df2574335f6626d` |
| `#wheelbase` | `FEEfR9mxGBHcU7G_0` | `variable-8f8e6f7bee654598b399022d4ba9e2cc` |
| `#wheelRadius` | `FKG42Nv7IZttnca_0` | `variable-d3f46969b69e452c8b38167516fb3903` |
| `#wheelThickness` | `FZPoOHSrcO2SZbb_0` | `variable-03719a55a5b5467f8b1df221a59d6795` |
| `#axleRadius` | `FFG2XwpICQ9c21X_0` | `variable-6cfc85720f704709882fc4e3b2f3e45b` |
| Chassis height, Top +20 mm | `FMi1WionXIlfo49_0` | `plane-76141a391b53499ca811004a70d62972` |
| Chassis sketch, 90 × 180 mm | `FdEYKeIfJvpoMtr_0` | `source-sketch-ffbc0575d93c446ebed238ea73086af6` |
| Chassis, 8 mm | `Fefkybt2kLtj3aF_0` | `extrude-dc380ff63dd34e8081e2790b2d306f94` |
| Body height, Top +28 mm | `FAu7bp3NJoRTRow_1` | `plane-fd1484cc6a23456c911dc5da5dde21eb` |
| Body sketch, 80 × 120 mm | `Fa6S2orBHAiWhV1_1` | `source-sketch-982cd45c194a4f62a13bfac6e3f1c243` |
| Body, depth `#bodyHeight` | `FcIxxzTt1h89PbG_1` | `extrude-658c4e35d9ff4bfb86b95a5f17731d83` |
| Axle left plane, Right −55 mm | `Fi4PZ6IukMEvMXS_2` | `plane-4d0a2025186a443ca12ff65d7ebfb806` |
| Axle sketch, two circles | `FpEgiNIOBxZsP3b_2` | `source-sketch-71be695d4c004a63bcf2ba5b6ac2803b` |
| Axles, 110 mm | `FehJH8zvR1SeGir_2` | `extrude-19fe2f3f6c394cf09519a5441be5f9b1` |
| Wheel left plane, `-#width / 2 - #wheelThickness` | `FFdUc4vsSvHCCTy_4` | `plane-bc91aaa441244b378425182c851d3382` |
| Left wheel sketch, two circles | `Fb22vfr7fitnybM_4` | `source-sketch-6f079eb55eb34277b6772c85390ec947` |
| Left wheels, depth `#wheelThickness` | `Ffstl9KhdNINYkY_4` | `extrude-a1a4f277e7714ec18862b6089d3bbf6f` |
| Wheel right plane, `#width / 2` | `F8Eq1Aw6yt2Id6S_6` | `plane-c753e6fc3a8a4ae28d7ea4dd5ebadbd7` |
| Right wheel sketch, two circles | `FMdwF6PbArvVmj0_6` | `source-sketch-da9f48303fe74479b8af41d7dde68147` |
| Right wheels, depth `#wheelThickness` | `FjpuLQTT1eNQXQS_6` | `extrude-070c8fbb3da84b9089f301980eb89cdb` |

Each plane used an exact, freshly observed normal UI reference and all prior observed plane operations. Each sketch used its exact source plane operation and required variable operation map. The adapter generated and solved the rectangle/circle constraints before saving; normal Browser UI allocated the blank feature. Each extrusion used its observed source sketch region, exact source depth, and NEW/SOLID/BLIND native controls. The 22 saved feature IDs remained stable through the final edit/restore. There was no manual drawing of car geometry.

## Independent model checks

| Check | Live Onshape result | Local source target |
| --- | --- | --- |
| Parts | 8, IDs `JID,JMD,JQD,JQH,JUD,JUH,JYD,JYH` | 8 solids |
| Total volume | 525,414.51 mm³, all eight selected in normal Mass Properties | 525,414.5098 mm³ |
| Total surface area | 85,598.583 mm² | 85,598.5828 mm² |
| Loaded viewer mesh bounds | min `[-57.00000003,-90.00000358,1.00000005]`, max `[57.00000003,90.00000358,64.99999762]` mm | min `[-57,-90,1]`, max `[57,90,65]` mm |
| `#wheelRadius` 14→16 mm | Same 22 features/8 parts; 534,462.297 mm³ | 534,462.2967 mm³ |
| Restored 16→14 mm | 525,414.51 mm³; all 22 source definitions exactly equal to pre-edit snapshot | 525,414.5098 mm³ |

[Initial eight-part volume](native-car-eight-parts-volume14.jpg), [16 mm wheel volume](native-car-eight-parts-volume16.jpg), [restored volume](native-car-eight-parts-volume14-restored.jpg), [full saved model](native-car-complete-clean-view.jpg).

The independent bounds came from the existing read-only `viewer_mesh` service, not the FSGen plan. It listed exactly the eight loaded part IDs and downloaded their already loaded face vertex buffers at the same displayed microversion `56e3965de03a89dd46ffe363`. Coordinates are meters in each part's local frame; every occurrence transform was identity in this Part Studio. Aggregating all vertices and converting to mm gave the bounds above. This is **display tessellation**, subject to its current quality and float32 coordinate precision, not an exact kernel CAD bound. The [per-part bounds and provenance summary](native-car-viewer-bounds-summary.json) records vertices, triangles, source and quality. Normal Mass Properties and mesh reads made no CAD edits or service export/translation requests.

## Recovery and limits

The Body extrusion's first local preflight stopped before a journal intent or modeling send because normal UI defaulted to ADD with inherited Part 1 merge scope. Selecting visible NEW and clearing that inherited scope made the draft match the source plan; one CLI operation then succeeded. After Axles, one normal Plane tool sequence unexpectedly navigated the owned tab to the documents listing. Returning through the official Browser showed a newly saved invalid Plane 4 `FyHJ1TOMgZFZlsZ_4`, with empty `entities`, default 25 mm and an error. The 16 preceding feature definitions were byte-identical to the saved baseline. Only that owned invalid plane was ordinarily deleted; a fresh Right-bound source plane then succeeded. No unknown write was replayed.

Final saved source revision is `7e829c1327e7a06b7c1a55fd`; journal has zero unresolved operations and extension reload guard is false. Hiding construction planes for the final screenshot changed display visibility only. This car remains a conceptual eight-solid Part Studio. It has no assembly mates, motor/roadgoing design, or proven general assembly automation. The end-to-end workflow uses reviewed CLI plus normal Browser feature allocation/reference selection; a single unattended create-car command remains unproved. The original custom-feature car has **not** been replaced or deleted.
