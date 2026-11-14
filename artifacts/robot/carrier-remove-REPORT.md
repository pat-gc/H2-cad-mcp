# Live native scoped REMOVE and centered-circle proof

2026-11-14. Paired companion/extension source46 was activated after saved-idle
and clear-journal checks. Target remains **Robot - Carrier Scope Test**,
document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`,
element `423a1c4eec848f03a9800ba5`.

The full `fixtures/native/carrier_remove_scope_sample.fs` was validated locally
before the writer populated its final REMOVE extrusion. Browser allocated the
draft and selected REMOVE, positive direction and one explicit body. The writer
verified source/journal identities, unchanged target sketch and extrusion,
fresh body query, unchanged unrelated features, then populated the source depth
and independently reconciled saved state. No REST CAD writes or opaque solids.

Cut operation `extrude-69d0f6c3fb9343d998acdfa34ab0c3cc` created native feature
`FXY94T7TMD6sGVL_2`, saved revision `043ede7530940aadec2c634e`.
See [writer result](carrier-remove-native-result.json).

| Native measurement | Carrier volume | Witness volume |
| --- | ---: | ---: |
| Source thickness 12 mm, 24 mm cut | 42,860.708 mm³ | 10,800 mm³ |
| Ordinary UI variable edit to 14 mm | 50,004.159 mm³ | 10,800 mm³ |
| Restore to 12 mm | 42,860.708 mm³ | unchanged definition |

These agree with carrier `(60*60 - pi*3²)*thickness` and witness `60*60*3`.
The witness occupies Z20…23, within the Z0…24 tool path: preserving it tests
scope exclusion rather than merely a tool that misses the second body.
All nine feature IDs remained stable, and restoring 12 mm restored the exact
feature tree. Restored revision `4050945c2e3e70b8862fcbb1`.
[Edit/restore evidence](carrier-remove-edit-restore.json),
[12 mm measurement](carrier-cut-volume12.png),
[14 mm measurement](carrier-cut-volume14.png),
[witness at 14 mm](carrier-witness-at14.png),
[restored measurement](carrier-cut-volume12-restored.png).

An additional locally validated source,
`fixtures/native/carrier_centered_circle_proof.fs`, appends a sketch containing
three radius3 circles at (0,0), (0,15), (15,0). It generated ordinary native
COINCIDENT/HORIZONTAL/VERTICAL positioning constraints rather than zero-length
dimensions. The active solver and independent saved-definition checks passed;
the feature contains three circles plus fixed origin and nine constraints.
Native feature `FpM8W9b6uEiLz0P_2`, operation
`source-sketch-b28f73c898444e65b05de340f6d2260d`, saved revision
`0a87fae1ef50f8cd55f559d4`. [Saved proof](carrier-centered-native-result.json).

This proves the small native cut and axis-centered sketch primitives. The
seven-hole bearing carrier combination, genuine T-slot profiles, full robot
assembly/joints, collision checks and mechanical release gates remain separate
work. No complete robotic arm or released manufacturing design is claimed.
