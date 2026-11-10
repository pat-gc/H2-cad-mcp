# FSGen upstream audit (2026-11-10)

## Pin and rights

- Repository: <https://github.com/Lucasfrit/onshape-fsgen>
- Audited commit: `eabcc02ba104005da3de869e613cefe53042fd98` (`git rev-parse HEAD`). The clone is in ignored `upstream/onshape-fsgen`; no upstream code is copied here.
- Root `LICENSE` is MIT, copyright 2026 Lucasfrit. Vendored `third_party/featuretree/LICENSE` is separately MIT, copyright 2026 dnewcome. Retain notices when redistributing substantial source.
- `pyproject.toml` declares Python `>=3.11,<3.15` and direct dependencies `build123d>=0.9`, `requests`, `python-dotenv`, `anthropic`, `matplotlib`, `numpy`. An unconstrained build123d resolved to 0.13.0 in this audit.

## Source-backed architecture

`fsgen/native/script.py` interprets a restricted Part Studio FeatureScript dialect into `TraceResult`. Its ordered `FeatureRec` values contain `feature_type`, logical `name`, typed `params`, optional `SketchRec`, and source line. `QText` carries a FeatureScript query plus a set of referenced logical names. The tracer checks feature parameter names/enums against `featurespecs.json`, enforces unique names and solved sketches, and blocks low-level custom-feature `op*` calls. It does not represent a complete Onshape document graph or existing human features.

`fsgen/native/build.py` serializes each record to Onshape feature JSON. Sketch serialization creates entities and dimensional constraints; regular features receive complete default parameters from `featurespecs.json`. `push_trace` sends one standard native feature at a time through `fsgen/onshape.py` REST `Onshape` client. Its persisted `.fsgen_native.json` state is local and positional: feature name, type, hash, native ID, and status. It reuses a same-position/same-hash feature, updates a changed same-type feature, and deletes the tail after a type/order mismatch. It does not read the remote tree before deciding, enforce an atomic workspace revision, or merge human edits. `get_studio` creates a Part Studio when state is absent. This is not safe collaborative synchronization without a new planner, remote readback, and execution boundary.

`fsgen/native/local.py` runs the trace through FS-Lite's OpenCascade geometry in `fsgen/fslite/geom.py` via build123d/OCP. Unsupported feature handlers yield a partial warning, so `ok=True` alone does not imply full validation. The locally supported subset is listed in `fsgen/native/catalog.py::LOCAL_SUPPORT`; `featurespecs.json` contains a wider parameter vocabulary, not a claim that every feature is locally built. The catalog's `verified`/`learned` labels in `catalog.json` are historical upstream claims; they are not live results from this audit. `fsgen/native/paste.py` emits one custom FeatureScript feature, which is an explicitly different editability class from the native tree.

`examples/native/plate.fs` demonstrates the initial graph: `newSketch` on Top, `skRectangle`, `skSolve`, then `extrude` using `qSketchRegion(id + "Plate sketch")`, `BoundingType.BLIND`, and variable depth. For integration, retain FSGen's trace and local builder, convert records to stable logical IDs and explicit dependencies (`QText.refs`, sketch plane and other typed references), and preserve a complete serialized native body as provenance. Do not treat query strings or REST JSON as verified Onshape Native browser RPC payloads. A semantic three-way planner should preserve unowned remote features, merge only independently changed parameter keys, and reject structural/topology conflicts.

## Windows and local validation

Commands run in the pinned upstream clone, with no Onshape credentials and no live service write:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e . pytest
```

The first install failed: `py -0p` showed the default Python 3.11 was ARM64; no `win_arm64` cadquery-ocp wheel satisfied build123d. Retried with the installed x64 interpreter:

```powershell
uv venv --clear --python 'C:\Users\patog\AppData\Local\Programs\Python\Python311-x64\python.exe' .venv
uv pip install --python .venv/Scripts/python.exe -e . pytest
.venv/Scripts/python.exe -m pytest -q
```

The x64 install succeeded (82 packages, build123d 0.13.0, cadquery-ocp-novtk 8.0.1.1.0). Test result is pending below. `AGENTS.md` documents Unix `.venv/bin/fsgen`; use `.venv/Scripts/fsgen.exe` on Windows. `fsgen/cli.py::paste_command` calls macOS `pbcopy`, so automatic clipboard copying is unavailable on Windows though the paste file is written. Paths in outputs are otherwise built with `pathlib`; platform success is limited to the tested offline commands.

## Integration recommendation

Reuse `trace`, `FeatureRec`/`QText`, `feature_json` for offline compilation, and `build_local` for supported local OCC validation behind a pinned optional dependency. Convert to the project's semantic feature graph before planning. Keep FSGen `push_trace`, `get_studio`, and the REST client out of the browser-native execution path. Require remote identity and revision readback and a durable operation journal. Until Native's typed editor creation/verification is replay-proven, report native browser writes as experimental rather than claiming end-to-end editable CAD support.
