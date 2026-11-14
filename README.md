# H2 CAD

H2 CAD compiles supported FSGen scripts into a semantic feature plan, validates
geometry locally with OpenCascade, and records guarded execution intent. Its
browser adapter inspects the native Onshape editor through a separately installed
companion. An experimental, explicitly targeted Sketch and Extrude path is under
live validation. Its revision check is not atomic, so it is restricted to an
isolated test Part Studio and does not yet establish a repeatable car workflow.

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

## Offline workflow

```powershell
python -m h2cad compile path/to/part.fs --did DID --wid WID --eid EID --output desired.json
python -m h2cad validate path/to/part.fs
python -m h2cad plan --base examples/collaboration/base.json --observed examples/collaboration/observed.json --desired examples/collaboration/desired.json
python scripts/benchmark.py --source upstream/onshape-fsgen/examples/native/plate.fs --iterations 3
```

`compile` and `validate` require the optional pinned FSGen installation.
`plan` is an offline three-way merge; it returns conflicts rather than
overwriting concurrent changes. The example has a human sketch radius change
and an independent AI extrusion depth change. The planner preserves both.

## Native inspection

With an already paired and running companion, supply its local `bridge.json`
explicitly:

```powershell
python -m h2cad doctor --bridge-config PATH_TO_BRIDGE_JSON
python -m h2cad inspect --did DID --wid WID --eid EID --bridge-config PATH_TO_BRIDGE_JSON
python -m h2cad reconcile OP_ID --journal PATH_TO_JOURNAL_DB --bridge-config PATH_TO_BRIDGE_JSON
```

`inspect` reads the exact editor tree; it can contain private model data.
`reconcile` never resubmits a write. The adapter permits only native editor
jobs, with no browser-session REST fallback. See [architecture](docs/ARCHITECTURE.md),
[Native audit](docs/audits/native.md), [fork patch](docs/native-fork.md), and
[integration limits](docs/native-integration.md).

The existing Onshape Native MCP server also exposes an experimental H2 plate
tool. It calls this package's CLI for the same local validation, journaled native
commands and readback. See [MCP setup and limits](docs/h2cad-mcp.md).
