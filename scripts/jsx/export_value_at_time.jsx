/**
 * Export valueAtTime Ground Truth for Keyframe Samples
 *
 * Opens each keyframe/property sample .aep, finds animated properties,
 * and exports valueAtTime() for every frame of the composition.
 * Output is one JSON file per sample in a value_at_time/ subfolder.
 *
 * Usage:
 *   1. Open After Effects 2025+
 *   2. File > Scripts > Run Script File
 *   3. Select the samples/models/property/ folder when prompted
 *   4. Results are saved to samples/models/property/value_at_time/
 */

#include "json2.jsx";

(function() {
    "use strict";

    // Restrict the run to these base names (no extension). Leave empty to
    // re-export every keyframe_*.aep / property_*.aep sample - which
    // rewrites all the committed ground truth, so set it when adding one.
    var ONLY = [];

    function isSelected(baseName) {
        if (ONLY.length === 0) return true;
        for (var i = 0; i < ONLY.length; i++) {
            if (ONLY[i] === baseName) return true;
        }
        return false;
    }

    /**
     * Recursively find all animated properties in a property group.
     * @param {PropertyGroup} group - The property group to search.
     * @param {string} pathPrefix - Accumulated path for display.
     * @returns {Array<{path: string, matchName: string, prop: Property}>}
     */
    function findAnimatedProperties(group, pathPrefix, indexPath) {
        var results = [];
        if (!group) return results;

        for (var i = 1; i <= group.numProperties; i++) {
            var p = group.property(i);
            var currentPath = pathPrefix ? (pathPrefix + " > " + p.name) : p.name;
            var currentIndex = indexPath.concat([i]);

            if (p.propertyType === PropertyType.PROPERTY) {
                if (p.numKeys > 0) {
                    results.push({
                        path: currentPath,
                        indexPath: currentIndex,
                        matchName: p.matchName,
                        prop: p
                    });
                }
            } else if (p.propertyType === PropertyType.INDEXED_GROUP ||
                       p.propertyType === PropertyType.NAMED_GROUP) {
                var sub = findAnimatedProperties(p, currentPath, currentIndex);
                for (var j = 0; j < sub.length; j++) {
                    results.push(sub[j]);
                }
            }
        }
        return results;
    }

    /**
     * Convert a property value to a JSON-safe format.
     * @param {*} val - The value to convert.
     * @returns {*} JSON-safe value (array or number).
     */
    function valueToArray(val) {
        if (val instanceof Shape) {
            return {
                closed: val.closed,
                vertices: val.vertices,
                inTangents: val.inTangents,
                outTangents: val.outTangents
            };
        }
        if (val instanceof Array) {
            var arr = [];
            for (var i = 0; i < val.length; i++) {
                arr.push(val[i]);
            }
            return arr;
        }
        return val;
    }

    /**
     * Round a number to a given number of decimal places.
     * @param {number} num - The number to round.
     * @param {number} decimals - Number of decimal places.
     * @returns {number}
     */
    function roundTo(num, decimals) {
        var factor = Math.pow(10, decimals);
        return Math.round(num * factor) / factor;
    }

    /**
     * Export valueAtTime for all animated properties in the given comp.
     * @param {CompItem} comp - The composition to export.
     * @returns {Object} Comp data with per-frame values for each animated property.
     */
    function exportCompValueAtTime(comp) {
        var numFrames = Math.round(comp.duration / comp.frameDuration);
        var compData = {
            name: comp.name,
            width: comp.width,
            height: comp.height,
            duration: comp.duration,
            frameRate: comp.frameRate,
            frameDuration: comp.frameDuration,
            numFrames: numFrames,
            layers: []
        };

        for (var li = 1; li <= comp.numLayers; li++) {
            var layer = comp.layer(li);
            var animatedProps = findAnimatedProperties(layer, "", []);
            if (animatedProps.length === 0) continue;

            var layerData = {
                name: layer.name,
                index: layer.index,
                width: layer.width,
                height: layer.height,
                properties: []
            };

            for (var pi = 0; pi < animatedProps.length; pi++) {
                var propInfo = animatedProps[pi];
                var prop = propInfo.prop;

                var propData = {
                    path: propInfo.path,
                    indexPath: propInfo.indexPath,
                    matchName: propInfo.matchName,
                    numKeys: prop.numKeys,
                    isSpatial: false,
                    keyframes: [],
                    frames: []
                };

                // Check if spatial
                try {
                    prop.keyInSpatialTangent(1);
                    propData.isSpatial = true;
                } catch (e) {}

                // Export keyframe reference data
                for (var ki = 1; ki <= prop.numKeys; ki++) {
                    var kfData = {
                        index: ki,
                        time: prop.keyTime(ki),
                        value: valueToArray(prop.keyValue(ki))
                    };
                    propData.keyframes.push(kfData);
                }

                // Export valueAtTime for every frame
                for (var fr = 0; fr < numFrames; fr++) {
                    var time = fr * comp.frameDuration;
                    var val;
                    try {
                        val = valueToArray(prop.valueAtTime(time, false));
                    } catch (e) {
                        val = "ERROR: " + e.toString();
                    }
                    propData.frames.push({
                        frame: fr,
                        time: time,
                        value: val
                    });
                }

                layerData.properties.push(propData);
            }

            compData.layers.push(layerData);
        }

        return compData;
    }

    /**
     * Process a single .aep file: open it, export valueAtTime, save JSON.
     * @param {File} aepFile - The .aep file to process.
     * @param {Folder} outputFolder - The folder to save the JSON output.
     */
    function processFile(aepFile, outputFolder) {
        var baseName = aepFile.name.replace(/\.aep$/i, "");

        var proj = app.open(aepFile);
        if (!proj) {
            $.writeln("  ERROR: Could not open " + aepFile.fsName);
            return;
        }

        var result = {
            source: aepFile.name,
            comps: []
        };

        for (var i = 1; i <= proj.numItems; i++) {
            var item = proj.item(i);
            if (item instanceof CompItem) {
                result.comps.push(exportCompValueAtTime(item));
            }
        }

        // Save JSON
        var jsonPath = outputFolder.fsName + "/" + baseName + "_value_at_time.json";
        var jsonFile = new File(jsonPath);
        jsonFile.open("w");
        jsonFile.encoding = "UTF-8";
        jsonFile.write(JSON.stringify(result, null, 2));
        jsonFile.close();

        $.writeln("  Exported: " + baseName + "_value_at_time.json");

        proj.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    }

    // =========================================================================
    // Main
    // =========================================================================

    function main() {
        // Resolve path relative to this script: scripts/jsx/../../samples/models/property/
        var scriptFile = new File($.fileName);
        var scriptDir = scriptFile.parent;
        var folder = new Folder(scriptDir.fsName + "/../../samples/models/property");

        if (!folder.exists) {
            $.writeln("ERROR: Sample folder not found: " + folder.fsName);
            return;
        }

        // Create output subfolder
        var outputFolder = new Folder(folder.fsName + "/value_at_time");
        if (!outputFolder.exists) {
            outputFolder.create();
        }

        // Collect all keyframe_*.aep and property_*.aep files
        var aepFiles = folder.getFiles("keyframe_*.aep");
        var propFiles = folder.getFiles("property_*.aep");
        for (var i = 0; i < propFiles.length; i++) {
            aepFiles.push(propFiles[i]);
        }

        if (aepFiles.length === 0) {
            $.writeln("ERROR: No keyframe_*.aep or property_*.aep files found in: " + folder.fsName);
            return;
        }

        // Sort by name for reproducible order
        aepFiles.sort(function(a, b) {
            return a.name.localeCompare(b.name);
        });

        $.writeln("=== Exporting valueAtTime Ground Truth ===");
        $.writeln("Input folder:  " + folder.fsName);
        $.writeln("Output folder: " + outputFolder.fsName);
        $.writeln("Found " + aepFiles.length + " sample files");
        $.writeln("");

        var errors = 0;
        for (var fi = 0; fi < aepFiles.length; fi++) {
            if (!isSelected(aepFiles[fi].name.replace(/\.aep$/i, ""))) {
                continue;
            }
            $.writeln("[" + (fi + 1) + "/" + aepFiles.length + "] " + aepFiles[fi].name);
            try {
                processFile(aepFiles[fi], outputFolder);
            } catch (e) {
                $.writeln("  ERROR: " + e.toString());
                errors++;
            }
        }

        $.writeln("");
        $.writeln("=== Export Complete ===");
        $.writeln("Total files: " + aepFiles.length);
        if (errors > 0) {
            $.writeln("Errors: " + errors);
        }
        $.writeln("Output: " + outputFolder.fsName);

        $.writeln("Processed " + aepFiles.length + " files" +
              (errors > 0 ? " (" + errors + " errors)" : "") + ".");
        $.writeln("Output: " + outputFolder.fsName);
    }

    main();

})();
