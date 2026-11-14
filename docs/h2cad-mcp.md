# H2 agent workflow in the existing Native plugin

The delivery is the existing **Onshape Native plugin and modeling skill**, backed
by its `onshape_native` MCP/session bridge and H2 CLI. An agent validates the FSGen
source locally, allocates each blank feature through normal Browser controls,
then delegates source geometry to the deterministic CLI and verifies the durable
journal result. There is no second orchestrator and no single autonomous car MCP
call. The complete native car and assemblies are not yet accepted; consult
[current verification status](STATUS.md) rather than inferring acceptance from
the presence of a command.

The source Chassis sketch and extrusion have saved-definition evidence. Final
geometry verification and the remaining car groups are underway.

After bootstrap, the packaged instructions are
`upstream/onshape-native/skills/onshape-native-modeling/SKILL.md`, with the complete
source workflow in its `references/h2-source-workflow.md`. The existing
`.codex-plugin/plugin.json` keeps the `onshape-native` identity, skill discovery,
and generated `.mcp.json` stdio configuration. No new plugin or tool registration
is needed for the skill workflow. The host must provide local command execution
and the official Browser plugin; the MCP bridge alone cannot perform the trusted
Browser allocation steps.

## Source-driven execution

Run `python -m h2cad compile SOURCE --did DID --wid WID --eid EID --output desired.json`
and `python -m h2cad validate SOURCE` before modeling. Consume `desired.json`'s
feature order and dependencies. Record each successful operation ID and native
feature ID against its source logical ID, using the existing journal as the
authority. Reuse those observed identities for later dependencies; never derive
IDs from display names or copy IDs from a sample.

All population commands below take `SOURCE`, `--logical-id`, `--did`, `--wid`,
`--eid`, `--bridge-config`, `--tab-id`, and the same pinned `--journal`.

| Source feature | Population command | Additional binding inputs |
| --- | --- | --- |
| Literal length variable | `experimental-populate-variable` | Repeated `--previous-variable-op-id` in source variable order; fresh unnamed LENGTH draft |
| OFFSET plane | `experimental-populate-plane` | `--baseline`, `--reference-binding`, `--variable-operations`, repeated `--previous-plane-op-id`; normal UI-bound reference plane |
| Supported rectangle or circle sketch | `experimental-populate-source-sketch` | `--baseline`, `--plane-op-id`, `--variable-operations`; blank sketch on that observed source plane |
| NEW/SOLID/BLIND extrusion | `experimental-populate-source-extrusion` | `--baseline`, `--sketch-op-id`, optional `--variable-op-id` for symbolic depth; normal whole-sketch region selection |

A baseline is the full saved-idle native state captured **before** allocating the
next draft, with its exact target, revision, and unchanged tree. Variable-map
files contain only the dependency names and observed operation IDs required by
that command. Plane reference binding additionally records the active draft's
exact query and independently resolved query data at the same revision; the
packaged workflow describes its fields. Keep these private runtime artifacts
outside published source.

For the basic car, this means processing its seven variables, then the plane,
sketch, and extrusion dependencies in the compiled source order. It does not mean
batching all sketches or all planes first. The Chassis sketch, for example, uses
the observed `Chassis height` plane operation and the `#length`/`#width` variable
operations. Geometry and expressions come from the source, not Browser drawing.

After each command, require an observed journal result and independent saved-idle
readback before allocating the next feature. An RPC acknowledgement, Save click,
or candidate receipt is insufficient. Sketch Commit additionally requires the
active solver graph to match source coordinates. Preserve uncertain operations
and reconcile their original IDs without replay:

| Operation | Read-only reconciliation command |
| --- | --- |
| Variable | `experimental-reconcile-saved-source-variable` |
| Plane | `experimental-reconcile-saved-source-plane` |
| Source sketch | `experimental-reconcile-saved-source-sketch` |
| Source extrusion | `experimental-reconcile-saved-source-extrude` |

Each reconciliation command takes `OP_ID`, `--bridge-config`, `--tab-id`, and
`--journal`. It retains the barrier if the target, definition, solver evidence,
saved state, or marker retirement is unconfirmed. Missing graph receipts cannot
be replaced with an assumption. A fresh same-target tab can supply independent
saved-state readback, but does not authorize replaying or canceling an uncertain
write. H2 never falls back to REST CAD writes.

Feature definitions, evaluated geometry, and human editability are separate
checks. Validate the final part count/bounds and an ordinary parameter edit that
regenerates dependent geometry. Assemblies remain outside this source writer.

## Experimental source-run checkpoints

`experimental-source-run` coordinates the existing guarded writers in source
order. It pins the source hash, target, journal and locally validated plan in a
run file. It does not allocate Browser drafts or create assemblies. The CLI is
offline-tested, including all 22 car features, and has created an eight-feature
carrier setup live with independently measured two-part geometry. Only NEW
extrusions are admitted by the coordinator; REMOVE remains disabled here.

