# H2 CAD development status

Updated 2026-11-14. This is the project lead's live state authority. Root owns handoffs and acceptance; tester alone owns browser/bridge/journal mutations. The watchdog remains stopped. Read [coordination rules](AGENT-COORDINATION.md) before work; use `followup_task` to restart a completed agent, because `send_message` alone does not restart it.

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

**Current task:** tester is creating a new native test assembly from these eight verified parts, retaining their Part Studio positions. Verify eight occurrence/source identities before replacing the old custom car/assembly. General source-backed assembly creation and mates remain an implementation gap; this simple assembly trial must not imply broader support.

## Exact targets and preservation

H2 CAD Test Project document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`.

- Verified native car Part Studio: `9b8155a2839e649138dae95f`, last known Browser tab941741361. Rediscover tab/URL before use. Full feature/operation map is in the report.
- Original custom car Part Studio `45730d1931712e2c548fae00` and Assembly `cb5c127f6a4b4eb2ab5838c9` remain untouched. User authorized replacement, but root has not approved deletion before the replacement assembly verifies. Preserve original Feature Studio `39a2e2afc5bc43eea167e938`.
- Preserve verified plate Test02 `3a4e8933dde1c594115a657f`, Test03 `db4cd489011c3f8dace7baca`, and sample schema studio `eb0d7b23baa21737e89c0464`.
- Preserve older plate `9a062f0eef8bb961f8c84f8e` and ownership-unknown Sketch `F6sL2WhVQXX64oZ_0` in `1926791d173990d5d45f70ef`.
- Test03 stale original tab941740810 was preserved; never resume that old edit controller. Its fresh verification tab was941741358.

On timeout, preserve the operation and journal. No replay, guard clearing by assumption, or guessed native IDs. New UI extrusion defaults can inherit ADD/merge scope; explicitly select source-required NEW and clear inherited scope before population. The car report records one local preflight rejection and one owned empty-plane cleanup after unexpected navigation; no uncertain write was replayed.

## Implementation and validation

Active runtime42 tree: `5fc52e3437e5643cf46a907d4eb118a3bac98feb`. Patch40 fixed explicit-null loss across browser injection by passing JSON text; exact comparisons remain strict. Patch41 creates source rectangles/circles with independent active solver and saved-tree proof. Patch42 populates source-bound literal/variable-depth extrusions amid preserved siblings.

Source43 (`bfaf034`) updates existing plugin modeling instructions and adds `references/h2-source-workflow.md`; it is documentation only and does not require interrupting the live runtime. See [MCP/skill workflow](h2cad-mcp.md) and [actual capability boundaries](CAPABILITIES.md). Existing plugin/server identity remains unchanged.

- Main regression suite:277passed after sketch/extrusion integration. Two stale bootstrap assumptions were repaired in `c127ad4`.
- Patch42 focused validation:37H2/bootstrap,155Native Python,54adapter tests passed.
- Patch43 documentation: YAML/manifest/reference/CLI checks and two bootstrap tests passed.
- Latest Graphify refresh:632nodes,2345edges,30communities,47/48files cached; no external model. Refresh once after each substantive integrated src/scripts/tests batch, not for documentation-only edits.

Earlier plate proof remains in [Test03](../artifacts/native-mvp-checkpoint/test03-clean-source-plate-2026-11-14.md). It passed with supported fresh-tab saved-state recovery. Detailed variable/plane/sketch/extrusion samples and transport repairs are in [development evidence](../artifacts/native-car-origin-circle-and-plane37-REPORT.md).

## Next stages and queued cadder

1. Verify replacement native car assembly, then perform the user's authorized old-car/assembly replacement while preserving unrelated content.
2. Root launches a **new Astra subagent named cadder** after that gate, with the exact arm brief: base rotation, vertical rail lift replacing shoulder pitch, elbow rotation, wrist rotation; NEMA17 motors, GT2 belts/pulleys,2020 extrusions, suitable rails/bearings;400mm reach and400mm side coverage;200g payload plus self-weight. Plan geometry and calculate loads/drives before modeling.
3. Cadder must work against the honest capability matrix. Centered profiles, REMOVE cuts/target-body binding, genuine hollow/T-slot profiles and source-bound assembly insertion/mates need development; coordinate those requirements with root rather than approximate away buildability. The robot design/demo is not complete and cadder has not yet launched.

The older printed robot source is a separate deferred regression, not this design: `C:/Users/patog/Documents/Codex/2026-10-29/i-want-you-to-fully-install/outputs/robot-printed/robot_printed.fs`, SHA256 `5E08D7D4E97C5E5260FA48BECCBA14AC5A8B18E874C9FB20BC023CFAC4308C35`; reported473features/73part types are not independently verified here.

Public repository: https://github.com/pat-gc/H2-cad-mcp. Root owns publishing reviewed source and sanitized evidence; private runtime config, pairing material and journals stay out of git.
