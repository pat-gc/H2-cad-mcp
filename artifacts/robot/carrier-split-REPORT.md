# Split-body source and measurement proof

Verified in [Robot - Split Scope Test](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/4bae4e36c39e40e64e8146d1).

The [source fixture](../../fixtures/native/carrier_split_scope_sample.fs) was built
locally before native modeling. Nine editable native features were created through
the source-run coordinator. One rectangular slot splits the carrier into two
solids; the separate witness intersects the cut path but is excluded from scope.

| Ordinary thickness edit | Witness mm³ | Each carrier half mm³ | Total mm³ |
| --- | ---: | ---: | ---: |
| 12 mm | 10800 | 19440 | 49680 |
| 14 mm | 10800 | 22680 | 56160 |
| Restored 12 mm | 10800 | 19440 | 49680 |

Native read-only QueryInsertables enumerated all three solids. GetQueryData
associated both halves with the original NEW creator, while their full operation
IDs pointed to the Boolean cut. The candidate scope verifier rejects a selection
containing only one half. A separate hidden-witness test retained the hidden body
in both server inventory and viewer inventory.

`inspect-geometry` acquired volume and area directly through the native session
bridge, without REST. The final area is 18576 mm². `measure-native` compared count,
volume and area with local validation and retained a hashed evidence report.
Document and element revisions were checked separately throughout each read batch.
The coordinator rejected source acceptance while the variable was changed; after
restoring 12 mm it accepted the matching metrics again.

All nine feature IDs and all three body IDs stayed unchanged. The restored saved
feature tree exactly matches the original. Final element revision:
`d559ebfd48db73fba2a05d78`; connected idle, no unresolved journal writes.

[Machine-readable proof](carrier-split-native-proof.json),
[local preview](carrier-split-local-preview.png),
[native screenshot](carrier-split-native.jpg),
[hidden-witness screenshot](carrier-hidden-witness.jpg).

This establishes scoped first-cut behavior, split-body identification and automatic
mass-property comparison. It does not authorize repeated cuts: complete source
journal/modification-chain binding and independent write-time scope verification
remain unimplemented. Mass properties do not prove topology, bounds, fit or motion.
The actual 2020 profile and robotic arm assembly remain unfinished.
