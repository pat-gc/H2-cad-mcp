FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");

// Concept-only toy car: eight bodies in one Part Studio, without assembly mates.
export function build(context is Context, id is Id)
{
    variable(context, "length", 180 * millimeter);
    variable(context, "width", 90 * millimeter);
    variable(context, "bodyHeight", 37 * millimeter);
    variable(context, "wheelbase", 130 * millimeter);
    variable(context, "wheelRadius", 14 * millimeter);
    variable(context, "wheelThickness", 12 * millimeter);
    variable(context, "axleRadius", 4 * millimeter);

    cPlane(context, id + "Chassis height", {
        "entities" : qCreatedBy(makeId("Top"), EntityType.FACE),
        "offset" : 20 * millimeter });
    var chassis = newSketch(context, id + "Chassis sketch", {
        "sketchPlane" : qCreatedBy(id + "Chassis height", EntityType.FACE) });
    skRectangle(chassis, "outline", {
        "firstCorner" : vector(-#width / 2, -#length / 2),
        "secondCorner" : vector(#width / 2, #length / 2) });
    skSolve(chassis);
    extrude(context, id + "Chassis", {
        "entities" : qSketchRegion(id + "Chassis sketch"),
        "endBound" : BoundingType.BLIND, "depth" : 8 * millimeter });

    cPlane(context, id + "Body height", {
        "entities" : qCreatedBy(makeId("Top"), EntityType.FACE),
        "offset" : 28 * millimeter });
    var body = newSketch(context, id + "Body sketch", {
        "sketchPlane" : qCreatedBy(id + "Body height", EntityType.FACE) });
    skRectangle(body, "outline", {
        "firstCorner" : vector(-40, -60) * millimeter,
        "secondCorner" : vector(40, 60) * millimeter });
    skSolve(body);
    extrude(context, id + "Body", {
        "entities" : qSketchRegion(id + "Body sketch"),
        "endBound" : BoundingType.BLIND, "depth" : #bodyHeight });

    cPlane(context, id + "Axle left plane", {
        "entities" : qCreatedBy(makeId("Right"), EntityType.FACE),
        "offset" : -55 * millimeter });
    var axle = newSketch(context, id + "Axle sketch", {
        "sketchPlane" : qCreatedBy(id + "Axle left plane", EntityType.FACE) });
    skCircle(axle, "front", {
        "center" : vector(#wheelbase / 2, 15 * millimeter),
        "radius" : #axleRadius });
    skCircle(axle, "rear", {
        "center" : vector(-#wheelbase / 2, 15 * millimeter),
        "radius" : #axleRadius });
    skSolve(axle);
    extrude(context, id + "Axles", {
        "entities" : qSketchRegion(id + "Axle sketch"),
        "endBound" : BoundingType.BLIND, "depth" : 110 * millimeter });

    cPlane(context, id + "Wheel left plane", {
        "entities" : qCreatedBy(makeId("Right"), EntityType.FACE),
        "offset" : -#width / 2 - #wheelThickness });
    var leftWheels = newSketch(context, id + "Left wheel sketch", {
        "sketchPlane" : qCreatedBy(id + "Wheel left plane", EntityType.FACE) });
    skCircle(leftWheels, "front", {
        "center" : vector(#wheelbase / 2, 15 * millimeter),
        "radius" : #wheelRadius });
    skCircle(leftWheels, "rear", {
        "center" : vector(-#wheelbase / 2, 15 * millimeter),
        "radius" : #wheelRadius });
    skSolve(leftWheels);
    extrude(context, id + "Left wheels", {
        "entities" : qSketchRegion(id + "Left wheel sketch"),
        "endBound" : BoundingType.BLIND, "depth" : #wheelThickness });

    cPlane(context, id + "Wheel right plane", {
        "entities" : qCreatedBy(makeId("Right"), EntityType.FACE),
        "offset" : #width / 2 });
    var rightWheels = newSketch(context, id + "Right wheel sketch", {
        "sketchPlane" : qCreatedBy(id + "Wheel right plane", EntityType.FACE) });
    skCircle(rightWheels, "front", {
        "center" : vector(#wheelbase / 2, 15 * millimeter),
        "radius" : #wheelRadius });
    skCircle(rightWheels, "rear", {
        "center" : vector(-#wheelbase / 2, 15 * millimeter),
        "radius" : #wheelRadius });
    skSolve(rightWheels);
    extrude(context, id + "Right wheels", {
        "entities" : qSketchRegion(id + "Right wheel sketch"),
        "endBound" : BoundingType.BLIND, "depth" : #wheelThickness });
}
