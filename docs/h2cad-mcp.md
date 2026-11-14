# Experimental H2 tool in the existing Native MCP server

The reviewed Native fork adds `experimental_h2_create_plate` to its existing
`onshape_native` stdio MCP server and modeling instructions. This is one entry
point into `python -m h2cad experimental-create-plate`; it does not implement a
second CAD compiler, server, or REST fallback. It remains experimental until a
clean empty-studio run and independent saved geometry/editability checks pass.

The MCP server and H2 CLI must use the same Python environment. After preparing
the pinned Native and FSGen checkouts, install this package and pinned FSGen into
the Native MCP launcher's environment. For the local Windows checkout:

```powershell
uv pip install --python .\upstream\onshape-native\.venv\Scripts\python.exe -e . -e .\upstream\onshape-fsgen
& .\upstream\onshape-native\.venv\Scripts\python.exe -c "import h2cad, fsgen"
```

The existing `.mcp.json` launcher must point to that Native Python environment.
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

This first tool supports one validated Top rectangle and one blind extrusion in
an isolated empty test Part Studio. Variables, offset planes, circles, dependent
expressions, multi-body car creation, and assemblies are outside its current
native operation set. The existing Native MCP server still contains other tools,
including REST tools; the H2 tool itself invokes only H2's browser-session
native path and never switches to those tools.
