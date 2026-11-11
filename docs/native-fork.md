# Onshape Native compatibility fork

This local compatibility branch starts from upstream `godbrigero/onshape-native`
commit `f5304ed0aa49347dec40911af9c2018d81012604` and preserves that Git
history. Branch: `codex/h2-native-compat` in ignored `upstream/onshape-native`.
Current fork commit: `4091e21d2460c393c639606cbd1f495c1999aefb`.
Reviewable patches: `patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch`
`patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch`, and
`patches/onshape-native/0003-fix-release-hung-read-only-bridge-work-safely.patch`.

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

Reproduction from an upstream clone at the base commit:

```powershell
git am patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch
git am patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch
git am patches/onshape-native/0003-fix-release-hung-read-only-bridge-work-safely.patch
node --test tests/adapter.test.mjs
```

The full Node suite passed 87/87 on Windows after three patches. A live editor tree and feature
definition response remain needed to establish a complete semantic readback
contract; the current tests use synthetic local objects and do not prove live
Onshape behavior.
