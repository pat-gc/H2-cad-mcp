FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");

// Robot capability fixture, not the complete arm or a released bearing fit.
// Witness overlaps the cutting tools in Z: exact booleanScope must preserve it.
export function build(context is Context, id is Id)
{
    variable(context, "carrierThickness", 12 * millimeter);
    cPlane(context, id + "Carrier plane", {
        "entities" : qCreatedBy(makeId("Top"), EntityType.FACE),
        "offset" : 0 * millimeter });
    var outline = newSketch(context, id + "Carrier outline", {
        "sketchPlane" : qCreatedBy(id + "Carrier plane", EntityType.FACE) });
    skRectangle(outline, "outline", {
        "firstCorner" : vector(-30, -30) * millimeter,
        "secondCorner" : vector(30, 30) * millimeter });
    skSolve(outline);
    extrude(context, id + "Carrier blank", {
        "entities" : qSketchRegion(id + "Carrier outline"),
        "operationType" : NewBodyOperationType.NEW,
        "endBound" : BoundingType.BLIND,
        "depth" : #carrierThickness });

    cPlane(context, id + "Witness plane", {
        "entities" : qCreatedBy(makeId("Top"), EntityType.FACE),
        "offset" : 20 * millimeter });
    var witness = newSketch(context, id + "Witness outline", {
        "sketchPlane" : qCreatedBy(id + "Witness plane", EntityType.FACE) });
    skRectangle(witness, "outline", {
        "firstCorner" : vector(-30, -30) * millimeter,
        "secondCorner" : vector(30, 30) * millimeter });
    skSolve(witness);
    extrude(context, id + "Untouched witness", {
        "entities" : qSketchRegion(id + "Witness outline"),
        "operationType" : NewBodyOperationType.NEW,
        "endBound" : BoundingType.BLIND, "depth" : 3 * millimeter });

    var holes = newSketch(context, id + "Carrier holes", {
        "sketchPlane" : qCreatedBy(id + "Carrier plane", EntityType.FACE) });
    skCircle(holes, "scopeProbe", {"center" : vector(10, 5) * millimeter, "radius" : 3 * millimeter});
    skSolve(holes);
    extrude(context, id + "Carrier through bores", {
        "entities" : qSketchRegion(id + "Carrier holes"),
        "operationType" : NewBodyOperationType.REMOVE,
        "endBound" : BoundingType.BLIND, "depth" : 24 * millimeter,
        "defaultScope" : false,
        "booleanScope" : qCreatedBy(id + "Carrier blank", EntityType.BODY) });
}
