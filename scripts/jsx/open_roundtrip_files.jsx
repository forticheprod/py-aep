/**
 * Open Roundtrip Test Files in After Effects
 *
 * Opens each .aep file in the roundtrip output folder, checks if it loads
 * without errors, and logs the result. Used to verify that files produced
 * by parse() + save() are valid After Effects projects.
 *
 * The folder is resolved relative to this script's location:
 *   scripts/jsx/../../samples/unused/roundtrip/
 *
 * Usage:
 *   1. Run generate_roundtrip_files.py first to produce the .aep files
 *   2. Run this script in After Effects (via ExtendScript debug or File > Scripts)
 *   3. Results are logged to the console and saved to results.txt
 */
(function() {
    "use strict";

    // Resolve samples/unused/roundtrip/ relative to this script
    var scriptFile = new File($.fileName);
    var scriptDir = scriptFile.parent;
    var folder = new Folder(scriptDir.fsName + "/../../samples/unused/roundtrip");
    if (!folder.exists) {
        $.writeln("ERROR: Could not find samples/unused/roundtrip/ relative to script.");
        $.writeln("$.fileName was: " + $.fileName);
        $.writeln("Resolved to: " + folder.fsName);
        $.writeln("Run generate_roundtrip_files.py first.");
        return;
    }

    var aepFiles = folder.getFiles("*.aep");
    if (aepFiles.length === 0) {
        $.writeln("No .aep files found in " + folder.fsName);
        return;
    }

    aepFiles.sort(function(a, b) {
        return a.name.localeCompare(b.name);
    });

    var results = [];
    var passed = 0;
    var failed = 0;

    $.writeln("=== Roundtrip Open Test ===");
    $.writeln("Folder: " + folder.fsName);
    $.writeln("Files:  " + aepFiles.length);
    $.writeln("");

    for (var i = 0; i < aepFiles.length; i++) {
        var file = aepFiles[i];
        var name = file.name;
        var status;
        var detail = "";

        try {
            app.open(file);

            // Basic sanity: project has items
            var numItems = app.project.numItems;
            detail = numItems + " items";

            app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            status = "OK";
            passed++;
        } catch (e) {
            status = "FAIL";
            detail = e.toString();
            failed++;
            // Try to close if something is open
            try {
                app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            } catch (e2) {}
        }

        var line = "[" + status + "] " + name + (detail ? " (" + detail + ")" : "");
        $.writeln(line);
        results.push(line);
    }

    $.writeln("");
    $.writeln("=== Results: " + passed + " passed, " + failed + " failed, " + aepFiles.length + " total ===");
    results.push("");
    results.push("=== Results: " + passed + " passed, " + failed + " failed, " + aepFiles.length + " total ===");

    // Save results to file
    var resultsFile = new File(folder.fsName + "/results.txt");
    resultsFile.open("w");
    resultsFile.encoding = "UTF-8";
    resultsFile.write(results.join("\n"));
    resultsFile.close();

    $.writeln("Results saved to: " + resultsFile.fsName);
})();
