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
| Source extrusion | Ordinary active `Extrude 1` `FjpogXiV3yGx0YH_0` selects the sole `Face of Sketch 1`; its live query resolves to the source sketch's `.imprint` face. SOLID/NEW/BLIND, current UI default depth 25 mm. **Active and uncommitted**; no saved solid or source-driven extrusion accepted yet. [Region evidence](../artifacts/native-source-edit-extrude/REPORT.md). | Native candidate → Astra review → tester performs one guarded source-driven 5 mm extrusion and ordinary Save, then verifies saved solid and dimensions. |
| Repeatable minimal pair | Source sketch population with manual begin/Save is evidenced; automatic begin and complete sketch→extrude CLI/MCP remain unproven. Patch 17 Top timing change `adc06bd` is integrated but has not been activated or live retested. | Native: repair lifecycle, then tester repeats from an empty isolated studio with no manual modeling. |
| Full native car | **Not created.** The earlier Onshape car is one custom feature, not the required 22 native features. Generic `NativeBackend.apply` creation is unsupported. | After minimal pair: variables, offset planes, circles, source expressions and dependencies, all eight solids, car editability and identity-preserving replacement. |
| Collaborative safety | Intent journal and observed reconciliation have been exercised on isolated test operations. The editor revision check is client-side preflight, not atomic server compare-and-set; complete remote model/geometry readback remains limited. | Preserve unknown-outcome barriers and restrict writes to authorized isolated test targets while proving the remaining gates. No user blocker is currently known. |

The active test target is `H2 CAD Test Project` document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`, temporary Part Studio `9a062f0eef8bb961f8c84f8e`, tester tab `941740752`. The existing car Part Studio `45730d1931712e2c548fae00`, its Feature Studio `39a2e2afc5bc43eea167e938`, and unrelated document content remain preserved. Never interpret the active Extrude preview as a committed feature or a saved part.

## Owners and handoff

- **Astra:** development lead, review, integration, acceptance decisions and this status page. Current integrated master at this handoff: `ca15666`.
- **Native Sol:** implementation owner for source extrusion, ordinary Save lifecycle, automatic Top begin, and subsequent full source graph. Most recent reviewed implementation is patch 18 `f3c6f05`; next candidate is pending Native.
- **Tester Sol:** sole live Onshape validation owner. Currently idle with the uncommitted, source-bound test Extrude preserved; no further CAD action until Astra reviews the next candidate.
- **Root:** oversight and user input only. Root starts `cadder` only after the full repeatable native car acceptance described above.

Next sequence: Native candidate → Astra review → tester 5 mm extrusion and saved solid proof → autonomous minimal pair → native car variables/planes/circles/expressions and eight-part parity → verified car edit and identity preservation → authorized replacement of the old generated car. Each owner should update the matching table row with observed evidence, not transport acknowledgments or inferred success.
