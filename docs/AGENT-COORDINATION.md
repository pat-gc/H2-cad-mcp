# Agent coordination

2026-11-13. Team working rules; [STATUS.md](STATUS.md) remains the authority for live state, acceptance, owners and sequencing. This document does not authorize new live operations.

## Working rules

- Root is project lead for sustained supervision and end-to-end completion. Astra is the sublead for Root-assigned review and coordination, and backup for escalation. Native owns implementation and paired runtime changes. Tester alone owns live browser actions. Assign an extra worker only to a bounded, independent output; release its slot after handoff.
- Before a task starts, name its owned files, input interface, output artifact, acceptance check and blocker. Shared checkout edits require disjoint files. Worktrees isolate files but do not isolate the browser, extension, server, journal or Onshape document.
- A handoff contains: commit; changed files; exact test command and result; server and extension identities/capabilities actually observed; target document/workspace/element and revision; pending operation ID and guard state; evidence paths; next owner and one next action. Use `not observed` for missing runtime facts. A staged patch is not an activated runtime.
- Root checks agent status at every approval or next-task handoff. Use `followup_task` for a completed agent: `send_message` alone does not restart it. After a bounded wait without an update, inspect status before waiting again.
- Send actionable completions, failures and blockers to Root promptly; copy Astra when implementation review or coordination applies. The watchdog was stopped at the user's request; Root owns progress checks and the next-task decision, with Astra as backup. Root keeps the status page current through reviewed integration.
- On timeout/disconnect, retain the operation ID and journal. Reattach and read exact target, feature identities and revision before reconciliation. Never interpret a transport acknowledgement as saved geometry, clear a guard by assumption, or replay an uncertain write. Runtime reload/restart belongs in the tester's coordinated handoff, after the applicable guard permits it.
- Send updates on changed evidence, completed output or a specific blocker. Avoid repeated unchanged polling, duplicate reviews and multiple supervisors asking the same owner for status. Batch independent reads and scoped offline tests; run Graphify once after substantive integration as STATUS requires.

These rules address this repository's delayed saved extrusion, saved blank Top sketch, disconnect/reattachment, staged-versus-active extension mismatch, and shared browser/journal state. The live sequence in STATUS takes precedence if newer evidence changes it.

## Usage reserve

Latest user instruction: continue until **85% remaining (15% used)**. This supersedes the earlier 90% threshold. Check the account usage meter between bounded work batches and stop development when it reaches 15% used. Checkpoint active work and stop workers; do not launch an unbounded parallel batch. If a worker reports a usage-limit error, stop that worker and inspect account state rather than repeatedly retrying. Never purchase credits or redeem a reset without explicit authorization.
