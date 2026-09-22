/**
 * Build the value_at_time edge-case sample.
 *
 * Comp "resample": path keyframe pairs holding DIFFERENT vertex counts,
 * which After Effects blends by resampling the shorter path up to the
 * longer one. The spread of count pairs (and one curved and one open
 * case) is what pins down the rule; both keys are LINEAR so the progress
 * is the plain time fraction and the resampled shape can be solved for
 * exactly from a single sampled frame.
 *
 * Comp "orient_speed": Orientation eases carrying a non-zero SPEED,
 * across overshoot magnitudes, signs, influences, durations and rotation
 * sizes - the configuration only reachable through the Keyframe Velocity
 * dialog.
 *
 * Ground truth is exported afterwards by export_value_at_time.jsx.
 */

var ROOT = "C:/Users/aurore.delaunay/git/py-aep";
var SOURCE = ROOT + "/samples/models/property/keyframe_single.aep";
var OUT_AEP = ROOT + "/samples/models/property/property_vat_edge_cases.aep";
var LOG = Folder.myDocuments.fsName + "/build_vat_edge_cases_log.txt";

var logFile = new File(LOG);
logFile.open("w");
function log(m) { logFile.writeln(m); $.writeln(m); }

function mkShape(verts, inT, outT, closed) {
    var s = new Shape();
    s.vertices = verts;
    if (inT) s.inTangents = inT;
    if (outT) s.outTangents = outT;
    s.closed = closed;
    return s;
}

function zeros(n) {
    var a = [];
    for (var i = 0; i < n; i++) a.push([0, 0]);
    return a;
}

/** A shape layer carrying one animated path. */
function addPathLayer(comp, name, shapeA, shapeB) {
    var layer = comp.layers.addShape();
    layer.name = name;
    var grp = layer.property("ADBE Root Vectors Group")
                   .addProperty("ADBE Vector Group");
    var pathGroup = grp.property("ADBE Vectors Group")
                       .addProperty("ADBE Vector Shape - Group");
    var path = pathGroup.property("ADBE Vector Shape");
    path.setValueAtTime(0, shapeA);
    path.setValueAtTime(2, shapeB);
    path.setInterpolationTypeAtKey(1, KeyframeInterpolationType.LINEAR,
                                      KeyframeInterpolationType.LINEAR);
    path.setInterpolationTypeAtKey(2, KeyframeInterpolationType.LINEAR,
                                      KeyframeInterpolationType.LINEAR);
    log("  " + name + " keys=" + path.numKeys);
    return path;
}

function addOrientLayer(comp, name, endAngles, dt, outSpeed, outInf, inSpeed, inInf) {
    var layer = comp.layers.addSolid([1, 0, 0], name, 200, 100, 1.0);
    layer.threeDLayer = true;
    var ori = layer.property("ADBE Transform Group").property("ADBE Orientation");
    ori.setValueAtTime(0, [0, 0, 0]);
    ori.setValueAtTime(dt, endAngles);
    ori.setTemporalEaseAtKey(1, [new KeyframeEase(0, outInf)],
                                [new KeyframeEase(outSpeed, outInf)]);
    ori.setTemporalEaseAtKey(2, [new KeyframeEase(inSpeed, inInf)],
                                [new KeyframeEase(0, inInf)]);
    var e1 = ori.keyOutTemporalEase(1)[0];
    var e2 = ori.keyInTemporalEase(2)[0];
    log("  " + name + " out=(" + e1.speed + "," + e1.influence + ")"
        + " in=(" + e2.speed + "," + e2.influence + ")");
    return ori;
}

try {
    log("start");
    var proj = app.open(new File(SOURCE));

    // ---- Comp 1: path vertex-count mismatch ----------------------------
    var rs = proj.items.addComp("resample", 400, 300, 1.0, 2.5, 24);

    var tri = [[-100, -60], [100, -60], [100, 60]];
    var quad = [[-100, -60], [100, -60], [100, 60], [-100, 60]];
    var five = [[-90, -80], [70, -50], [110, 40], [-20, 90], [-120, 20]];
    var eight = [[-90, -80], [-20, -95], [70, -50], [110, -5], [110, 40],
                 [20, 75], [-20, 90], [-120, 20]];
    var seven = [[-90, -80], [-10, -90], [70, -50], [110, 40], [20, 75],
                 [-20, 90], [-120, 20]];
    var two = [[-100, -60], [100, 60]];
    var three_b = [[-60, -40], [80, -20], [40, 70]];

    addPathLayer(rs, "r3to5", mkShape(tri, zeros(3), zeros(3), true),
                 mkShape(five, zeros(5), zeros(5), true));
    addPathLayer(rs, "r3to8", mkShape(tri, zeros(3), zeros(3), true),
                 mkShape(eight, zeros(8), zeros(8), true));
    addPathLayer(rs, "r4to7", mkShape(quad, zeros(4), zeros(4), true),
                 mkShape(seven, zeros(7), zeros(7), true));
    addPathLayer(rs, "r2to5", mkShape(two, zeros(2), zeros(2), true),
                 mkShape(five, zeros(5), zeros(5), true));
    addPathLayer(rs, "r5to3", mkShape(five, zeros(5), zeros(5), true),
                 mkShape(three_b, zeros(3), zeros(3), true));
    // Curved short side: a de Casteljau split and a straight-line midpoint
    // land in different places here.
    addPathLayer(rs, "r3to5curved",
                 mkShape(tri,
                         [[-40, 30], [-50, -20], [10, -60]],
                         [[40, -30], [50, 20], [-10, 60]],
                         true),
                 mkShape(five, zeros(5), zeros(5), true));
    addPathLayer(rs, "r3to5open", mkShape(tri, zeros(3), zeros(3), false),
                 mkShape(five, zeros(5), zeros(5), false));
    log("resample comp done, layers=" + rs.numLayers);

    // ---- Comp 2: Orientation ease speeds --------------------------------
    var os = proj.items.addComp("orient_speed", 400, 300, 1.0, 5.0, 24);
    addOrientLayer(os, "sp_small", [45, 90, 30], 2, 5, 50, 5, 50);
    addOrientLayer(os, "sp_large", [45, 90, 30], 2, 200, 33, 200, 33);
    addOrientLayer(os, "sp_negative", [45, 90, 30], 2, -30, 50, 40, 50);
    addOrientLayer(os, "sp_asym_inf", [45, 90, 30], 2, 40, 20, 10, 80);
    addOrientLayer(os, "sp_short_dt", [45, 90, 30], 0.5, 40, 50, 20, 50);
    addOrientLayer(os, "sp_long_dt", [45, 90, 30], 4, 40, 50, 20, 50);
    addOrientLayer(os, "sp_small_rot", [3, 5, 2], 2, 40, 50, 20, 50);
    addOrientLayer(os, "sp_one_side", [45, 90, 30], 2, 60, 50, 0, 50);
    log("orient comp done, layers=" + os.numLayers);

    proj.save(new File(OUT_AEP));
    log("saved " + OUT_AEP);
    log("DONE");
} catch (e) {
    log("ERROR: " + e.toString() + " line " + e.line);
    log("DONE");
}
logFile.close();
