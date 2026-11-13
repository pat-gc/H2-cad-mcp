# Onshape Native compatibility fork

This local compatibility branch starts from upstream `godbrigero/onshape-native`
commit `f5304ed0aa49347dec40911af9c2018d81012604` and preserves that Git
history. Branch: `codex/h2-native-compat` in ignored `upstream/onshape-native`.
Current candidate fork commit in the isolated Native creation worktree:
`1e90135d3d7752d531f16a0a8c78c1bac3ab2720`. The running bridge and
extension require an explicit reviewed reload before this candidate can be probed.
Reviewable patches: `patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch`
`patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch`,
`patches/onshape-native/0003-fix-release-hung-read-only-bridge-work-safely.patch`, and
`patches/onshape-native/0004-feat-guard-isolated-Part-Studio-extrusion-depth-edit.patch`, and
`patches/onshape-native/0005-feat-advertise-loaded-depth-edit-capability.patch`, and
`patches/onshape-native/0006-feat-add-guarded-paired-extension-reload.patch`, and
`patches/onshape-native/0007-fix-persist-reload-safety-and-validate-new-worker-in.patch`, and
`patches/onshape-native/0008-feat-inspect-native-creation-allocator-surfaces-read.patch`.

The user reports that the upstream owner authorized integration. This note
records the report, not an independently verified public license grant. Keep
upstream attribution and commit ancestry; do not publish the fork without
checking the precise permission terms.

The first fork change adds a read-only `h2Readback` probe to native editor
`state`: candidate feature IDs, node IDs, types, names, and presence of status,
parameters, entities, and constraints. It explicitly reports `complete=false`.
There is no inferred geometry, no copied captured IDs, and no write-path change.
The second patch bounds probe traversal and raw tree serialization so a large
editor tree fails closed instead of leaving the extension worker busy. This
addresses a plausible contributor to a live read-only state timeout; causation
is unproven because the tab had also reported a disconnected editor.
The third patch gives selected read-only editor commands a bounded wait in the
extension worker. If a read hangs, its one request returns a timeout error;
another exact tab can still be inspected. Writes stay paused while the original
read task remains unresolved. Potentially committed writes retain the original
no-timeout, no-replay fail-closed behavior.
The fourth patch adds one experimental native editor transaction that edits the
depth of a saved solid/new/blind extrusion. It is hard limited to the
authorized disposable Part Studio. It checks live feature identity, element
revision, parameter type and previous depth before using the editor's
BeginEdit/SpecifyFeature/Commit lifecycle. It reports only definition readback.
H2 independently rereads the entire tree before observing the journal intent.
Live execution and geometry/editability verification remain with the testing
agent; this patch does not create a sketch or extrusion.
The fifth patch advertises separate read-only capability markers in the bridge
health response, extension handshake, and page state. H2 checks all three
before journaling or submitting an edit. An old loaded build refuses the edit
without leaving an unresolved journal intent.
The sixth patch adds a bounded paired reload command to the existing local
Native MCP and CLI distribution. The worker uses its own `chrome.runtime.reload()`
only after an authenticated bridge acknowledgement. The bridge checks the
configured H2 write journal, active bridge commands, the currently paired
extension identity, and a new worker instance handshake with the expected
build and capability. Existing loaded builds need one normal manual Reload.
No CAD mutation or journal state is changed by this command. See the candidate
fork's `docs/extension-reload.md` for setup and result meanings.
The seventh patch requires a valid new worker UUID before declaring success and
persists pending or uncertain reload and CAD write state beside the pinned H2
journal, so a bridge restart cannot silently unlock or repeat it.
The eighth patch adds a read-only native creation probe. It lists relevant
method names on the already-used editor objects and checks whether local
serializer constructors generate unique node IDs. It does not invoke an
allocator, send a feature command, or change the CAD document.

Reproduction from an upstream clone at the base commit:

```powershell
git am patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch
git am patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch
git am patches/onshape-native/0003-fix-release-hung-read-only-bridge-work-safely.patch
git am patches/onshape-native/0004-feat-guard-isolated-Part-Studio-extrusion-depth-edit.patch
git am patches/onshape-native/0005-feat-advertise-loaded-depth-edit-capability.patch
git am patches/onshape-native/0006-feat-add-guarded-paired-extension-reload.patch
git am patches/onshape-native/0007-fix-persist-reload-safety-and-validate-new-worker-in.patch
git am patches/onshape-native/0008-feat-inspect-native-creation-allocator-surfaces-read.patch
node --test tests/adapter.test.mjs
```

The full Node suite passed 93/93 after eight patches. Targeted Native Python
bridge tests passed 48/48, and H2 tests passed 58/58. The
full Native Python suite had 238 passed, one skipped, and two failures in
unmodified Windows-specific tests: symlink creation lacked privilege and one
archive separator case was not rejected. The new command has not been
executed against Onshape; its tests use synthetic local objects. The earlier
live editor tree supports a narrow preflight shape, not a complete semantic
readback contract.
