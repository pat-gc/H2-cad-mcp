FeatureScript 3083;
import(path : "onshape/std/common.fs", version : "3083.0");

export function build(context is Context, id is Id)
{
    var outline = newSketch(context, id + "Outline", {
        "sketchPlane" : qCreatedBy(makeId("Top"), EntityType.FACE) });
    skRectangle(outline, "box", {
        "firstCorner" : vector(0, 0) * millimeter,
        "secondCorner" : vector(40, 20) * millimeter });
    skSolve(outline);
    extrude(context, id + "Solid", {
        "entities" : qSketchRegion(id + "Outline"),
        "endBound" : BoundingType.BLIND,
        "depth" : 5 * millimeter });
}
