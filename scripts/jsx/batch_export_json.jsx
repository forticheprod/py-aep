/**
 * Batch Export All Sample Projects to JSON
 * 
 * This script iterates through all .aep files in the selected folder
 * and exports each one to JSON using the export_project_json module.
 * 
 * Usage (interactive):
 *   1. Open After Effects (the latest version you have to get the most attributes)
 *   2. Run this script: File > Scripts > Run Script File
 *   3. Select a folder
 *   4. All .aep files in selected folder and subfolders will be exported to .json files in the same location
 * 
 * Usage (headless):
 *   Set targetFolder below, then run:
 *   & "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.com" -noui -ro <path>
 *   Poll the log file for a "DONE" marker.
 * 
 * Output:
 *   - Each .aep file gets a corresponding .json file next to it
 *   - A summary is written to the log file (and console) with success/failure counts
 */

// ── Configuration ─────────────────────────────────────────────────────────
// Set this to a folder path for headless mode, or leave empty for interactive dialog
var targetFolder = "";

// Set library mode before including export module
// (export_project_json.jsx includes json2.jsx internally)
var AEP_EXPORT_AS_LIBRARY = true;

// Include the export module
#include "export_project_json.jsx";

(function() {
    "use strict";

    // ── Logging ───────────────────────────────────────────────────────────
    var logPath = targetFolder ? targetFolder + "/_batch_export_log.txt" : Folder.myDocuments.fsName + "/_batch_export_log.txt";
    var logFile = new File(logPath);
    logFile.open("w");
    function log(msg) {
        logFile.writeln(msg);
        $.writeln(msg);
    }

    // =========================================================================
    // Batch Processing Functions
    // =========================================================================

    /**
     * Recursively find all .aep files in a folder.
     * @param {Folder} folder - The folder to search
     * @param {Array} fileList - Array to collect files into
     * @returns {Array} The fileList with found files
     */
    function findAepFiles(folder, fileList) {
        var files = folder.getFiles();

        for (var i = 0; i < files.length; i++) {
            var file = files[i];

            if (file instanceof Folder) {
                // Skip non-project folders: assets (source files) and auto-save
                var lowerName = file.name.toLowerCase();
                if (lowerName !== "assets" && lowerName.indexOf("auto-save") === -1) {
                    findAepFiles(file, fileList);
                }
            } else if (file instanceof File) {
                if (file.name.match(/\.aep$/i)) {
                    fileList.push(file);
                }
            }
        }

        return fileList;
    }

    /**
     * Process a single .aep file: open, export to JSON, close.
     * @param {File} aepFile - The .aep file to process
     * @returns {Object} Result with success status and details
     */
    function processAepFile(aepFile) {
        try {
            // Open the project
            var project = app.open(aepFile);

            if (!project) {
                return { success: false, error: "Failed to open project" };
            }

            // Export using the AepExport module
            var projectData = AepExport.exportProject();

            // Save JSON file next to the AEP
            var jsonPath = aepFile.fsName.replace(/\.aep$/i, ".json");
            var success = AepExport.saveProjectJson(projectData, jsonPath);

            // Close without saving changes
            app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);

            if (success) {
                return { success: true, jsonPath: jsonPath };
            } else {
                return { success: false, error: "Failed to write JSON file" };
            }

        } catch(e) {
            // Try to close any open project
            try {
                if (app.project) {
                    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
                }
            } catch(e2) {}

            return { success: false, error: e.toString() };
        }
    }

    // =========================================================================
    // Main Execution
    // =========================================================================

    function main() {
        // Check that AepExport is available
        if (typeof AepExport === "undefined" || typeof AepExport.exportProject !== "function") {
            log("ERROR: export_project_json.jsx must be included before this script.");
            log("Make sure the @include directive is uncommented and the file path is correct.");
            logFile.close();
            return;
        }

        // Determine target folder: use config variable or interactive dialog
        var selectedFolder;
        if (targetFolder && targetFolder.length > 0) {
            selectedFolder = new Folder(targetFolder);
            if (!selectedFolder.exists) {
                log("ERROR: Configured targetFolder does not exist: " + targetFolder);
                logFile.close();
                return;
            }
        } else {
            selectedFolder = Folder.selectDialog("Select folder containing .aep files");
            if (!selectedFolder) {
                logFile.close();
                return;
            }
        }

        log("=== Batch Export to JSON ===");
        log("Selected folder: " + selectedFolder.fsName);
        log("");

        // Find all .aep files
        var aepFiles = findAepFiles(selectedFolder, []);

        if (aepFiles.length === 0) {
            log("ERROR: No .aep files found in: " + selectedFolder.fsName);
            logFile.close();
            return;
        }

        log("Found " + aepFiles.length + " .aep files");
        log("");

        // Process each file
        var successCount = 0;
        var failureCount = 0;
        var failures = [];

        for (var i = 0; i < aepFiles.length; i++) {
            var aepFile = aepFiles[i];
            var relativePath = aepFile.fsName.replace(selectedFolder.fsName, "");

            log("[" + (i + 1) + "/" + aepFiles.length + "] " + relativePath);

            var result = processAepFile(aepFile);

            if (result.success) {
                log("  -> OK");
                successCount++;
            } else {
                log("  -> FAILED: " + result.error);
                failureCount++;
                failures.push({ file: relativePath, error: result.error });
            }
        }

        // Summary
        log("");
        log("=== Summary ===");
        log("Success: " + successCount);
        log("Failed: " + failureCount);
        log("Total: " + aepFiles.length);

        if (failures.length > 0) {
            log("");
            log("Failed files:");
            for (var j = 0; j < failures.length; j++) {
                log("  " + failures[j].file + ": " + failures[j].error);
            }
        }

        log("");
        log("Success: " + successCount + "  Failed: " + failureCount + "  Total: " + aepFiles.length);
        log("DONE");
        logFile.close();
    }

    main();

})();
