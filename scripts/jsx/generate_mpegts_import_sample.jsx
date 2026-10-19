/**
 * generate_mpegts_import_sample.jsx
 *
 * Builds samples/models/import/mpegts_import.aep: every samples/assets/ts_*
 * transport stream imported as footage (one item per file, named after the
 * file; AE refuses the HEVC one), plus its ExtendScript JSON export. Tests
 * compare py_aep's import of the same assets against these items.
 *
 * Usage (headless, AE 2026):
 *   Stop-Process -Name AfterFX* -Force; Start-Sleep 3
 *   & ".../AfterFX.com" -noui -ro <this file>
 * then poll generate_mpegts_import_sample_log.txt for the trailing "DONE".
 */

var AEP_EXPORT_AS_LIBRARY = true;

(function () {
    "use strict";

    var scriptFile = new File($.fileName);
    var dir = scriptFile.parent;
    var repoRoot = dir.parent.parent;
    var assets = new Folder(repoRoot.fsName + "/samples/assets");
    var outAep = new File(repoRoot.fsName + "/samples/models/import/mpegts_import.aep");
    var outJson = new File(repoRoot.fsName + "/samples/models/import/mpegts_import.json");
    var logFile = new File(dir.fsName + "/generate_mpegts_import_sample_log.txt");

    function log(msg) {
        logFile.open("a");
        logFile.writeln(msg);
        logFile.close();
    }

    logFile.open("w");
    logFile.writeln("AE version: " + app.version);
    logFile.close();

    app.beginSuppressDialogs();
    // newProject crashes AE over RDP; start from a known-good project.
    app.open(new File(repoRoot.fsName + "/samples/models/folder/folder.aep"));
    if (outAep.exists) { outAep.remove(); }
    if (outJson.exists) { outJson.remove(); }

    var files = assets.getFiles("ts_*");
    files.sort(function (a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); });
    for (var i = 0; i < files.length; i++) {
        var f = files[i];
        try {
            var opts = new ImportOptions(f);
            opts.importAs = ImportAsType.FOOTAGE;
            var item = app.project.importFile(opts);
            item.name = f.name;
            log("OK       " + f.name + " | w=" + item.width + " h=" + item.height +
                " dur=" + item.duration + " fps=" + (item.frameDuration ? 1.0 / item.frameDuration : 0) +
                " par=" + item.pixelAspect + " audio=" + item.hasAudio +
                " fieldSep=" + item.mainSource.fieldSeparationType);
        } catch (e) {
            log("REFUSED  " + f.name + " - " + e.toString());
        }
    }
    app.project.save(outAep);
    log("SAVED    " + outAep.fsName);

    $.evalFile(new File(dir.fsName + "/export_project_json.jsx"));
    var data = AepExport.exportProject();
    var ok = AepExport.saveProjectJson(data, outJson);
    log(ok ? ("WROTE " + outJson.fsName) : "EXPORT FAILED");
    log("DONE");
})();
