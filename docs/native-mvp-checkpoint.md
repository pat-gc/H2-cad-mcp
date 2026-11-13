# Empty-studio native plate checkpoint candidate

Patch 26 adds an explicit `h2cad_create_target` binding to the paired bridge configuration and a single CLI sequence: local FSGen/OpenCascade validation, normal Sketch/Top initiation, source rectangle population and Save, normal selection of the saved sketch and Extrude initiation, source depth population and Save, then exact saved-definition readback. It uses the same FSGen text throughout. It does not use REST or a custom feature for CAD writes.

The authorized empty checkpoint target is document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`, Part Studio `1926791d173990d5d45f70ef` (`Native MVP Checkpoint - Empty`). The older verified plate and existing car remain separate. The paired bridge config must include:

```json
"h2cad_create_target": {"did":"4e078dec822b4e509616b1cb","wid":"af0627de07264acf086e646a","eid":"1926791d173990d5d45f70ef"}
```

After staging the exact reviewed 26-patch Native tree, restart the paired Python broker and reload/reconnect its own browser extension. Verify server capability `h2_native_begin_source_extrude_server_v1` and loaded page capability `h2_native_begin_source_extrude_page_v1`. Use the existing private bridge config and its pinned H2 journal; do not print the token. The tester alone runs one command on the confirmed empty target and exact paired tab:

```powershell
h2cad experimental-create-plate fixtures/native/minimal_plate.fs --did 4e078dec822b4e509616b1cb --wid af0627de07264acf086e646a --eid 1926791d173990d5d45f70ef --tab-id 941740760 --bridge-config <paired-config.json> --journal <same-pinned-journal.sqlite>
```

The bridge and H2 both reject another configured target, and H2 journals each possible editor mutation before sending it. A failure or ambiguous outcome stops the sequence; rerunning the command on a nonempty target is refused. Verify the actual saved tree and one solid independently, including 40 × 20 × 5 mm mass properties, then reopen the source Sketch and Extrude in the ordinary UI and edit/restore a dimension. The CLI's `native_definitions_observed` result alone does not claim solid geometry or human editability.

The supported first slice is one Top-plane origin rectangle with four native lines, eleven constraints including internal point Fix, literal editable width/height dimensions, and one blind solid extrusion. The new Extrude selection may be `GBTMIndividualSketchRegionQuery` only when it identifies the exact source Sketch and that Sketch has one validated closed rectangle; unrelated or multiple-profile sketches fail. An editor default depth already equal to the source depth is rejected before any mutation because a commit-only extrusion has not been proved. Variables, offset planes, circles, source expressions and multi-body additions remain outside this first slice and are required before the full car workflow.
