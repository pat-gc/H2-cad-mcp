# Onshape Native compatibility fork

This local compatibility branch starts from upstream `godbrigero/onshape-native`
commit `f5304ed0aa49347dec40911af9c2018d81012604` and preserves that Git
history. Branch: `codex/h2-native-compat` in ignored `upstream/onshape-native`.
Current fork commit: `4320d04337a6b0e96b814df3569bfd38b87b621e`.
Reviewable patch: `patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch`.

The user reports that the upstream owner authorized integration. This note
records the report, not an independently verified public license grant. Keep
upstream attribution and commit ancestry; do not publish the fork without
checking the precise permission terms.

The first fork change adds a read-only `h2Readback` probe to native editor
`state`: candidate feature IDs, node IDs, types, names, and presence of status,
parameters, entities, and constraints. It explicitly reports `complete=false`.
There is no inferred geometry, no copied captured IDs, and no write-path change.

Reproduction from an upstream clone at the base commit:

```powershell
git am patches/onshape-native/0001-feat-add-fail-closed-H2-native-readback-probe.patch
node --test tests/adapter.test.mjs
```

The focused Node suite passed 23/23 on Windows. A live editor tree and feature
definition response remain needed to establish a complete semantic readback
contract; the current tests use synthetic local objects and do not prove live
Onshape behavior.
