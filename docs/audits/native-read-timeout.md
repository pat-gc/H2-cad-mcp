# Native read timeout, patch 30

The observed 12–15 second read failures carry the extension's exact 10-second
`boundedRead` timeout message. The H2 client allows 60 seconds and the broker
waits 50 seconds, so these observations do not establish a broker timeout or a
lost HTTP reply. Broker `pending=0` confirms only that the bounded result was
returned; the original page task may still run. The extension retains its
per-tab orphaned-read barrier. No CAD write is retried or unblocked by this
diagnostic patch.

The path is H2 `NativeBridge.command` → broker `/command` → extension
`boundedRead` → exact tab lookup → `chrome.scripting.executeScript` in the page
→ model tree serialization → reply and optional response transfer. Patch 30
reports a bounded phase (`extension_received`, `tab_lookup`, `page_script`,
`page_reply`, or `response_transfer`) and elapsed milliseconds on read timeout.
The H2 and Native Python clients preserve those fields in the error. The phase
identifies where the extension awaited when its timer fired, not whether the
page task finished or what statement within it blocked.

`native_state` previously enumerated the serializer registry on every read.
That discovery is needed for typed construction, not state or editor health.
Patch 30 defers it until schema or typed commands request it. This removes
demonstrably unnecessary work, but no captured trace proves it caused the past
timeouts. The editor's model getter or serialization remains unobserved within
the `page_script` phase. A trace should only be considered after a permitted
browser action opens and verifies the exact target tab again.

Exact URL matching already occurs before page script execution in
`extension/worker.js` `resolveTab`, using `matchesEditor`; the editor-tab tests
cover wrong URL, configuration, and foreign origin. A reused tab ID pointing
to another Part Studio must fail at lookup. A closed tab, disconnected Onshape
editor, still-running page task, malformed page reply, and transfer failure are
separate conditions. Extension loopback connectivity alone proves none of
those editor conditions.

Patch 30 tests: Native adapter state skips registry while schema still uses it;
connection timeout preserves phase, elapsed time, and the orphan write barrier;
H2 and Native Python clients surface the diagnostic with exactly one command.
Pinned bootstrap replay verifies the reviewed 30-patch tree. Live verification
has not occurred; the historical unknown begin operation and guard remain.
