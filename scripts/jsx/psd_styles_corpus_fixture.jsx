/**
 * psd_styles_corpus_fixture.jsx - AE 2026 ground truth for the layer-style
 * documents of samples/assets/psd_styles (scripts/jsx/make_psd_styles_assets.jsx):
 * every PSD imported as COMP_CROPPED_LAYERS with MERGED layer styles (sticky
 * pref "1"), plus the Stroke Emboss files and bevel-outer-smooth as COMP with
 * EDITABLE styles (pref "0"), renamed "<stem>|editable". Saves
 * samples/models/import/psd_styles_corpus.aep and its export_project_json.jsx
 * JSON next to it.
 *
 * Run headless: Stop-Process AfterFX*; AfterFX.com -noui -ro <this file>.
 * The log (next to the .aep) ends with DONE.
 */
var AEP_EXPORT_AS_LIBRARY = true;
#include "export_project_json.jsx";
(function () {
    var REPO = new File($.fileName).parent.parent.parent.fsName + "/";
    var SRC = REPO + "samples/assets/psd_styles/";
    var OUT = REPO + "samples/models/import/";
    var BASE = REPO + "samples/models/folder/folder.aep";
    var log = new File(OUT + "psd_styles_corpus_log.txt");
    log.open("w"); log.writeln("start " + new Date().toString() + " AE " + app.version); log.close();
    function w(s) { log.open("a"); log.writeln(s); log.close(); }
    var SEC = "Choose Layer Dialog", KEY = "PSD Comp Layer Styles Option v2";
    var T = PREFType.PREF_Type_MACHINE_SPECIFIC;
    function setPref(v) {
        try { app.preferences.savePrefAsString(SEC, KEY, v, T); app.preferences.saveToDisk(); } catch (e) { w("PREF ERROR " + e.toString()); }
    }
    app.beginSuppressDialogs();
    try {
        app.open(new File(BASE));
        setPref("1");
        var files = new Folder(SRC).getFiles("*.psd");
        for (var i = 0; i < files.length; i++) {
            try {
                var o = new ImportOptions(files[i]);
                o.importAs = ImportAsType.COMP_CROPPED_LAYERS;
                app.project.importFile(o);
                w("OK merge " + files[i].name);
            } catch (eI) { w("FAIL " + files[i].name + " " + eI.toString()); }
        }
        setPref("0");
        var editable = ["bevel-stroke-smooth", "bevel-stroke-chisel-hard", "bevel-stroke-chisel-soft",
            "bevel-stroke-emboss-center-stroke-chisel-soft", "bevel-stroke-emboss-inside-stroke", "bevel-outer-smooth"];
        for (var j = 0; j < editable.length; j++) {
            try {
                var oe = new ImportOptions(new File(SRC + editable[j] + ".psd"));
                oe.importAs = ImportAsType.COMP;
                var comp = app.project.importFile(oe);
                comp.name = editable[j] + "|editable";
                w("OK editable " + editable[j]);
            } catch (eE) { w("FAIL editable " + editable[j] + " " + eE.toString()); }
        }
        setPref("1");
        app.project.save(new File(OUT + "psd_styles_corpus.aep"));
        w("SAVED");
        var ok = AepExport.saveProjectJson(AepExport.exportProject(), OUT + "psd_styles_corpus.json");
        w("JSON " + ok);
    } catch (eD) { w("ERROR " + eD.toString() + " line " + eD.line); }
    w("DONE");
    app.quit();
})();
