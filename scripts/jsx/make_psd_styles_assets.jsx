/**
 * make_psd_styles_assets.jsx - Photoshop script that authors the layer-style
 * documents under samples/assets/psd_styles/ (one small document per case:
 * a rounded-rectangle pixel layer "shape" over a white Background, a text
 * layer for the text case, a Levels adjustment layer in a CMYK and a Lab
 * document). The styles are set through the layer's effects descriptor so
 * every value below is written exactly; Photoshop adds its own disabled
 * defaults for the other styles and drops the contour keys of a bevel whose
 * contour is off (the `shape0` cases).
 *
 * Run from PowerShell through COM (Photoshop 2026 on the authoring machine):
 *   $ps = New-Object -ComObject Photoshop.Application.200
 *   $ps.DoJavaScript("var OUT_DIR = '<repo>/samples/assets/psd_styles';" +
 *                    (Get-Content scripts/jsx/make_psd_styles_assets.jsx -Raw))
 * The returned string is the log. Without OUT_DIR the folder is derived from
 * the script's location (File > Scripts > Browse works too).
 *
 * samples/models/import/psd_styles_corpus.aep is After Effects 2026's import
 * of these files (scripts/jsx/psd_styles_corpus_fixture.jsx).
 */
(function () {
    var cID = charIDToTypeID, sID = stringIDToTypeID;
    var OUT = (typeof OUT_DIR !== "undefined") ? OUT_DIR
        : new File($.fileName).parent.parent.parent.fsName + "/samples/assets/psd_styles";
    var log = [];
    function w(s) { log.push(s); }

    // ---- descriptor helpers ---------------------------------------------
    function rgb(c) {
        var d = new ActionDescriptor();
        d.putDouble(cID("Rd  "), c[0]); d.putDouble(cID("Grn "), c[1]); d.putDouble(cID("Bl  "), c[2]);
        return d;
    }
    function contour(spec) {
        var d = new ActionDescriptor();
        d.putString(cID("Nm  "), spec[0]);
        var list = new ActionList();
        for (var i = 0; i < spec[1].length; i++) {
            var p = new ActionDescriptor();
            p.putDouble(cID("Hrzn"), spec[1][i][0]); p.putDouble(cID("Vrtc"), spec[1][i][1]);
            list.putObject(cID("CrPt"), p);
        }
        d.putList(cID("Crv "), list);
        return d;
    }
    var LINEAR = ["linear", [[0, 0], [255, 255]]];
    var DOUBLE_RING = ["double ring", [[0, 0], [64, 255], [128, 40], [192, 255], [255, 0]]];
    var SOFT_S = ["soft s", [[0, 0], [70, 30], [185, 225], [255, 255]]];
    function blend(d, key, mode) { d.putEnumerated(cID(key), cID("BlnM"), sID(mode)); }
    function prc(d, key, v) { d.putUnitDouble(cID(key), cID("#Prc"), v); }
    function pxl(d, key, v) { d.putUnitDouble(cID(key), cID("#Pxl"), v); }
    function ang(d, key, v) { d.putUnitDouble(cID(key), cID("#Ang"), v); }
    function common(d, enabled) {
        d.putBoolean(cID("enab"), enabled !== false);
        d.putBoolean(sID("present"), true);
        d.putBoolean(sID("showInDialog"), true);
    }

    // Stroke: position OutF/InsF/CtrF, size px, colour, enabled (default true).
    function stroke(o) {
        var d = new ActionDescriptor(); common(d, o.enabled);
        d.putEnumerated(cID("Styl"), cID("FStl"), cID(o.position));
        d.putEnumerated(cID("PntT"), cID("FrFl"), cID("SClr"));
        blend(d, "Md  ", "normal"); prc(d, "Opct", 100); pxl(d, "Sz  ", o.size);
        d.putObject(cID("Clr "), cID("RGBC"), rgb(o.color));
        d.putBoolean(sID("overprint"), false);
        return d;
    }
    // Bevel: style OtrB/InrB/Embs/PlEb/strokeEmboss, technique SfBL/PrBL/Slmt,
    // size px, soften px, gloss contour + antialiasGloss, contour (useShape)
    // + antialias + range.
    function bevel(o) {
        var d = new ActionDescriptor(); common(d, true);
        blend(d, "hglM", "screen"); d.putObject(cID("hglC"), cID("RGBC"), rgb([255, 255, 255])); prc(d, "hglO", 75);
        blend(d, "sdwM", "multiply"); d.putObject(cID("sdwC"), cID("RGBC"), rgb([0, 0, 0])); prc(d, "sdwO", 75);
        d.putEnumerated(cID("bvlT"), cID("bvlT"), cID(o.technique));
        d.putEnumerated(cID("bvlS"), cID("BESl"), o.style === "strokeEmboss" ? sID("strokeEmboss") : cID(o.style));
        d.putBoolean(cID("uglg"), false); ang(d, "lagl", 120); ang(d, "Lald", 30); prc(d, "srgR", 100);
        pxl(d, "blur", o.size);
        d.putEnumerated(cID("bvlD"), cID("BESs"), cID("In  "));
        d.putObject(cID("TrnS"), cID("ShpC"), contour(o.gloss || LINEAR));
        d.putBoolean(sID("antialiasGloss"), !!o.antialiasGloss);
        pxl(d, "Sftn", o.soften || 0);
        d.putBoolean(sID("useShape"), !!o.useShape);
        if (o.contour) {
            d.putObject(cID("MpgS"), cID("ShpC"), contour(o.contour));
            d.putBoolean(cID("AntA"), !!o.antialias);
            prc(d, "Inpr", o.range);
        }
        d.putBoolean(sID("useTexture"), false);
        return d;
    }
    // Outer/inner glow: colour, opacity %, technique SfBL/PrBL, spread px,
    // size px, antialias, contour, range %.
    function glow(o, inner) {
        var d = new ActionDescriptor(); common(d, true);
        blend(d, "Md  ", "screen"); d.putObject(cID("Clr "), cID("RGBC"), rgb(o.color)); prc(d, "Opct", o.opacity);
        d.putEnumerated(cID("GlwT"), cID("BETE"), cID(o.technique || "SfBL"));
        pxl(d, "Ckmt", o.spread || 0); pxl(d, "blur", o.size); prc(d, "Nose", 0); prc(d, "ShdN", 0);
        d.putBoolean(cID("AntA"), !!o.antialias);
        d.putObject(cID("TrnS"), cID("ShpC"), contour(o.contour || LINEAR));
        prc(d, "Inpr", o.range || 50);
        if (inner) { d.putEnumerated(cID("glwS"), cID("IGSr"), cID("SrcE")); }
        return d;
    }
    // Satin: colour, opacity %, angle, distance px, size px, contour.
    function satin(o) {
        var d = new ActionDescriptor(); common(d, true);
        blend(d, "Md  ", "multiply"); d.putObject(cID("Clr "), cID("RGBC"), rgb(o.color));
        d.putBoolean(cID("AntA"), false); d.putBoolean(cID("Invr"), false); prc(d, "Opct", o.opacity);
        ang(d, "lagl", o.angle); pxl(d, "Dstn", o.distance); pxl(d, "blur", o.size);
        d.putObject(cID("MpgS"), cID("ShpC"), contour(o.contour || LINEAR));
        return d;
    }
    function applyStyles(fx) {
        var root = new ActionDescriptor();
        prc(root, "Scl ", 100);
        root.putBoolean(sID("masterFXSwitch"), true);
        var keys = ["OrGl", "FrFX", "IrGl", "ebbl", "ChFX"];
        for (var i = 0; i < keys.length; i++) {
            if (fx[keys[i]]) { root.putObject(cID(keys[i]), cID(keys[i]), fx[keys[i]]); }
        }
        var d = new ActionDescriptor(); var r = new ActionReference();
        r.putProperty(cID("Prpr"), cID("Lefx")); r.putEnumerated(cID("Lyr "), cID("Ordn"), cID("Trgt"));
        d.putReference(cID("null"), r);
        d.putObject(cID("T   "), cID("Lefx"), root);
        executeAction(cID("setd"), d, DialogModes.NO);
    }
    // Needs a normal active layer: the command is unavailable on the Background.
    function setGlobalLight(angle, altitude) {
        var d = new ActionDescriptor(); var r = new ActionReference();
        r.putProperty(cID("Prpr"), sID("globalAngle")); r.putEnumerated(cID("Dcmn"), cID("Ordn"), cID("Trgt"));
        d.putReference(cID("null"), r);
        var t = new ActionDescriptor();
        t.putInteger(sID("globalAngle"), angle); t.putInteger(sID("globalAltitude"), altitude);
        d.putObject(cID("T   "), sID("globalAngle"), t);
        executeAction(cID("setd"), d, DialogModes.NO);
    }

    // ---- layers ---------------------------------------------------------
    function roundedRectLayer(doc, box, radius, color) {
        var d = new ActionDescriptor(); var r = new ActionReference();
        r.putClass(sID("contentLayer")); d.putReference(cID("null"), r);
        var u = new ActionDescriptor();
        var type = new ActionDescriptor(); type.putObject(cID("Clr "), cID("RGBC"), rgb(color));
        u.putObject(cID("Type"), sID("solidColorLayer"), type);
        var shp = new ActionDescriptor();
        pxl(shp, "Top ", box[1]); pxl(shp, "Left", box[0]); pxl(shp, "Btom", box[3]); pxl(shp, "Rght", box[2]);
        var corners = ["topLeft", "topRight", "bottomLeft", "bottomRight"];
        for (var i = 0; i < corners.length; i++) { shp.putUnitDouble(sID(corners[i]), cID("#Pxl"), radius); }
        u.putObject(cID("Shp "), cID("Rctn"), shp);
        var ss = new ActionDescriptor();
        ss.putInteger(sID("strokeStyleVersion"), 2);
        ss.putBoolean(sID("strokeEnabled"), false); ss.putBoolean(sID("fillEnabled"), true);
        u.putObject(sID("strokeStyle"), sID("strokeStyle"), ss);
        d.putObject(cID("Usng"), sID("contentLayer"), u);
        executeAction(cID("Mk  "), d, DialogModes.NO);
        doc.activeLayer.rasterize(RasterizeType.ENTIRELAYER);
        doc.activeLayer.name = "shape";
    }
    function textLayer(doc, text, color) {
        var layer = doc.artLayers.add();
        layer.kind = LayerKind.TEXT;
        layer.name = text;
        var t = layer.textItem;
        t.kind = TextType.POINTTEXT;
        try { t.font = "Arial-BoldMT"; } catch (e) { t.font = "ArialMT"; }
        t.size = 48;
        t.contents = text;
        var c = new SolidColor(); c.rgb.red = color[0]; c.rgb.green = color[1]; c.rgb.blue = color[2];
        t.color = c;
        t.position = [18, 70];
    }
    function levelsLayer(doc) {
        var d = new ActionDescriptor(); var r = new ActionReference();
        r.putClass(cID("AdjL")); d.putReference(cID("null"), r);
        var u = new ActionDescriptor(); var lv = new ActionDescriptor();
        lv.putEnumerated(sID("presetKind"), sID("presetKindType"), sID("presetKindDefault"));
        u.putObject(cID("Type"), cID("Lvls"), lv);
        d.putObject(cID("Usng"), cID("AdjL"), u);
        executeAction(cID("Mk  "), d, DialogModes.NO);
        doc.activeLayer.name = "levels";
    }
    function newDoc(name, width, height, mode) {
        // The Background layer keeps Photoshop's localized name; readers
        // (After Effects, py_aep) name a true background layer "Background".
        return app.documents.add(width, height, 72, name, mode, DocumentFill.WHITE, 1, BitsPerChannelType.EIGHT);
    }
    function save(doc, name) {
        var o = new PhotoshopSaveOptions();
        o.layers = true; o.alphaChannels = true; o.embedColorProfile = true;
        o.annotations = false; o.spotColors = false;
        var file = new File(OUT + "/" + name + ".psd");
        doc.saveAs(file, o, true, Extension.LOWERCASE);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        return file;
    }
    // Photoshop clamps a scripted stroke size to 1 px; the two `_s0_` cases
    // (what After Effects does with a 0 px stroke) get the size zeroed in the
    // saved file: the 8-byte double after `Sz  UntF#Pxl` in each enabled
    // stroke object (key `FrFX` + type `Objc`) of the effects descriptors.
    function zeroStrokeSize(file) {
        file.encoding = "BINARY";
        file.open("r"); var s = file.read(); file.close();
        var key = "\x00\x00\x00\x00FrFXObjc", tag = "Sz  UntF#Pxl", at = 0, n = 0;
        while ((at = s.indexOf(key, at)) >= 0) {
            var sz = s.indexOf(tag, at) + tag.length;
            s = s.substring(0, sz) + "\x00\x00\x00\x00\x00\x00\x00\x00" + s.substring(sz + 8);
            at = sz; n++;
        }
        file.open("w"); file.write(s); file.close();
        return n;
    }

    // ---- the cases ------------------------------------------------------
    var RED = [200, 60, 40], GREEN = [40, 180, 120], YELLOW = [240, 200, 40];
    var GLOW = [255, 230, 120], SATIN = [20, 20, 60], DARK = [20, 20, 20];
    function se(strokeSpec, bevelSpec) {
        bevelSpec.style = "strokeEmboss";
        return { FrFX: stroke(strokeSpec), ebbl: bevel(bevelSpec) };
    }
    function aa(technique, useShape, antialias, antialiasGloss) {
        return { ebbl: bevel({ style: "OtrB", technique: technique, size: 14, antialiasGloss: antialiasGloss,
            useShape: useShape, contour: DOUBLE_RING, antialias: antialias, range: 70 }) };
    }
    var SHAPE_CASES = [
        ["bevel-emboss-chisel-hard", { ebbl: bevel({ style: "Embs", technique: "PrBL", size: 10 }) }],
        ["bevel-emboss-smooth", { ebbl: bevel({ style: "Embs", technique: "SfBL", size: 10 }) }],
        ["bevel-inner-contour-double-ring-aa-r70", { ebbl: bevel({ style: "InrB", technique: "SfBL", size: 14,
            useShape: true, contour: DOUBLE_RING, antialias: true, range: 70 }) }],
        ["bevel-inner-gloss-double-ring-aa", { ebbl: bevel({ style: "InrB", technique: "SfBL", size: 12,
            gloss: DOUBLE_RING, antialiasGloss: true }) }],
        ["bevel-inner-smooth", { ebbl: bevel({ style: "InrB", technique: "SfBL", size: 10 }) }],
        ["bevel-outer-chisel-hard", { ebbl: bevel({ style: "OtrB", technique: "PrBL", size: 10 }) }],
        ["bevel-outer-chisel-soft", { ebbl: bevel({ style: "OtrB", technique: "Slmt", size: 10 }) }],
        ["bevel-outer-smooth", { ebbl: bevel({ style: "OtrB", technique: "SfBL", size: 10 }) }],
        ["bevel-pillow-chisel-soft", { ebbl: bevel({ style: "PlEb", technique: "Slmt", size: 10 }) }],
        ["bevel-pillow-smooth", { ebbl: bevel({ style: "PlEb", technique: "SfBL", size: 10 }) }],
        ["bevel-stroke-chisel-hard", se({ position: "OutF", size: 6, color: RED }, { technique: "PrBL", size: 10 })],
        ["bevel-stroke-chisel-soft", se({ position: "OutF", size: 6, color: RED }, { technique: "Slmt", size: 10 })],
        ["bevel-stroke-emboss-center-stroke-chisel-soft",
            se({ position: "CtrF", size: 10, color: GREEN }, { technique: "Slmt", size: 8 })],
        ["bevel-stroke-emboss-inside-stroke",
            se({ position: "InsF", size: 8, color: YELLOW }, { technique: "SfBL", size: 6 })],
        ["bevel-stroke-smooth", se({ position: "OutF", size: 6, color: RED }, { technique: "SfBL", size: 10 })],
        ["combo-bevel-satin-glows-stroke", {
            OrGl: glow({ color: GLOW, opacity: 85, size: 10 }),
            FrFX: stroke({ position: "OutF", size: 3, color: DARK }),
            IrGl: glow({ color: [255, 255, 255], opacity: 50, size: 8 }, true),
            ebbl: bevel({ style: "InrB", technique: "SfBL", size: 8, useShape: true, contour: SOFT_S, antialias: false, range: 50 }),
            ChFX: satin({ color: SATIN, opacity: 40, angle: 19, distance: 11, size: 14, contour: SOFT_S })
        }],
        ["inner-glow-edge-soft", { IrGl: glow({ color: [255, 255, 180], opacity: 85, size: 14 }, true) }],
        ["outer-glow-contour-double-ring-r60",
            { OrGl: glow({ color: GLOW, opacity: 85, size: 24, antialias: true, contour: DOUBLE_RING, range: 60 }) }],
        ["outer-glow-precise-spread40", { OrGl: glow({ color: GLOW, opacity: 85, technique: "PrBL", spread: 40, size: 16 }) }],
        ["outer-glow-soft", { OrGl: glow({ color: GLOW, opacity: 85, size: 12 }) }],
        ["satin-default", { ChFX: satin({ color: SATIN, opacity: 50, angle: 19, distance: 11, size: 14, contour: SOFT_S }) }],
        // Outer-bevel anti-alias flag variants (shape = contour on, anta =
        // contour anti-alias, gloss = gloss contour anti-alias).
        ["aa_outer_PrBL_shape0_anta0_gloss1", aa("PrBL", false, false, true)],
        ["aa_outer_PrBL_shape1_anta0_gloss0", aa("PrBL", true, false, false)],
        ["aa_outer_SfBL_shape1_anta1_gloss0", aa("SfBL", true, true, false)],
        ["aa_outer_SfBL_shape1_anta1_gloss1", aa("SfBL", true, true, true)],
        // Stroke Emboss matrix: stroke position and size, bevel size,
        // technique and soften. A 0 px stroke is what After Effects clamps.
        ["se_ctr_s0_b10_SfBL_f0", se({ position: "CtrF", size: 0, color: RED }, { technique: "SfBL", size: 10 })],
        ["se_ctr_s12_b3_PrBL_f0", se({ position: "CtrF", size: 12, color: RED }, { technique: "PrBL", size: 3 })],
        ["se_ctr_s6_b10_SfBL_f0", se({ position: "CtrF", size: 6, color: RED }, { technique: "SfBL", size: 10 })],
        ["se_in_s6_b10_SfBL_f0", se({ position: "InsF", size: 6, color: RED }, { technique: "SfBL", size: 10 })],
        ["se_out_s0_b10_SfBL_f0", se({ position: "OutF", size: 0, color: RED }, { technique: "SfBL", size: 10 })],
        ["se_out_s6_b10_PrBL_f3", se({ position: "OutF", size: 6, color: RED }, { technique: "PrBL", size: 10, soften: 3 })],
        ["se_out_s6_b10_SfBL_f0", se({ position: "OutF", size: 6, color: RED }, { technique: "SfBL", size: 10 })],
        ["se_out_s6_b10_SfBL_f0_strokeoff",
            se({ position: "OutF", size: 6, color: RED, enabled: false }, { technique: "SfBL", size: 10 })],
        ["se_out_s6_b10_Slmt_f0", se({ position: "OutF", size: 6, color: RED }, { technique: "Slmt", size: 10 })]
    ];

    // ---- run --------------------------------------------------------------
    var savedRuler = app.preferences.rulerUnits, savedType = app.preferences.typeUnits;
    var savedCompat = app.preferences.maximizeCompatibility;
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits = TypeUnits.PIXELS;
    app.preferences.maximizeCompatibility = QueryStateType.ALWAYS;
    new Folder(OUT).create();
    w("start " + app.version + " -> " + OUT);
    try {
        for (var i = 0; i < SHAPE_CASES.length; i++) {
            var name = SHAPE_CASES[i][0];
            try {
                var doc = newDoc(name, 192, 192, NewDocumentMode.RGB);
                roundedRectLayer(doc, [19, 29, 173, 169], 20, [70, 130, 200]);
                setGlobalLight(90, 30);
                applyStyles(SHAPE_CASES[i][1]);
                var file = save(doc, name);
                w("OK " + name + (name.indexOf("_s0_") >= 0 ? " (stroke size zeroed x" + zeroStrokeSize(file) + ")" : ""));
            } catch (e1) { w("FAIL " + name + ": " + e1 + " line " + e1.line); }
        }
        try {
            var tdoc = newDoc("text-with-layer-styles", 320, 96, NewDocumentMode.RGB);
            textLayer(tdoc, "STYLED", [30, 30, 30]);
            setGlobalLight(90, 30);
            applyStyles({ FrFX: stroke({ position: "OutF", size: 2, color: [40, 20, 0] }),
                ebbl: bevel({ style: "InrB", technique: "SfBL", size: 4 }) });
            save(tdoc, "text-with-layer-styles");
            w("OK text-with-layer-styles");
        } catch (e2) { w("FAIL text-with-layer-styles: " + e2 + " line " + e2.line); }
        var modes = [["cmyk8-levels", NewDocumentMode.CMYK], ["lab8-levels", NewDocumentMode.LAB]];
        for (var m = 0; m < modes.length; m++) {
            try {
                var adoc = newDoc(modes[m][0], 96, 96, modes[m][1]);
                levelsLayer(adoc);
                setGlobalLight(90, 30);
                save(adoc, modes[m][0]);
                w("OK " + modes[m][0]);
            } catch (e3) { w("FAIL " + modes[m][0] + ": " + e3 + " line " + e3.line); }
        }
    } finally {
        app.preferences.rulerUnits = savedRuler;
        app.preferences.typeUnits = savedType;
        app.preferences.maximizeCompatibility = savedCompat;
    }
    w("DONE");
    return log.join("\n");
})();
