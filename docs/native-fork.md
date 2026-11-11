# Onshape Native compatibility fork

This local compatibility branch starts from upstream `godbrigero/onshape-native`
commit `f5304ed0aa49347dec40911af9c2018d81012604` and preserves that Git
history. Branch: `codex/h2-native-compat` in ignored `upstream/onshape-native`.
Current fork commit: `5108cb0e2f46a60c5fed7befd5094cd363ec9179`.
Reviewable patches: `patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch`
and `patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch`.

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

Reproduction from an upstream clone at the base commit:

```powershell
git am patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch
git am patches/onshape-native/0002-fix-bound-native-state-readback-inspection.patch
node --test tests/adapter.test.mjs
```

The full Node suite passed 85/85 on Windows after both patches. A live editor tree and feature
definition response remain needed to establish a complete semantic readback
contract; the current tests use synthetic local objects and do not prove live
Onshape behavior.
