FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");

// Modeling primitive only: square tube, NOT a 2020 T-slot extrusion.
// No material, load rating, slot-nut interface or manufacturing tolerance implied.
export function build(context is Context, id is Id)
{
    variable(context, "outerSize", 20 * millimeter);
    variable(context, "wallThickness", 2 * millimeter);
    variable(context, "tubeLength", 220 * millimeter);
    cPlane(context, id + "Tube plane", {
        "entities" : qCreatedBy(makeId("Top"), EntityType.FACE),
        "offset" : 0 * millimeter });
    var outside = newSketch(context, id + "Tube outside", {
        "sketchPlane" : qCreatedBy(id + "Tube plane", EntityType.FACE) });
    skRectangle(outside, "outline", {
        "firstCorner" : vector(-#outerSize / 2, -#outerSize / 2),
        "secondCorner" : vector(#outerSize / 2, #outerSize / 2) });
    skSolve(outside);
    extrude(context, id + "Tube blank", {
        "entities" : qSketchRegion(id + "Tube outside"),
        "operationType" : NewBodyOperationType.NEW,
        "endBound" : BoundingType.BLIND, "depth" : #tubeLength });
    var inside = newSketch(context, id + "Tube bore", {
        "sketchPlane" : qCreatedBy(id + "Tube plane", EntityType.FACE) });
    skRectangle(inside, "bore", {
        "firstCorner" : vector(-#outerSize / 2 + #wallThickness, -#outerSize / 2 + #wallThickness),
        "secondCorner" : vector(#outerSize / 2 - #wallThickness, #outerSize / 2 - #wallThickness) });
    skSolve(inside);
    extrude(context, id + "Hollow tube", {
        "entities" : qSketchRegion(id + "Tube bore"),
        "operationType" : NewBodyOperationType.REMOVE,
        "endBound" : BoundingType.BLIND, "depth" : #tubeLength,
        "defaultScope" : false,
        "booleanScope" : qCreatedBy(id + "Tube blank", EntityType.BODY) });
}
