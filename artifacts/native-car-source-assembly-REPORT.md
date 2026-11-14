# Separate native car test assembly — 2026-11-14

After the [22-feature, eight-solid source car](native-car-full-source-REPORT.md) passed volume, bounds and reversible edit checks, normal Onshape Browser controls created a **new** tab named `Native Car Source Assembly Test`: [actual Assembly](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/4b621d8d622b4d57863db2cb). The original custom car and `Assembly 1` were not edited, renamed or deleted. [Actual saved assembly screenshot](native-car-source-assembly-eight-occurrences.jpg).

The ordinary `#add-element-button` menu created a new Assembly tab. Its observed toolbar `div.tool[command-id="insertPartOrAssembly"]` opened Insert parts and assemblies. In Current document → Part Studios, the exact source Part Studio row was `.select-item-dialog-item.parent-item[data-bs-original-title="Native Car Source Variables Test 02"]`. One normal click on that row displayed `Inserted: 8`; the dialog's visible `.ns-dialog-button-ok` saved it. The instance tree then showed `Instances (8)`, `Part 1 <1>` through `Part 8 <1>`, and `Mate features (0)`. There was no canvas placement or drag. Onshape's [insertion documentation](https://cad.onshape.com/help/Content/Assembly/insert_parts_and_assemblies.htm) says parts inserted this way align Part Studio and Assembly origins.

## Independent assembly readback

Saved assembly `native_state` is connected and idle at revision `313bfe22c361f0d362864e00`, but its `tree.instances` and `assemblyTree.nodes` are empty due lazy assembly definitions. Those empty arrays cannot be treated as proof of no instances. The existing read-only `viewer_mesh` list at the **same displayed microversion** returned eight loaded parts, eight unique occurrence paths, and source `full_element_id` rooted in verified Part Studio `9b8155a2839e649138dae95f` at display microversion `56e3965de03a89dd46ffe363`. All eight per-occurrence readbacks had identity transforms and original source body IDs:

| Source part | Body ID | Occurrence path |
| --- | --- | --- |
| Part 1 | `JID` | `M0E00ppn3/JNI2lIQ` |
| Part 2 | `JMD` | `MAWzelXr+CaiTGN7K` |
| Part 3 | `JQD` | `MtxkmR44o1kFEp0GW` |
| Part 4 | `JQH` | `MgXTBd5GhooePVqfI` |
| Part 5 | `JUD` | `MjFhRBjdIFYn0nu8i` |
| Part 6 | `JUH` | `M+xXIO4WPHWA0TpUk` |
| Part 7 | `JYD` | `MP8aZtMCStbD7DoQj` |
| Part 8 | `JYH` | `MDwf4mqi6l/I1V3Wz` |

Aggregated assembly display tessellation bounds were min `[-57.00000003,-90.00000358,1.00000005]`, max `[57.00000003,90.00000358,64.99999762]` mm, exactly the same loaded-mesh bounds as the source Part Studio within float32 precision. This independently confirms that the eight inserted instances retained their Part Studio positions. These are loaded display meshes, not exact CAD or mate validation. [Read-only occurrence, transform and bounds summary](native-car-source-assembly-viewer-summary.json).

For future source-bound assembly automation, the live serializer's **read-only constructor schemas** were captured for [tree item definition request](native-car-assembly-tree-request-schema.json) (`classId=3222`, `elementId`, `nodeId`, `parentOccurrence.path`) and [insert occurrence](native-car-assembly-insert-occurrence-schema.json) (`classId=521`, `elementId`, `insertables`, `initialTransform`, `startDrag`, configuration/library fields). These defaults establish available message shapes only. No typed insertion request was sent or recorded, and the general source-to-assembly pipeline remains unimplemented. The saved assembly currently has eight independent un-mated instances; no joints, mates or additional geometry were added.
