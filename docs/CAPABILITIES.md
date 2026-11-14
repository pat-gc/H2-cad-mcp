# Capability evidence

Updated 2026-11-14. [STATUS.md](STATUS.md) is the authority for the current live run. Local FSGen supports more operations than the current native writers; successful source parsing alone does not authorize a native write.

## Implemented source workflow

The supported delivery is an agent skill combining local FSGen/OpenCascade validation, ordinary Browser feature allocation, deterministic source population through the private Native session bridge, and independent saved-state reconciliation. It is not a single autonomous car MCP call. No REST CAD-write fallback is used.

| Operation | Implemented native path | Boundary |
| --- | --- | --- |
| Variables | Literal ASSIGNED/LENGTH variables, source-order journal bindings | General expression-valued variables and arbitrary updates are unsupported |
| Rectangles | One rectangle per source sketch, four lines and twelve source constraints mapped to thirteen native constraints with a fixed local origin; symbolic dimensions preserved | Both first-corner coordinates must be nonzero in the new source path; the legacy plate path handles origin-anchored rectangles. No mixed/multiple profiles |
| Circles | One or more circles, each with diameter and two position dimensions; source expressions and fixed local origin | Origin-centered and axis-centered circles passed native active-solver and saved-definition checks |
| Planes | Signed OFFSET from Top or Right, including live-tested zero offset, literal or validated linear expressions | No Front, angled, face-derived or arbitrary-frame planes |
| Extrusions | SOLID/NEW/BLIND, exact whole-sketch regions, positive literal or direct variable depth | Explicit-scope REMOVE passed live on one observed source-created body; ADD/intersection, arithmetic depth expressions, reverse/symmetric extrusion and draft remain unsupported |
| Regeneration | Native variable edits regenerate dependent source geometry; same-ID restoration tested in isolated samples | Full car14→16→14 wheel-radius edit passed with stable IDs and exact restored definitions |
| Updates | Three-way planner and narrowly scoped native edit paths exist | General source synchronization and existing-feature update execution remain unsupported |
| Assemblies | Underlying tools inspect/edit existing mates, transform existing occurrences and preview existing revolute mates | No source-backed assembly creation, insertion or mate-creation pipeline |
| Unknown writes | Intent journal, exact target/revision checks, no replay, independent saved-tree proof and explicit marker retirement | Missing proof/receipt leaves an operation unresolved; no atomic rollback promise |
| Authentication | Authenticated Edge session and private loopback pairing; official Browser controls | Computer Use is authorized only for saved sign-in |

Live evidence includes the source plate with edit/restore; all seven car variables; source planes, rectangles and circles; and source extrusions. The car passed all22 native definitions, eight-solid volume/area, independent tessellated bounds, and ordinary parameter edit/restore checks. The isolated two-circle extrusion proved two NEW solids and variable-driven regeneration. These results do not establish a general mechanical-design or assembly compiler. See the [evidence report](../artifacts/native-car-origin-circle-and-plane37-REPORT.md).

## Implementation references

- Source staging: `src/h2cad/native_rectangles.py`, `native_circles.py`, `native_planes.py`, `native_extrusions.py`.
- Journaled writers: `src/h2cad/native_sketches.py`, `native_source_extrusions.py`, and variable population in `native.py`.
- Native protocol and independent verification: reviewed patches under `patches/onshape-native/`, paired source46; patches45/46 add journal-bound scoped REMOVE with unchanged single-profile target sketch and live scope re-resolution.
- Agent workflow and commands: [MCP integration](h2cad-mcp.md), packaged modeling skill reference `references/h2-source-workflow.md`.

## Remaining primitives for the robotic arm

1. Combine the now-live-proven zero-coordinate circles and scoped REMOVE into the complete seven-hole bearing carrier fixture. See [live primitive proof](../artifacts/robot/carrier-remove-REPORT.md).
2. Mixed/nested profiles or validated component insertion for actual hollow/T-slot 2020 profiles; a solid rectangular bar is not equivalent.
3. Source-bound assembly creation and insertion, then fixed connections, three revolute joints, one slider joint, limits and independent motion verification.
4. Repeatable source updates and regeneration checks. Additional plane orientations depend on the chosen mechanical layout.

This is a code audit, not a claim that every supported combination has been exercised live. The robotic design must separately establish loads, drive sizing, reach, travel, clearances and manufacturability.

## Reliability limits

Native dependencies include runtime constructor registries, typed field IDs, editor model state, native node allocation and transaction sequencing. The browser/session interface is not a public stable API. Unsupported builds, ambiguous references and mismatched definitions must fail before writes. Exact preflight is not server-side atomic compare-and-set; concurrent human edits still require inspection and reconciliation. No rate-limit or quota exemption is claimed.
