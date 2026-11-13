# Paired extension self-reload verification — 2026-11-13

This check used the reviewed Native patch 7 tree `8f5b4ff2009cec50830be8c75ef41980213abe9d` in the user's existing unpacked extension folder. The existing pairing and runtime directory were preserved. No CAD write or document command was sent.

The shared persistent H2 journal was initialized only after confirming it had been absent and no bridge mutation had been attempted. It was pinned in the Native bridge configuration at `.runtime/h2cad-depth.sqlite`. Before and after the reload it contained zero writes and no unresolved intent. The local bridge was restarted from the exact reviewed checkout, and `/health` advertised `h2_extension_reload_server_v1`.

Before the one self-reload call, the authenticated bridge reported extension version `0.4.4`, build `h2-extension-reload-v1`, capability `h2_extension_reload_v1`, runtime ID `apegfgchneleamdoljddjpjadflldfcj`, and valid worker instance UUID `711f56dd-77fe-448c-8e2b-f5c5c197d09f`. The H2 CLI command was:

```powershell
.venv/Scripts/h2cad.exe extension-reload --bridge-config upstream/onshape-native/.runtime/bridge.json --journal upstream/onshape-native/.runtime/h2cad-depth.sqlite
```

It returned exit 0, `status=reconnected`, `phase=new_handshake_verified`, and a request ID. A fresh authenticated `/health` then showed the same runtime ID, version, build and capabilities, with new worker UUID `0b43678d-b273-418d-888c-41fc4b780dc7`. The persistent local guard reported `reload.status=reconnected`, `reload.phase=new_handshake_verified`, and `unknown_write=false`. No retry was made.

The H2 installed CLI now exposes `extension-reload`. The installed Native checkout contains its MCP `extension_reload` tool and `.mcp.json` launcher configuration. This Codex session did not expose that Native MCP tool as a callable connector, so MCP invocation was **not_run**; no duplicate reload was issued to test packaging. The CAD depth edit and native geometry/regeneration validation remain separate, untested steps.
