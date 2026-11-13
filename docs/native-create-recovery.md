# Patch 11: bounded recovery and repair

The first live source sketch attempt returned `Invalid native field.` and was journaled unknown as `sketch-92236722d2ca4a40b669c2dbb8dea600`. The editable temp sketch remained blank with unchanged element revision `ce4cf721313c9e4a75dff375`. Patch 10's `hydrate` routine is the only source of that exact error, and every hydrate in its sketch branch precedes the first `callAndPromise`. An offline regression reproduced the identical error with serializer-owned private fields and zero modeling sends. Patch 11 converts typed children to plain schema fields before rehydration.

For future commands, patch 11 reports `write_stage=pre_dispatch` only before any normal UI click or modeling RPC. The bridge and H2 journal classify that as a rejected no-op. After the first click or RPC, failures remain unknown with no retry.

The earlier patch 10 response has no stage marker. Patch 11 adds a one-purpose authenticated local recovery endpoint. It accepts only the operation ID above and exact tab, requires the sole unresolved journal row to have the exact target, error, active sketch and before revision, then independently reads the same connected blank sketch with an identical full tree and checks that no bridge command is pending. Only then does it mark that row rejected and clear the persisted bridge guard. A mismatch preserves both barriers. The reviewed recovery command is:

`h2cad experimental-reconcile-known-sketch-rejection sketch-92236722d2ca4a40b669c2dbb8dea600 --tab-id 941740731 --bridge-config <paired-config> --journal <same-pinned-journal>`

The tester must stage reviewed patch 11 and restart the Python bridge before this command. The existing patch 10 extension can serve the read-only recovery state. On `rejected_pre_dispatch`, the tester can use the official extension reload, check fresh patch 11 capabilities, inspect the still blank active Top sketch, and send **one** repaired source population attempt after Astra review. On any recovery refusal, retain the unknown journal and guard and do not retry. No operation targets the existing car.

Patch 11 also contains dormant page commands for normal Sketch/Top initiation and active extrusion depth population. The Top selector is grounded in the tester's ordinary editor observation. Their H2 orchestration and live acceptance are separate next steps; this handoff asks only for bounded recovery and one repaired sketch trial.
