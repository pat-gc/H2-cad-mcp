# Development roadmap

Technical lead: GPT-6 Astra, high reasoning. Implementation and independent
verification: genuine GPT-6 Sol workers, medium reasoning.

## Acceptance milestones

0. Audit and pin upstream repositories; run baseline tests — in progress.
1. Browser-backed editable native sketch and extrusion — pending; live acceptance requires an explicit test target and browser access.
2. FSGen plan integration with local validation — pending.
3. Reference model parity — pending.
4. Identity-preserving incremental modification — pending.
5. Three-way collaborative synchronization — pending.
6. Journaled recovery and revision guards — pending.
7. Expand evidenced feature coverage — pending.
8. Benchmarks and Windows hardening — pending.
9. Reproducible usable delivery — pending.

## Invariants

- Onshape is authoritative; local validation does not prove remote regeneration.
- Unknown human features and independent human parameter edits are preserved.
- Ambiguous writes are reconciled, never blindly retried.
- Native editability and dependency integrity are acceptance criteria.
- Unsupported or unverified capabilities are explicitly identified.
- Upstream source is not redistributed before license evidence is checked.

## Work organization

Two independent workers run at a time because the root coordination chat and Astra
occupy the other two runtime slots. Isolated git worktrees protect concurrent
implementation. Roles rotate between generation, browser runtime, graph/sync,
execution, independent verification, and integration.
