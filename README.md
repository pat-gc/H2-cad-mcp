# H2 CAD

H2 CAD validates supported FSGen geometry locally with OpenCascade, then creates
native, human-editable Onshape variables, planes, sketches and extrusions through
the existing browser-session bridge. It uses ordinary Browser controls to allocate
features and deterministic source commands to populate them. It does not use
Onshape REST CAD writes or imported-solid substitutes.

The full native car and seven-hole carrier have passed live geometry measurements
and ordinary parameter edit/restore checks. Execution remains experimental and
restricted to explicitly targeted test studios: general profiles, source-backed
assembly mates and the complete four-axis robotic arm are unfinished. Revision
checks are not atomic; concurrent edits require inspection and reconciliation.
See [current status](docs/STATUS.md) and [capability boundaries](docs/CAPABILITIES.md).

## Set up

Python 3.11 or newer and Git are required. On Windows, use an x64 Python process
for optional FSGen/OpenCascade support. The setup script checks pinned upstream
commits and applies a reviewable compatibility patch; it refuses dirty or
unrecognized existing checkouts.

```powershell
python scripts/bootstrap.py --check
python scripts/bootstrap.py --dry-run
python scripts/bootstrap.py --sources-only
# In an x64 Python shell, install optional FSGen/OpenCascade support:
python scripts/bootstrap.py --with-fsgen
```

The last command creates `.venv`, installs this package and pinned FSGen, and
prepares the local Native compatibility source. It does not install or approve
the browser extension or open an Onshape document. On Windows, the equivalent
wrapper is `./scripts/bootstrap.ps1 -WithFsgen`.

Use `bootstrap.py --with-fsgen` for FSGen rather than installing FSGen from a
Git wheel: the current upstream wheel omits `native/featurespecs.json`, which
its compiler needs. Bootstrap checks out the pinned source and installs it
editably, retaining that resource.

## Offline workflow

```powershell
python -m h2cad compile path/to/part.fs --did DID --wid WID --eid EID --output desired.json
python -m h2cad validate path/to/part.fs
python -m h2cad preview path/to/part.fs --output artifacts/part-preview.png
python -m h2cad plan --base examples/collaboration/base.json --observed examples/collaboration/observed.json --desired examples/collaboration/desired.json
python scripts/benchmark.py --source upstream/onshape-fsgen/examples/native/plate.fs --iterations 3
```

`compile` and `validate` require the optional pinned FSGen installation.
`preview` renders the actual local solids and writes a neighboring JSON report
with source/image hashes, geometry metrics and solid validity. It requires the
local rendering dependencies and makes no Onshape call. A local preview does not
establish native feature support; check the capability matrix before pushing.
`plan` is an offline three-way merge; it returns conflicts rather than
overwriting concurrent changes. The example has a human sketch radius change
and an independent AI extrusion depth change. The planner preserves both.

## Native inspection

With an already paired and running companion, supply its local `bridge.json`
explicitly:

```powershell
python -m h2cad doctor --bridge-config PATH_TO_BRIDGE_JSON
python -m h2cad inspect --did DID --wid WID --eid EID --bridge-config PATH_TO_BRIDGE_JSON
python -m h2cad inspect-geometry --did DID --wid WID --eid EID --bridge-config PATH_TO_BRIDGE_JSON --tab-id TAB --output artifacts/native-geometry.json
python -m h2cad reconcile OP_ID --journal PATH_TO_JOURNAL_DB --bridge-config PATH_TO_BRIDGE_JSON
```

`inspect` reads the exact editor tree; it can contain private model data.
`reconcile` never resubmits a write. The adapter permits only native editor
jobs, with no browser-session REST fallback. See [architecture](docs/ARCHITECTURE.md),
[Native audit](docs/audits/native.md), [fork patch](docs/native-fork.md), and
[integration limits](docs/native-integration.md).

The existing Onshape Native plugin supplies an agent workflow using its MCP
session bridge, normal Browser feature allocation, and deterministic H2 source
commands for variables, planes, sketches, and extrusions. Its separate
experimental MCP plate tool remains limited to the plate sequence. See
[plugin workflow, commands, and limits](docs/h2cad-mcp.md). The persistent
`experimental-source-run` coordinator validates source once, stages each Browser
allocation, binds observed native features and resumes without replaying uncertain
writes. Final geometric and editability acceptance remain independent checks.

Live evidence: [native car](artifacts/native-car-full-source-REPORT.md),
[seven-hole carrier](artifacts/robot/full-carrier-REPORT.md), and
[current assembly limitation](artifacts/native-car-source-assembly-REPORT.md).
