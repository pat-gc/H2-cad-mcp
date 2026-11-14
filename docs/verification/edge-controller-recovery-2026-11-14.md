# Edge controller recovery — 2026-11-14

## Observed result

The official Browser plugin connected to Microsoft Edge. Its tab listing and
accessibility state supplied the complete Onshape URL without reading a cropped
address bar. This supersedes earlier reports that no Edge controller was available.
The JavaScript execution tool's presence alone neither proved nor disproved this
connection; the documented browser selection call succeeded.

Root selected Edge's saved Onshape account through Computer Use at the user's
explicit request. The password stayed masked. After sign-in, Browser control
confirmed the exact existing target:

- Document: `4e078dec822b4e509616b1cb`
- Workspace: `af0627de07264acf086e646a`
- Part Studio: `3a4e8933dde1c594115a657f`
- Existing tab: `941740810` (rediscover rather than assume this remains valid)

The UI showed Sketch 1 and Parts (0), with no visible active feature dialog.
That is not sufficient to clear the pending native-write journal. Tester must
verify the exact saved feature and definition through the established readback.
No modeling action was performed during this login recovery.

## Supported connection procedure

Use the installed Browser skill's setup instructions and its official
`scripts/browser-client.mjs` entry point through the provided JavaScript tool.
Select `agent.browsers.get("edge")`, read that browser's complete documentation,
name the session, then select the exact target from `edge.user.openTabs()` and
pass the returned object to `edge.user.claimTab(...)`. Reuse the resulting
browser binding; do not reset it or rediscover a backend for each task.

In this session the missing setup skill was found in the bundled marketplace
staging directory at
`C:/Users/patog/.codex/.tmp/bundled-marketplaces/openai-bundled/plugins/chrome/skills/control-chrome/SKILL.md`.
The runtime was available in the versioned Browser plugin cache. These are
machine-specific discovery facts, not portable installation paths. Do not copy
plugin internals into this project or infer availability from cache files alone.

User preference: Browser control for Onshape; Computer Use only for saved
sign-in when necessary. The first Computer Use attempt returned Windows
`GetCursorPos failed: Access is denied. (0x80070005)`; the user-requested retry
succeeded. This does not establish why the first attempt failed.

Proof of authenticated target: `artifacts/onshape-login-restored.jpg`.
