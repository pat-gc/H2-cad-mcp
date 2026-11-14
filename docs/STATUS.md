> **Active budget:** user authorized continuation until90%remaining (10%used). Root is sole live owner; check account meter between batches and stop at10%used. Last observed9%used. Workers are idle after bounded handoffs.
>
> **Live work:** paired source46 is active. The complete nine-feature seven-hole carrier passed through the coordinator, including a scoped cut preserving the witness and12→14→12 ordinary variable edit with exact tree restoration. Current EIDe37ca903af44622ca6919031/tab941741361 is idle at revisionc130f5d8bed1a97d87b830a4. See `artifacts/robot/full-carrier-REPORT.md`. Earlier carrier/origin-circle studios are preserved. Measurement comparison is now retained separately from automatic verification. Hollow square tube primitive is locally validated only; actual2020T-slot and assemblies remain open.

# H2 CAD development status

Updated 2026-11-14. This is the project lead's live state authority. Root owns handoffs and acceptance; Root currently owns browser/bridge/journal mutations; tester is stopped. The watchdog remains stopped. Read [coordination rules](AGENT-COORDINATION.md) before work; use `followup_task` to restart a completed agent, because `send_message` alone does not restart it.

## Objective and current result

Deliver an MCP/plugin/skill workflow that validates FSGen CAD locally, then creates native human-editable Onshape features through our browser-session bridge, without REST CAD-write fallback. The ultimate demonstration is the requested four-axis robotic arm, with design/load calculations before modeling. Do not equate a successful car with complete mechanical-design or assembly support.

**The full native car Part Studio has passed.** [Complete report and identity map](../artifacts/native-car-full-source-REPORT.md), [actual screenshot](../artifacts/native-car-complete-clean-view.jpg), [independent mesh bounds](../artifacts/native-car-viewer-bounds-summary.json).

| Acceptance check | Verified result |
| --- | --- |
| Source | `fixtures/car/basic_car.fs`, SHA256 `C7C397354394C91F5648667BFF9D48A63757105C331DB83E283B469D69245EE8` |
| Native structure | 22 source features: seven variables, five planes, five sketches, five NEW extrusions; native constraints and source expressions retained |
| Solids | Eight parts: `JID,JMD,JQD,JQH,JUD,JUH,JYD,JYH` |
| Volume / area | Onshape525414.51mm³ /85598.583mm², matching local525414.5098 /85598.5828 |
| Independent bounds | Loaded viewer geometry approximately[-57,-90,1]→[57,90,65]mm, or114×180×64mm; same displayed revision, identity transforms, meters converted to mm. Tessellated bounds, not exact kernel bounds |
| Human editability | Ordinary wheelRadius14→16→14 changed volume525414.51→534462.297→525414.51mm³; eight stable part IDs and22 stable feature IDs; all definitions restored exactly |
| Final saved state | Revision `7e829c1327e7a06b7c1a55fd`, connected idle, zero unresolved writes, guard false |
| Workflow | Local validation plus Browser blank-feature allocation/reference selection and deterministic source CLI population; no manual car drawing. A single autonomous create-car MCP call remains unproved |

**Current task:** root is completing the source-run coordinator and robot primitives. The eight-occurrence native car assembly and authorized old-car replacement passed; see [assembly proof](../artifacts/native-car-source-assembly-REPORT.md) and [replacement proof](../artifacts/native-car-replacement-REPORT.md). General source-backed assembly creation and mates remain an implementation gap.

## Exact targets and preservation

