# H2 CAD development status

Updated 2026-11-13. **This is the development lead's current status page.** Read it before starting a new stage; at each substantive handoff, the owner reports the exact row change and evidence to Astra for integration. Historical trials and plans retain their own dates.

After integrating a substantive `src/`, `scripts/`, or `tests/` batch, refresh the local code map once from the main checkout using the [Graphify workflow](GRAPHIFY.md) before the handoff.

## Objective and acceptance

Generate the approved [basic car source](../fixtures/car/basic_car.fs) as a **repeatable native, human-editable Onshape feature tree**. Acceptance requires all 22 planned features (7 variables, 5 planes, 5 sketches, 5 extrudes), eight resulting solids matching the approved local 114 × 180 × 64 mm bounds, source parametric expressions and dependencies, one verified edit and regeneration of the resulting car, preservation of unrelated feature identities, and a repeatable CLI/MCP workflow without manual modeling steps. Apply the [acceptance gates](ACCEPTANCE.md), including separate definition, regeneration, geometry, and human-editability evidence. Only after the full native creation path is proven may the authorized existing generated car be replaced. The later `cadder` launch condition and exact robotics brief are recorded under [Queued future requirement](verification/native-begin-top-trial-2026-11-13.md#queued-future-requirement); robotics work has not started.

## Current result and next gate

| Gate | Current evidence and limit | Next owner/action |
| --- | --- | --- |
| Local source model | Approved eight-solid conceptual car from `basic_car.fs`; local geometry bounds 114 × 180 × 64 mm. This is local parity only. | Native: compile its full variable, plane, sketch, and extrusion graph to supported native operations. |
| Native source sketch | In isolated test Part Studio, FSGen-sourced 40 × 20 mm sketch `FDwrlDX9Oobgytk_0` has four editable lines, 11 constraints, internal Fix at origin, and a direct live constraint graph without error. Width 40→45→40 mm and height 20→25→20 mm were edited in the ordinary UI and restored. [Exact readbacks](../artifacts/native-source-edit-extrude/REPORT.md). | Native: make Top selection and Sketch Save autonomous; manual setup/completion remains a limit. |
| Source extrusion | Patch 20's source-driven 5 mm update on a fresh ordinary UI-bound Extrude `FQiKvPTvs72j1km_0` produced a saved, idle native definition and visible `Part 1`. The live region query resolves to source sketch `FDwrlDX9Oobgytk_0.imprint`; independent tree exactly matches the journaled expected tree, and Onshape mass properties show **4000 mm³** volume and **2200 mm²** surface area, matching 40 × 20 × 5 mm. **Journal operation `extrude-0c56afc209d243c3b78c8eed504fa839` remains unknown and the write guard remains set** because the command's final page poll did not confirm Save; do not retry or edit. | Native: implement exact positive post-Save reconciliation; Astra reviews; tester verifies reconciliation, then one reversible saved-solid edit and restore. |
| Repeatable minimal pair | Source sketch and Extrude were both initiated through ordinary UI; source population and 5 mm extrusion definition were driven by FSGen commands, but sketch completion needed manual Save and the extrusion result remains journal-unresolved. Automatic Top begin and complete sketch→extrude CLI/MCP are unproven. Patch 17's Top timing change `adc06bd` is loaded but not live retested. | Native: repair lifecycle, then tester repeats from an empty isolated studio without manual modeling. |
| Full native car | **Not created.** The earlier Onshape car is one custom feature, not the required 22 native features. Generic `NativeBackend.apply` creation is unsupported. | After minimal pair: variables, offset planes, circles, source expressions and dependencies, all eight solids, car editability and identity-preserving replacement. |
| Collaborative safety | The current extrusion intent is `unknown` with persistent `unknown_write=true` even though independent saved state matches its expected tree. The editor revision check is client-side preflight, not atomic server compare-and-set; complete remote model/geometry readback remains limited. | Reconcile the exact known intent from positive readback before any further test write; preserve the barrier until then. No user blocker is currently known. |

The active test target is `H2 CAD Test Project` document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`, temporary Part Studio `9a062f0eef8bb961f8c84f8e`, tester tab `941740760`. The existing car Part Studio `45730d1931712e2c548fae00`, its Feature Studio `39a2e2afc5bc43eea167e938`, and unrelated document content remain preserved. The saved test solid is independently observed, while its journaled operation is still unresolved.

## Owners and handoff

- **Astra:** development lead, review, integration, acceptance decisions and this status page. Patch 20 is integrated at `69c3a29`; the latest main baseline before this handoff was `6d14847`.
- **Native Sol:** implementation owner for exact extrusion reconciliation, ordinary Save lifecycle, automatic Top begin, and the subsequent full source graph. Reviewed patch 20 is loaded; a reconciliation candidate is pending Native.
- **Tester Sol:** sole live Onshape validation owner. Currently idle with saved test `Part 1` visible; no CAD edit or repeat while the extrusion journal barrier is set.
- **Root:** oversight and user input only. Root starts `cadder` only after the full repeatable native car acceptance described above.

Next sequence: Native exact-result reconciliation → Astra review → tester clears the guard through approved positive proof → saved-solid edit/restore → autonomous minimal pair → native car variables/planes/circles/expressions and eight-part parity → verified car edit and identity preservation → authorized replacement of the old generated car. Each owner should update the matching table row with observed evidence, not transport acknowledgments or inferred success.
