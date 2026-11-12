# Disposable Part Studio depth edit handoff

This is a candidate for the designated live testing agent only. It changes the
saved `Extrude 1` depth from 25 mm to 5 mm in the authorized disposable Part
Studio. It does not create features or establish full native geometry status.

## Before the one write

1. Install the reviewed five-patch Native fork with `scripts/bootstrap.py` or
   confirm its fifth tree is `0f89502a9661f2191a712756775403cbadde06df`.
   Stop the existing local bridge process through its normal control and start
   the installed fork's bridge process. Reload the installed extension through
   the browser extension manager, then select Connect in its popup. Do not
   print, copy, or share the pairing token.
2. Check authenticated bridge `/health` read-only. Require server capability
   `h2_depth_edit_server_v1`, `extension_connected=true`, and connected
   extension capability `h2_depth_edit_page_v1`. The H2 command checks these
   again before creating any journal intent. Native state must also report
   `h2DepthEdit.contract=h2-depth-edit-page-v1` and `supported=true`.
3. Use one exact editor tab for
   `f5a8353dc826a9ec52106138/a3baadfcc7e36a50134951d6/a2761fa52794bee99354ae96`.
   Confirm connected and idle. Read native state afresh. Check `Extrude 1` is
   still the saved solid/new/blind feature with depth `25 mm`, the sketch and
   unrelated features are present, and `editingFeatureId` is null. The old
   feature ID and revisions in private fixture files are observations, not
   reusable bindings.
4. Use a persistent local journal path (for example,
   `upstream/onshape-native/.runtime/h2cad-depth.sqlite`). Ensure it has no
   unresolved intent for this target. Do not use a temporary path that will be
   discarded after the test.

## One candidate invocation

Run from the H2 project root, substituting only the fresh tab and feature IDs:

```powershell
.venv\Scripts\h2cad.exe experimental-depth-edit `
  --did f5a8353dc826a9ec52106138 `
  --wid a3baadfcc7e36a50134951d6 `
  --eid a2761fa52794bee99354ae96 `
  --bridge-config upstream\onshape-native\.runtime\bridge.json `
  --tab-id <fresh-exact-tab-id> `
  --journal upstream\onshape-native\.runtime\h2cad-depth.sqlite `
  --feature-id <fresh-extrude-feature-id> --from-mm 25 --to-mm 5
```

The command reads current state, durably records the intended edit, submits
one BeginEdit/SpecifyFeature/Commit transaction through the authenticated
editor bridge, then independently rereads the entire model tree. Success means
the tree matches exactly except the depth expression/value and the element
revision advanced. It reports `geometry_verified=false` and
`ui_editability_verified=false` until separate UI inspection.

If it reports an unknown outcome, inspect the editor and the journal. Do not
rerun the command or undo/redo automatically. If the browser or bridge times
out, the original write may still be running.
Use `h2cad reconcile <op_id> --journal <same-path> --bridge-config <same-config>
--tab-id <fresh-exact-tab-id>` for a read-only check of an uncertain
experimental intent. It observes the intent only when the current connected,
idle tree exactly matches the journaled expected tree at a changed revision.

## Independent UI verification

In the ordinary Onshape editor, confirm one solid Part 1 remains, reopen
`Extrude 1` and observe depth 5 mm and `Face of Sketch 1`, then cancel without
changes. Confirm `Sketch 1` and any unrelated features remain in order. Record
fresh document and element revisions, the exact feature IDs, screenshot or
structured UI observations, and any regeneration error. These UI observations
are separate from native definition verification.
