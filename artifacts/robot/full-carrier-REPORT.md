# Seven-hole carrier: complete source-run proof

Verified 2026-11-14 in **Robot - Seven Hole Carrier**:
https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/e37ca903af44622ca6919031

The unmodified [local source](bearing_carrier_scope_fixture.fs) generated all nine native features through the source-run coordinator: a variable, two offset planes, three constrained sketches, two NEW extrusions and one explicitly scoped REMOVE extrusion. Browser control allocated the blank features and selected references; the bridge populated source definitions and verified saved operations. No REST CAD writes or imported solid substitutes were used.

The holes are a centered 28 mm bore, four 5.5 mm mounting holes and two 3.3 mm holes on the vertical axis. The 24 mm cut intersects both the carrier and witness geometrically, but its explicit scope contains only the carrier. The separate witness at Z20–23 mm remains uncut.

| Normal Onshape measurement | Carrier volume mm³ | Carrier area mm² | Witness volume mm³ |
| --- | ---: | ---: | ---: |
| Source thickness 12 mm | 34465.304 | 10757.987 | 10800 |
| Ordinary UI edit to 14 mm | 40209.522 | 11593.615 | 10800 |
| Restored to 12 mm | 34465.304 | 10757.987 | — |

Volumes match the independently validated local solids at displayed precision. The witness area is 7920 mm² at both measured thicknesses. All nine feature IDs remained unchanged, and restoring the variable restored the entire saved feature tree exactly. Final revision: `c130f5d8bed1a97d87b830a4`; connected and idle; zero unresolved journal writes.

[Machine-readable operation and edit evidence](full-carrier-native-proof.json), [12 mm measurement](full-carrier-volume12.jpg), [14 mm measurement](full-carrier-volume14.jpg), [restored measurement](full-carrier-volume12-restored.jpg), [witness](full-carrier-witness.jpg), [witness after edit](full-carrier-witness14.jpg).

The coordinator intentionally returns `verify_geometry` after all feature definitions are observed. Independent geometry verification in this run was performed using the ordinary Onshape Mass Properties dialog. Automatic mass-property acceptance, autonomous blank-feature allocation, general polygon/T-slot profiles, source-backed assembly mates and the complete robotic arm remain unfinished. This carrier is a capability fixture, not a released mechanical assembly.
