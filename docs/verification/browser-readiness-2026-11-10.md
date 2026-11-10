# Browser and bridge readiness — 2026-11-10

Scope: local setup and read-only checks. No Onshape write was attempted.

## Local result

The pinned Native fork checkout is at
`4320d04337a6b0e96b814df3569bfd38b87b621e`. Its existing private
`.runtime/bridge.json` was reused. Running
`.venv/Scripts/python.exe scripts/configure.py` created the ignored
`extension/local-config.js` and `.mcp.json` without printing pairing data.
The extension folder prepared for loading is
`C:\Users\patog\Documents\ChatGPT\H2 cad\upstream\onshape-native\extension`.

The loopback bridge was started as a hidden Windows process from the pinned
checkout (`scripts/bridge.py`, process ID 38644 at startup). Output and error
were redirected into ignored private `.runtime` files; the error file was empty.
`python -m h2cad doctor --bridge-config
C:\Users\patog\Documents\ChatGPT\H2 cad\upstream\onshape-native\.runtime\bridge.json`
then returned exit 0:

```json
{"bridge_protocol": 1, "extension": null, "extension_connected": false}
```

The bridge is therefore ready locally, but there is no authenticated extension
connection. A prior read-only check of an existing Edge Onshape assembly tab
showed the signed-in account and a page banner saying Onshape was disconnected
and attempting to reconnect. The tab was not reloaded or edited. Browser
control blocked opening `edge://extensions` under its URL policy, so extension
installation, activation, and profile inspection could not be completed by
this agent. No alternate browser route was attempted.

## User action required

In the same Edge profile as the Onshape tab, open `edge://extensions`, enable
Developer mode if needed, choose **Load unpacked**, and select the extension
folder above. Then open the **Onshape Native Local Bridge** toolbar popup and
choose **Connect**. If an older copy is already installed, inspect it before
loading another; keep the existing pairing and avoid regenerating its token.
Wait until Onshape itself reconnects. The agent can then rerun read-only
`doctor` and exact-target `inspect` to check the loaded extension version,
capabilities, editor profile, and readback completeness. No live model write is
authorized without an explicit disposable editable Part Studio URL.