The companion must run patch44 or later so authenticated health reports its
startup creation target. `doctor --bridge-config ...` displays this as
`running_creation_target`. Editing the private configuration file alone does
not retarget a running companion. The coordinator refuses a missing or stale
running target before staging; restart the reviewed companion only after
resolving outstanding journal operations, without replacing pairing material.

Pass the same arguments to each action:

```powershell
$runArgs = @('fixtures/car/basic_car.fs', '--run-state', 'out/car-run.json',
  '--bridge-config', '<private bridge.json>', '--journal', '<pinned journal.sqlite>',
  '--tab-id', '<current tab id>', '--did', '<document id>',
  '--wid', '<workspace id>', '--eid', '<approved Part Studio id>')
& .\.venv\Scripts\python.exe -m h2cad experimental-source-run init @runArgs
& .\.venv\Scripts\python.exe -m h2cad experimental-source-run next @runArgs
# Allocate exactly the returned blank feature/reference through Browser.
& .\.venv\Scripts\python.exe -m h2cad experimental-source-run apply @runArgs
# Repeat next -> Browser allocation -> apply for each source feature.
```

Resume the existing run file after interruption. Never initialize another run
to bypass an observed or unresolved operation. The coordinator adopts matching
independently observed journal entries without replay. Changed source, target,
staged tab, native definitions or saved baseline stop dispatch. Reconcile an
uncertain operation using the existing writer-specific commands before resuming.
Final `verify_geometry` explicitly reports `geometry_verified: false`: verify
solid count, geometry and a native parameter edit separately.

## Existing plate MCP entry point

The reviewed Native fork adds `experimental_h2_create_plate` to its existing
`onshape_native` stdio MCP server and modeling instructions. This is one entry
point into `python -m h2cad experimental-create-plate`; it does not implement a
second CAD compiler, server, or REST fallback. Plate geometry and editability
have been verified with documented Browser orchestration and saved-state
recovery; the standalone wrapper does not automate every intermediate step.

The MCP server and H2 CLI must use the same compatible Python environment. On
this Windows machine the existing Native `.venv` is ARM64 and cannot import the
installed x64 OpenCascade kernel; the existing H2 root `.venv` is AMD64 and can
import both FSGen and OpenCascade. Use that H2 environment as the **one MCP
launcher interpreter**. After preparing the pinned Native checkout, install its
package into the already working H2 environment:

```powershell
uv pip install --python .\.venv\Scripts\python.exe -e .\upstream\onshape-native
& .\.venv\Scripts\python.exe -c "import h2cad, fsgen, OCP, mcp, onshape_native"
$nativeRuntime = (Get-Content .\upstream\onshape-native\.mcp.json | ConvertFrom-Json).mcpServers.onshape_native.env.ONSHAPE_NATIVE_RUNTIME
& .\.venv\Scripts\python.exe .\upstream\onshape-native\scripts\configure.py --runtime-dir $nativeRuntime --mcp-python (Resolve-Path .\.venv\Scripts\python.exe).Path
```

The generated Native `.mcp.json` launcher then points to that x64 H2 Python;
keep its existing private pairing runtime. `--mcp-python` checks the required
imports before changing the launcher. This is local setup, not a second server.
Its private `ONSHAPE_NATIVE_RUNTIME/bridge.json` must pin the same existing H2
SQLite journal and the exact approved empty test Part Studio as
`h2cad_create_target`. Pairing and journal paths stay private. The tool takes an
absolute local `.fs` source path, exact unconfigured workspace Part Studio URL,
and connected editor `tab_id`. It delegates to the H2 CLI with those exact IDs;
the CLI checks the pinned target and journal and records intent before each
possible native write. Local FSGen/OpenCascade validation and the supported
rectangle/extrusion source check run before modeling.

`h2_command_completed` means the CLI returned its saved-definition checks. It
does not prove a solid or human editability; inspect the saved Part Studio and
edit a dimension separately. `needs_readback` means the CLI failed or its receipt
could not be parsed. The MCP tool makes no retry. Inspect the pinned journal and
current exact editor state, then use the appropriate read-only reconciliation
path before any new creation attempt. If H2 or FSGen is absent from the MCP
environment, installation must be repaired before using the tool.

The CLI additionally supports `experimental-create-plate ...
--resume-sketch-op-id OP_ID` for an interrupted run whose source sketch has
already been positively reconciled to `observed`, before any extrusion was
allocated. It reruns local validation and checks the exact target, source
blueprint, entity prefix, saved feature identity, and origin/solver evidence.
It skips both sketch stages and uses the existing live extrusion preflight.
Unresolved writes or an existing extrusion stop continuation; this is not a
generic retry or a resume path after extrusion allocation. The MCP wrapper
does not yet expose this CLI option.

This plate tool supports one validated Top rectangle and one blind extrusion in
an isolated empty test Part Studio. Its wrapper does not invoke the newer
source-feature commands listed above or create assemblies. The existing Native
MCP server still contains other tools,
including REST tools; the H2 tool itself invokes only H2's browser-session
native path and never switches to those tools.
