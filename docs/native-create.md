# Native feature creation: first browser editor slice

The accepted FSGen car plan contains 22 separate definitions: seven variables,
five offset planes, five sketches and five extrusions. Its `feature_json` bodies
are standard feature JSON templates. They cannot be submitted as native editor
RPC payloads. The tested local car is a single custom feature, so it does not
establish this separate-feature path.

## First compile step

`stage_minimal_pair` now reads an actual `compile_fsgen` snapshot for
`fixtures/native/minimal_plate.fs`. It accepts exactly one new Top-plane
rectangle sketch followed by a dependent solid/new/blind extrusion with a
literal millimeter depth. Its normalized geometry is 40 × 20 × 5 mm. Local
OpenCascade validation returned one body, bounding box 40 × 20 × 5 mm and
4,000 mm³. It rejects changed plane, region dependency, mode, construction
flag or unresolved depth expression. The returned blueprint explicitly has
`write_ready=false`; it is semantic input to a future editor transaction,
not a fake native command.

## Live read-only evidence

The designated tester's blank temporary Part Studio had a connected, idle
`bsedit.GBTMModel`, four default features, a rollback insertion node, and no
user features. Current serializer constructors resolve the typed edit list,
insertion, sketch, query and parameter classes. Creating a local
`bsedit.GBTMSketch` or parameter object produces a fresh `nodeId`, while
`featureId` and `parameterId` remain empty. This is evidence of native node ID
allocation only; it does not establish a feature ID allocator. `ui_inspect`
exposed no stable labeled Sketch control. The Top feature ID and node ID are
visible, but no supported read response has bound them to a native face query.
The captured `GBTUiAddFeatureCall` shows typed insertions and subsequent
`GBTUiCommit`/`GBTUiSpecifyFeature` commands, but anonymized IDs and opaque
deterministic face/region IDs make it unsuitable for replay.

The first read-only method-name probe hung in the editor and returned no
allocator evidence. The compatibility patch now removes that traversal; its
remaining constructor check is narrow and read-only. Do not retry the earlier
probe in the stuck tab. The normal toolbar has a live DOM-grounded Sketch
control (`command-id="newSketch"`), so Onshape can allocate the feature ID
through its ordinary editor lifecycle. The designated tester is observing
that path in the isolated temporary Part Studio and will stop before drawing.

## Creation gate

Do not send `GBTUiAddFeatureCall` until the live editor supplies an actual
feature ID allocator, exact insertion location, a Top face query, parameter
bindings and a verified create/commit/readback contract. Then bind the
resulting sketch region for the extrusion from the saved feature's own current
state. Acknowledgement alone does not establish an editable sketch or solid.
The isolated temporary Part Studio may be used for the first reviewed live
proof; the existing car Part Studio and Feature Studio stay intact.