H2 CAD Test Project document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`.

- Verified native car Part Studio: `9b8155a2839e649138dae95f`, last known Browser tab941741361. Rediscover tab/URL before use. Full feature/operation map is in the report.
- Original custom car Part Studio `45730d1931712e2c548fae00` and empty Assembly `cb5c127f6a4b4eb2ab5838c9` were deleted after replacement verification. The new native assembly is `4b621d8d622b4d57863db2cb`. Preserve original Feature Studio `39a2e2afc5bc43eea167e938` and unrelated tabs.
- Preserve verified plate Test02 `3a4e8933dde1c594115a657f`, Test03 `db4cd489011c3f8dace7baca`, and sample schema studio `eb0d7b23baa21737e89c0464`.
- Preserve older plate `9a062f0eef8bb961f8c84f8e` and ownership-unknown Sketch `F6sL2WhVQXX64oZ_0` in `1926791d173990d5d45f70ef`.
- Test03 stale original tab941740810 was preserved; never resume that old edit controller. Its fresh verification tab was941741358.

On timeout, preserve the operation and journal. No replay, guard clearing by assumption, or guessed native IDs. New UI extrusion defaults can inherit ADD/merge scope; explicitly select source-required NEW and clear inherited scope before population. The car report records one local preflight rejection and one owned empty-plane cleanup after unexpected navigation; no uncertain write was replayed.

## Implementation and validation

Active paired source46 tree: `cc9f5f269fe0134befe4c69b545a909365379c57`. Patch44 reports loaded creation target; patches45/46 implement explicit REMOVE scope bound to an observed NEW extrusion and unchanged single-profile target sketch. Active native cut, preserved witness, variable edit/restore and centered-circle solver proofs are in the carrier report.

Source43 (`bfaf034`) updates existing plugin modeling instructions and adds `references/h2-source-workflow.md`; it is documentation only and does not require interrupting the live runtime. See [MCP/skill workflow](h2cad-mcp.md) and [actual capability boundaries](CAPABILITIES.md). Existing plugin/server identity remains unchanged.

Source47 (`914d844`, tree `13a9995f99bef8af6a3c7f872d35ea7b46d5b812`) updates that bundled workflow with the persistent coordinator, scoped-cut boundary and revision-bound measurement evidence. Bootstrap reproducibility:2passed. This patch changes documentation only; paired modeling runtime46 remains active and no extension reload is needed.

- Main regression suite:277passed after sketch/extrusion integration. Two stale bootstrap assumptions were repaired in `c127ad4`.
- Patch42 focused validation:37H2/bootstrap,155Native Python,54adapter tests passed.
- Patch43 documentation: YAML/manifest/reference/CLI checks and two bootstrap tests passed.
- Latest full suite:348passed after coordinator REMOVE integration. Latest focused source-run/CLI/setup tests:45passed, including measurement provenance, stale revision and changed/missing evidence rejection. Hollow-tube local validation:5passed.
- Latest Graphify refresh:745nodes,2702edges,22communities,46/56files cached; no external model. Refresh once after each substantive integrated src/scripts/tests batch, not for documentation-only edits.

Earlier plate proof remains in [Test03](../artifacts/native-mvp-checkpoint/test03-clean-source-plate-2026-11-14.md). It passed with supported fresh-tab saved-state recovery. Detailed variable/plane/sketch/extrusion samples and transport repairs are in [development evidence](../artifacts/native-car-origin-circle-and-plane37-REPORT.md).

## Next stages and queued cadder

1. Centered profiles and explicit-scope REMOVE passed on the full seven-hole carrier/witness fixture. Next geometry gap is actual2020T-slot profiles; the locally validated hollow square tube is a distinct primitive, not a substitute.
2. New Astra `cadder` completed the first plan in [robot design](robot/DESIGN.md): base rotation, vertical rail lift, elbow rotation and wrist rotation; NEMA17 motors, GT2 belts/pulleys,2020 extrusions, rails/bearings;400mm reach and400mm side coverage;200g payload plus self-weight. Calculations and local carrier validation passed; component ratings, clearances and physical checks remain open.
3. Continue against the capability matrix: genuine hollow/T-slot profiles and source-bound assembly insertion/mates need development. The robot design/demo is not complete. Cadder is idle pending primitives.

The older printed robot source is a separate deferred regression, not this design: `C:/Users/patog/Documents/Codex/2026-10-29/i-want-you-to-fully-install/outputs/robot-printed/robot_printed.fs`, SHA256 `5E08D7D4E97C5E5260FA48BECCBA14AC5A8B18E874C9FB20BC023CFAC4308C35`; reported473features/73part types are not independently verified here.

Public repository: https://github.com/pat-gc/H2-cad-mcp. Root owns publishing reviewed source and sanitized evidence; private runtime config, pairing material and journals stay out of git.
