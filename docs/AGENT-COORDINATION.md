# Agent coordination

2026-11-13. Team working rules; [STATUS.md](STATUS.md) remains the authority for live state, acceptance, owners and sequencing. This document does not authorize new live operations.

## Working rules

- Astra integrates status and accepts handoffs. Native owns implementation and paired runtime changes. Tester alone owns live browser actions. Root oversees. Assign an extra worker only to a bounded, independent output; release its slot after handoff.
- Before a task starts, name its owned files, input interface, output artifact, acceptance check and blocker. Shared checkout edits require disjoint files. Worktrees isolate files but do not isolate the browser, extension, server, journal or Onshape document.
- A handoff contains: commit; changed files; exact test command and result; server and extension identities/capabilities actually observed; target document/workspace/element and revision; pending operation ID and guard state; evidence paths; next owner and one next action. Use `not observed` for missing runtime facts. A staged patch is not an activated runtime.
- On timeout/disconnect, retain the operation ID and journal. Reattach and read exact target, feature identities and revision before reconciliation. Never interpret a transport acknowledgement as saved geometry, clear a guard by assumption, or replay an uncertain write. Runtime reload/restart belongs in the tester's coordinated handoff, after the applicable guard permits it.
- Send updates on changed evidence, completed output or a specific blocker. Avoid repeated unchanged polling, duplicate reviews and multiple supervisors asking the same owner for status. Batch independent reads and scoped offline tests; run Graphify once after substantive integration as STATUS requires.

These rules address this repository's delayed saved extrusion, saved blank Top sketch, disconnect/reattachment, staged-versus-active extension mismatch, and shared browser/journal state. The live sequence in STATUS takes precedence if newer evidence changes it.
