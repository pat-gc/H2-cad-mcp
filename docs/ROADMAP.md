# Development roadmap

This is the planned milestone sequence. For the verified result, active target,
current owners, and next action, use the canonical [development status](STATUS.md).
Status labels in earlier revisions were superseded by live testing on 2026-11-13.

## Acceptance milestones

0. Audit and pin upstream repositories; run baseline tests.
1. Browser-backed editable native sketch and extrusion.
2. FSGen plan integration with local validation.
3. Reference model parity.
4. Identity-preserving incremental modification.
5. Three-way collaborative synchronization.
6. Journaled recovery and revision guards.
7. Expand evidenced feature coverage.
8. Benchmarks and Windows hardening.
9. Reproducible usable delivery.

## Invariants

- Onshape is authoritative; local validation does not prove remote regeneration.
- Unknown human features and independent human parameter edits are preserved.
- Ambiguous writes are reconciled, never blindly retried.
- Native editability and dependency integrity are acceptance criteria.
- Unsupported or unverified capabilities are explicitly identified.
- Upstream source is not redistributed before license evidence is checked.

## Work organization

The [status page](STATUS.md#owners-and-handoff) records current owners and the
live handoff. Isolated Git worktrees protect concurrent implementation.
