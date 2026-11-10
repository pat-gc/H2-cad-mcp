# Independent verification — 2026-11-10

Implementation snapshot: `f536c98d9aee3dc3955f14dd416cb48344c9a703`.
Testing worktree: `codex/independent-testing`. Windows, x64 CPython 3.11.9
from the pinned FSGen virtual environment. `PYTHONPATH` pointed at this
worktree's `src` so tests used the integrated source, not another installation.

## Results

| Check | Exact command or method | Result | Evidence level |
| --- | --- | --- | --- |
| Full Python suite | `python -m pytest -q` | 34 passed, 1 expected failure in 9.37 s | Offline and mocked bridge; includes real local OCC geometry |
| Native compatibility fork | `node --test tests/*.test.mjs` in `upstream/onshape-native` | 83 passed, 0 failed | Synthetic Node fixtures; no live editor profile |
| FSGen plate geometry | `python -m h2cad validate upstream/onshape-fsgen/examples/native/plate.fs` | `passed`; 1 part; 23244.3849 mm³; no warnings | Real local OpenCascade; remote and editability `not_run` |
| Process exclusion | `test_target_lock_excludes_another_process_and_releases` | Passed: a second Python process could not acquire the same journal/target lock until first process released it | Real OS process and file lock |
| Cancellation and restart | `test_cancel_during_remote_handoff_stays_unresolved_after_restart` | Passed: journal remained pending/unknown, restarted executor refused replay, one backend submission | Fake backend, real SQLite journal |
| Feature order | `tests/test_executor_adversarial.py` | Both passed: reordered untouched human features rejected before submission or left unknown after readback | Fake backend |
| Variable edit | `tests/test_fsgen_adapter.py` | Plate's `#thickness` edit planned as one parameter update; sketch dependencies retained | Actual FSGen trace, offline planner |
| Native bridge doctor | `python -m h2cad doctor --bridge-config upstream/onshape-native/.runtime/bridge.json` | Exit 1: `Installed native bridge unavailable` | Local runtime check |
| Browser session | Read only Edge inventory and existing Onshape assembly tab | Signed-in Onshape chrome visible; page banner said disconnected and reconnecting | Live browser UI, no mutation |

The pinned clones were `eabcc02ba104005da3de869e613cefe53042fd98`
for FSGen and `4320d04337a6b0e96b814df3569bfd38b87b621e` for the local
Native fork. Native's original base is
`f5304ed0aa49347dec40911af9c2018d81012604`.

## Reproduced issue

`test_bootstrap_refuses_unrecognized_native_descendant` is an intentionally
strict `xfail`. I cloned the pinned Native fork and added an empty clean commit.
`bootstrap(..., sources_only=True)` accepted the extra descendant. The current
logic checks ancestry and reverse patch applicability, which establish that
the reviewed patch is present, but do not exclude additional commits. This
does not match the documented refusal of unrecognized existing checkouts.

## Limits

No editable disposable Part Studio was supplied. The bridge was unavailable
and the existing Onshape tab reported disconnection, so native profile
compatibility, remote regeneration, sketch/extrusion creation, human editability,
and browser-backed readback remain unverified. The process lock is scoped to
one journal database path and target key; separate journal paths do not share it.
`reconcile` does not acquire the target lock, so it can read during execution;
this was identified by source inspection and was not exercised against a live
backend.
