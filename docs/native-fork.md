# Onshape Native compatibility fork

This local compatibility branch starts from upstream `godbrigero/onshape-native`
commit `f5304ed0aa49347dec40911af9c2018d81012604` and preserves that Git
history. Branch: `codex/h2-native-compat` in ignored `upstream/onshape-native`.
Current fork commit: `6a4e157f2aa8cb781b8ba84552bd76c180374336`.
Reviewable patches: `patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch`
`patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch`,
`patches/onshape-native/0003-fix-release-hung-read-only-bridge-work-safely.patch`, and
`patches/onshape-native/0004-feat-guard-isolated-Part-Studio-extrusion-depth-edit.patch`, and
`patches/onshape-native/0005-feat-advertise-loaded-depth-edit-capability.patch`.

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

Reproduction from an upstream clone at the base commit:

```powershell
git am patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch
git am patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch
git am patches/onshape-native/0003-fix-release-hung-read-only-bridge-work-safely.patch
git am patches/onshape-native/0004-feat-guard-isolated-Part-Studio-extrusion-depth-edit.patch
git am patches/onshape-native/0005-feat-advertise-loaded-depth-edit-capability.patch
node --test tests/adapter.test.mjs
```

The full Node suite passed 90/90 and focused bridge tests 47/47 on Windows
after five patches. H2 local tests passed 39/39 before the fifth-patch
integration and 45/45 afterward. The new command has not been
executed against Onshape; its tests use synthetic local objects. The earlier
live editor tree supports a narrow preflight shape, not a complete semantic
readback contract.
