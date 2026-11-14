# H2 CAD code graph

[Graphify](https://github.com/Graphify-Labs/graphify) maps the local code in `src/`, `scripts/`, and `tests/`. It uses syntax parsing without an external model. The map does not index CAD fixture geometry or replace the evidence and acceptance gates in [the development status](STATUS.md).

On a fresh Windows checkout, install the pinned [Graphify package](https://pypi.org/project/graphifyy/0.9.108/) in its own environment. Run these commands from the repository root with `uv` and Python 3.12 available:

```powershell
uv venv --python 3.12 --no-python-downloads .graphify-venv
uv pip install --python .\.graphify-venv\Scripts\python.exe --index-url https://pypi.org/simple 'graphifyy==0.9.108'
```

After an integrated change to source, scripts, or tests, the development owner refreshes the graph from the main checkout before handing off. Run both lines in the same PowerShell invocation:

```powershell
$env:GRAPHIFY_BACKEND = 'none'
& .\.graphify-venv\Scripts\graphify.exe update . --force
```

`--force` allows the updated graph to shrink when code is deleted; unchanged code still uses the syntax cache. Refreshing isn't needed for documentation or generated output changes. Use `graphify-out/GRAPH_REPORT.md` for an offline overview, `graphify-out/graph.html` to browse the map (the browser loads its rendering library from a public CDN), or query `graphify-out/graph.json` locally with the CLI. Generated outputs and the tool environment are excluded from Git.

For unfamiliar call paths, dependencies, or affected tests, consult the existing
graph when it narrows navigation, then confirm each finding in the actual
source. Use `rg` for simple names and file lookups. Do not query or refresh the
graph for every small edit; refresh once after an integrated source, script, or
test batch as described above.
