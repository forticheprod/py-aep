/**
 * Export After Effects Project to JSON for testing py_aep.
 * 
 * This script dynamically discovers and exports all readable attributes
 * from AE objects, making tests low-maintenance when new attributes are added.
 * 
 * Usage (standalone):
 *   1. Open After Effects (the latest version you have to get the most attributes)
 *   2. Open the .aep file you want to export
 *   3. Run this script: File > Scripts > Run Script File
 *   4. A .json file will be saved next to the .aep file
 * 
 * Usage (as library):
 *   Set AEP_EXPORT_AS_LIBRARY = true before including this script.
 *   Then call AepExport.exportProject() and AepExport.saveProjectJson().
 * 
 * The exported JSON serves as the "ground truth" for Python tests.
 */

// Polyfill for JSON (AE uses ES3)
#include "json2.jsx";

// Global namespace for library usage
var AepExport = AepExport || {};

(function(exports) {
    "use strict";

    // =========================================================================
    // Configuration: Properties to skip during dynamic discovery
    // =========================================================================

    // Properties that would cause infinite recursion or are not useful
    var SKIP_PROPERTIES = {
        // Object references that would cause recursion or duplicates
        "activeItem": true,
        "parent": true,
        "parentFolder": true,
        "parentProperty": true,
        "rootFolder": true,
        "selectedLayers": true,
        "selectedProperties": true,
        "selection": true,
        "source": true,
        "usedIn": true,

        // Methods disguised as properties or internal
        "reflect": true,
        "toSource": true,
        "unwatch": true,
        "watch": true,
        
        // File objects (handled specially)
        "file": true,
        "mainSource": true,
        
        // Collections (handled separately)
        "items": true,
        "layers": true,

        // GUI stuff
        "dirty": true,
        "selected": true,
        "toolType": true,

        // Not useful
        "dynamicLinkGUID": true,
        "revision": true,
        "xmpPacket": true,
    };

    // =========================================================================
    // Helper Functions
    // =========================================================================

    /**
     * Export all settings from a getSettings() result object.
     * Keeps original After Effects key names (e.g., "Video Output", "Frame Rate").
     */
    function exportSettingsObject(settingsObj) {
        var result = {};
        for (var key in settingsObj) {
            if (settingsObj.hasOwnProperty(key)) {
                var value = settingsObj[key];
                if (isSimpleValue(value)) {
                    result[key] = value;
                } else if (typeof value === "object" && value !== null) {
                    // Recurse into nested settings objects
                    // (e.g. "Output File Info", "Resize to")
                    result[key] = exportSettingsObject(value);
                }
            }
        }
        return result;
    }

    /**
     * Check if a value is a simple exportable type.
     */
    function isSimpleValue(value) {
        var type = typeof value;
        if (type === "undefined") return true;
        if (value === null) return true;
        if (type === "boolean") return true;
        if (type === "number") return true;
        if (type === "string") return true;
        // Arrays of simple values (like bgColor, resolutionFactor)
        if (value instanceof Array) {
            for (var i = 0; i < value.length; i++) {
                if (!isSimpleValue(value[i])) return false;
            }
            return true;
        }
        return false;
    }

    /**
     * Dynamically get all readable attributes from an object.
     * Skips functions, complex objects, and properties in SKIP_PROPERTIES.
     */
    function getAllAttributes(obj) {
        var result = {};
        
        for (var prop in obj) {
            // Skip properties in our skip list
            if (SKIP_PROPERTIES[prop]) continue;
            
            try {
                var value = obj[prop];
                var type = typeof value;
                
                // Skip functions
                if (type === "function") continue;
                
                // Skip complex objects (but allow arrays and null)
                if (!isSimpleValue(value)) continue;
                
                // Handle undefined
                if (type === "undefined") {
                    result[prop] = {"_undefined": true};
                } else {
                    result[prop] = value;
                }
            } catch (e) {
                // Property threw an error when accessed - skip it
                // (some properties are only valid in certain states)
            }
        }
        
        return result;
    }

    /**
     * Export guides from an item.
     */
    function exportGuides(item) {
        var guides = [];
        try {
            var itemGuides = item.guides;
            if (!itemGuides || itemGuides.length === 0) {
                return guides;
            }
            for (var i = 0; i < itemGuides.length; i++) {
                guides.push(getAllAttributes(itemGuides[i]));
            }
        } catch (e) {
            // guides not available in this AE version
        }
        return guides;
    }

    /**
     * Export markers from a property group.
     */
    function exportMarkers(markerProperty) {
        var markers = [];
        if (!markerProperty || markerProperty.numKeys === 0) {
            return markers;
        }

        for (var i = 1; i <= markerProperty.numKeys; i++) {
            var markerValue = markerProperty.keyValue(i);
            var marker = {
                time: markerProperty.keyTime(i),
                index: i
            };

            // Dynamically get all marker attributes
            var markerAttrs = getAllAttributes(markerValue);
            for (var key in markerAttrs) {
                marker[key] = markerAttrs[key];
            }

            markers.push(marker);
        }

        return markers;
    }

    /**
     * Export keyframes from a property.
     */
    function exportKeyframes(prop) {
        var keyframes = [];
        if (!prop || prop.numKeys === 0) {
            return keyframes;
        }

        for (var i = 1; i <= prop.numKeys; i++) {
            var kf = {
                index: i,
                time: prop.keyTime(i),
                value: prop.keyValue(i),
                inInterpolationType: prop.keyInInterpolationType(i),
                outInterpolationType: prop.keyOutInterpolationType(i)
            };

            // Shape keyframe values are Shape objects - export them explicitly
            try {
                if (prop.propertyValueType === PropertyValueType.SHAPE) {
                    kf.value = exportShape(prop.keyValue(i));
                }
            } catch (e) {}

            // Spatial tangents only exist for spatial properties (e.g. Position)
            // and throw on non-spatial ones (e.g. Opacity, Rotation)
            try {
                kf.inSpatialTangent = prop.keyInSpatialTangent(i);
                kf.outSpatialTangent = prop.keyOutSpatialTangent(i);
                kf.spatialAutoBezier = prop.keySpatialAutoBezier(i);
                kf.spatialContinuous = prop.keySpatialContinuous(i);
                kf.roving = prop.keyRoving(i);
            } catch (e) {}

            // Get temporal ease - explicitly access speed and influence
            // (getAllAttributes uses for..in which may not enumerate native object properties)
            kf.inTemporalEase = [];
            kf.outTemporalEase = [];
            var inEase = prop.keyInTemporalEase(i);
            var outEase = prop.keyOutTemporalEase(i);
            for (var j = 0; j < inEase.length; j++) {
                kf.inTemporalEase.push({speed: inEase[j].speed, influence: inEase[j].influence});
                kf.outTemporalEase.push({speed: outEase[j].speed, influence: outEase[j].influence});
            }
            kf.temporalAutoBezier = prop.keyTemporalAutoBezier(i);
            kf.temporalContinuous = prop.keyTemporalContinuous(i);

            // Keyframe label (AE 22.6+)
            try { kf.label = prop.keyLabel(i); } catch (e) {}

            keyframes.push(kf);
        }

        return keyframes;
    }

    /**
     * Export a TextDocument value object.
     * Uses getAllAttributes as a base, then explicitly adds properties that
     * may not be enumerable via for..in (native getters).
     */
    function exportTextDocument(textDoc) {
        var result = getAllAttributes(textDoc);

        // Color & stroke
        try { result.strokeColor = textDoc.strokeColor; } catch (e) {}

        // Text box
        try { result.boxTextSize = textDoc.boxTextSize; } catch (e) {}
        try { result.boxTextPos = textDoc.boxTextPos; } catch (e) {}
        try { result.boxVerticalAlignment = textDoc.boxVerticalAlignment; } catch (e) {}
        try { result.boxAutoFitPolicy = textDoc.boxAutoFitPolicy; } catch (e) {}
        try { result.boxFirstBaselineAlignment = textDoc.boxFirstBaselineAlignment; } catch (e) {}
        try { result.boxFirstBaselineAlignmentMinimum = textDoc.boxFirstBaselineAlignmentMinimum; } catch (e) {}
        try { result.boxInsetSpacing = textDoc.boxInsetSpacing; } catch (e) {}
        try { result.boxOverflow = textDoc.boxOverflow; } catch (e) {}

        return result;
    }

    /**
     * Export a Shape object (mask path or shape layer path).
     * Extracts core path data and variable-width feather point attributes.
     */
    function exportShape(shape) {
        var result = {};

        // Core path attributes
        try { result.closed = shape.closed; } catch (e) {}
        try { result.vertices = shape.vertices; } catch (e) {}
        try { result.inTangents = shape.inTangents; } catch (e) {}
        try { result.outTangents = shape.outTangents; } catch (e) {}

        // Variable-width mask feather point attributes
        try { result.featherSegLocs = shape.featherSegLocs; } catch (e) {}
        try { result.featherRelSegLocs = shape.featherRelSegLocs; } catch (e) {}
        try { result.featherRadii = shape.featherRadii; } catch (e) {}
        try { result.featherTypes = shape.featherTypes; } catch (e) {}
        try { result.featherInterps = shape.featherInterps; } catch (e) {}
        try { result.featherTensions = shape.featherTensions; } catch (e) {}
        try { result.featherRelCornerAngles = shape.featherRelCornerAngles; } catch (e) {}

        return result;
    }

    /**
     * Export a single property (not a group).
     */
    function exportProperty(prop) {
        var result = getAllAttributes(prop);
        result.propertyType = "Property";

        // Explicitly export attributes needed for value_at_time() that
        // getAllAttributes may miss (native getters not enumerable via for..in)
        try { result.propertyValueType = prop.propertyValueType; } catch (e) {}
        try { result.isSpatial = prop.isSpatial; } catch (e) {}
        try { result.canVaryOverTime = prop.canVaryOverTime; } catch (e) {}
        try { result.isSeparationLeader = prop.isSeparationLeader; } catch (e) {}
        try { result.isSeparationFollower = prop.isSeparationFollower; } catch (e) {}
        try { result.dimensionsSeparated = prop.dimensionsSeparated; } catch (e) {}
        try { result.separationDimension = prop.separationDimension; } catch (e) {}
        try { result.numKeys = prop.numKeys; } catch (e) {}
        try { result.hasMin = prop.hasMin; } catch (e) {}
        try { result.hasMax = prop.hasMax; } catch (e) {}
        try { if (prop.hasMin) result.minValue = prop.minValue; } catch (e) {}
        try { if (prop.hasMax) result.maxValue = prop.maxValue; } catch (e) {}
        try { result.unitsText = prop.unitsText; } catch (e) {}
        try { result.expression = prop.expression; } catch (e) {}
        try { result.expressionEnabled = prop.expressionEnabled; } catch (e) {}

        // Export TextDocument value for text properties (propertyValueType 6424)
        try {
            if (prop.propertyValueType === PropertyValueType.TEXT_DOCUMENT) {
                var textDoc = prop.value;
                if (textDoc) {
                    result.textDocument = exportTextDocument(textDoc);
                }
            }
        } catch (e) {}

        // Export Shape value for shape/mask path properties (propertyValueType 6423)
        try {
            if (prop.propertyValueType === PropertyValueType.SHAPE) {
                var shapeVal = prop.value;
                if (shapeVal) {
                    result.shapeValue = exportShape(shapeVal);
                }
            }
        } catch (e) {}

        // Get keyframes
        if (prop.numKeys > 0) {
            result.keyframes = exportKeyframes(prop);
        }

        return result;
    }

    /**
     * Export a property group recursively.
     */
    function exportPropertyGroup(group, depth) {
        if (!group) return null;
        if (typeof depth === "undefined") depth = 0;
        if (depth > 10) return null; // Prevent infinite recursion

        var result = getAllAttributes(group);
        result.propertyType = "PropertyGroup";

        // Export child properties
        result.properties = [];
        for (var i = 1; i <= group.numProperties; i++) {
            var child = group.property(i);
            if (!child) continue;

            if (child.propertyType === PropertyType.PROPERTY) {
                result.properties.push(exportProperty(child));
            } else if (child.propertyType === PropertyType.INDEXED_GROUP || 
                       child.propertyType === PropertyType.NAMED_GROUP) {
                result.properties.push(exportPropertyGroup(child, depth + 1));
            }
        }

        return result;
    }

    /**
     * Export effects from a layer.
     */
    function exportEffects(layer) {
        var effectsGroup = layer.property("ADBE Effect Parade");
        if (!effectsGroup || effectsGroup.numProperties === 0) {
            return null;
        }
        return exportPropertyGroup(effectsGroup, 0);
    }

    /**
     * Export masks from a layer.
     */
    function exportMasks(layer) {
        var masksGroup = layer.property("ADBE Mask Parade");
        if (!masksGroup || masksGroup.numProperties === 0) {
            return null;
        }
        return exportPropertyGroup(masksGroup, 0);
    }

    /**
     * Export transform properties from a layer.
     */
    function exportTransform(layer) {
        try {
            var transform = layer.property("ADBE Transform Group");
            if (!transform) return null;
            return exportPropertyGroup(transform, 0);
        } catch (e) {
            return null;
        }
    }

    /**
     * Export a FootageSource object.
     */
    function exportFootageSource(source) {
        if (!source) return null;

        var result = {
            type: source.toString()
        };

        // Determine source type
        if (source instanceof SolidSource) {
            result.sourceType = "SolidSource";
        } else if (source instanceof FileSource) {
            result.sourceType = "FileSource";
            // Get file path
            if (source.file) {
                result.filePath = source.file.fsName;
                result.fileName = source.file.name;
            }
        } else if (source instanceof PlaceholderSource) {
            result.sourceType = "PlaceholderSource";
        } else {
            result.sourceType = "FootageSource";
        }

        // Dynamically get all source attributes
        var sourceAttrs = getAllAttributes(source);
        for (var key in sourceAttrs) {
            result[key] = sourceAttrs[key];
        }

        return result;
    }

    /**
     * Export a Layer object.
     */
    function exportLayer(layer) {
        // Dynamically get all layer attributes
        var result = getAllAttributes(layer);

        // Determine layer type
        if (layer instanceof CameraLayer) {
            result.layerType = "CameraLayer";
        } else if (layer instanceof LightLayer) {
            result.layerType = "LightLayer";
        } else if (layer instanceof AVLayer) {
            // AVLayer includes TextLayer, ShapeLayer
            if (layer instanceof TextLayer) {
                result.layerType = "TextLayer";
            } else if (layer instanceof ShapeLayer) {
                result.layerType = "ShapeLayer";
            } else {
                result.layerType = "AVLayer";
            }

            // Get source reference
            if (layer.source) {
                result.sourceId = layer.source.id;
                result.sourceName = layer.source.name;
            }
        } else {
            result.layerType = "Layer";
        }

        // Get parent reference
        if (layer.parent) {
            result.parentIndex = layer.parent.index;
            result.parentName = layer.parent.name;
        }

        // Export all property groups as an ordered properties list.
        result.properties = [];
        for (var i = 1; i <= layer.numProperties; i++) {
            var child = layer.property(i);
            if (!child) continue;
            if (child.propertyType === PropertyType.PROPERTY) {
                result.properties.push(exportProperty(child));
            } else {
                result.properties.push(exportPropertyGroup(child, 1));
            }
        }

        return result;
    }

    /**
     * Export an Item object (CompItem, FootageItem, or FolderItem).
     */
    function exportItem(item) {
        // Dynamically get all item attributes
        var result = getAllAttributes(item);

        // Export guides
        var guides = exportGuides(item);
        if (guides.length > 0) {
            result.guides = guides;
        }

        // Export proxySource (AVItem attribute, available on CompItem and FootageItem)
        if (item instanceof CompItem || item instanceof FootageItem) {
            try {
                if (item.proxySource) {
                    result.proxySource = exportFootageSource(item.proxySource);
                } else {
                    result.proxySource = null;
                }
            } catch (e) {
                result.proxySource = null;
            }
        }

        // Get parent folder reference
        if (item.parentFolder && item.parentFolder !== app.project.rootFolder) {
            result.parentFolderId = item.parentFolder.id;
            result.parentFolderName = item.parentFolder.name;
        }

        if (item instanceof CompItem) {
            result.itemType = "CompItem";

            // Export essential graphics controller names (AE 16.1+)
            try {
                var controllerCount = item.motionGraphicsTemplateControllerCount;
                if (controllerCount > 0) {
                    result.motionGraphicsTemplateControllerNames = [];
                    for (var c = 1; c <= controllerCount; c++) {
                        result.motionGraphicsTemplateControllerNames.push(
                            item.getMotionGraphicsTemplateControllerName(c)
                        );
                    }
                }
            } catch (e) {}

            // Export composition markers
            if (item.markerProperty) {
                result.markers = exportMarkers(item.markerProperty);
            }

            // Export layers
            result.layers = [];
            for (var i = 1; i <= item.numLayers; i++) {
                result.layers.push(exportLayer(item.layer(i)));
            }

        } else if (item instanceof FootageItem) {
            result.itemType = "FootageItem";

            // Get file reference
            if (item.file) {
                result.filePath = item.file.fsName;
                result.fileName = item.file.name;
            }

            // Export mainSource
            result.mainSource = exportFootageSource(item.mainSource);

        } else if (item instanceof FolderItem) {
            result.itemType = "FolderItem";

            // List child item IDs
            result.childItemIds = [];
            for (var i = 1; i <= item.numItems; i++) {
                result.childItemIds.push(item.item(i).id);
            }
        }

        return result;
    }

    /**
     * Export the active viewer panel and its views/options.
     */
    function exportActiveViewer() {
        try {
            var viewer = app.activeViewer;
            if (!viewer) return null;

            var result = getAllAttributes(viewer);
            result.views = [];

            for (var i = 0; i < viewer.views.length; i++) {
                var view = viewer.views[i];
                var viewResult = getAllAttributes(view);
                try {
                    viewResult.options = getAllAttributes(view.options);
                } catch(e) {
                    viewResult.options = {};
                }
                result.views.push(viewResult);
            }

            return result;
        } catch(e) {
            return null;
        }
    }

    /**
     * Export the entire project.
     */
    function exportProject() {
        var project = app.project;

        var result = {};

        // Get project file info
        if (project.file) {
            result.projectName = project.file.name;
        } else {
            result.projectName = "Untitled";
        }

        // Dynamically get all project attributes
        var projectAttrs = getAllAttributes(project);
        for (var key in projectAttrs) {
            result[key] = projectAttrs[key];
        }

        // Export all items
        result.items = [];
        for (var i = 1; i <= project.numItems; i++) {
            result.items.push(exportItem(project.item(i)));
        }

        // Export render queue
        result.renderQueue = exportRenderQueue(project.renderQueue);

        // Export active viewer
        result.activeViewer = exportActiveViewer();

        return result;
    }

    /**
     * Export the render queue.
     */
    function exportRenderQueue(renderQueue) {
        var result = {
            numItems: renderQueue.numItems,
            items: []
        };

        for (var i = 1; i <= renderQueue.numItems; i++) {
            result.items.push(exportRenderQueueItem(renderQueue.item(i)));
        }

        return result;
    }

    /**
     * Export a single render queue item.
     */
    function exportRenderQueueItem(rqItem) {
        var result = getAllAttributes(rqItem);

        // Get comp reference
        if (rqItem.comp) {
            result.compName = rqItem.comp.name;
        }

        // Export render settings
        result.settings = exportRenderSettings(rqItem);

        // Export output modules
        result.outputModules = [];
        for (var i = 1; i <= rqItem.numOutputModules; i++) {
            result.outputModules.push(exportOutputModule(rqItem.outputModule(i)));
        }

        return result;
    }

    /**
     * Export render settings from a RenderQueueItem.
     * Uses getSettings() to retrieve all render settings.
     */
    function exportRenderSettings(rqItem) {
        var settings = rqItem.getSettings(GetSettingsFormat.NUMBER);
        return exportSettingsObject(settings);
    }

    /**
     * Export a single output module.
     */
    function exportOutputModule(om) {
        var result = getAllAttributes(om);

        // Get file path
        if (om.file) {
            result.file = om.file.fsName;
        }

        // Export output module settings
        result.settings = exportOutputModuleSettings(om);

        return result;
    }

    /**
     * Export output module settings from an OutputModule.
     * Uses getSettings() to retrieve all output module settings.
     */
    function exportOutputModuleSettings(om) {
        var settings = om.getSettings(GetSettingsFormat.NUMBER);
        return exportSettingsObject(settings);
    }

    // =========================================================================
    // Public API (for library usage)
    // =========================================================================

    exports.exportProject = exportProject;

    /**
     * Save project data to a JSON file.
     * @param {Object} projectData - The exported project data
     * @param {string} outputPath - The file path to save to
     * @returns {boolean} True if successful
     */
    exports.saveProjectJson = function(projectData, outputPath) {
        try {
            var jsonString = JSON.stringify(projectData, null, 2);
            var outputFile = new File(outputPath);
            outputFile.open("w");
            outputFile.encoding = "UTF-8";
            outputFile.write(jsonString);
            outputFile.close();
            return true;
        } catch(e) {
            return false;
        }
    };

    // =========================================================================
    // Main Execution (only when run directly)
    // =========================================================================

    function main() {
        if (!app.project) {
            $.writeln("ERROR: No project open");
            return;
        }

        var projectData = exportProject();
        var jsonString = JSON.stringify(projectData, null, 2);

        // Determine output file path
        var outputFile;
        if (app.project.file) {
            outputFile = new File(app.project.file.fsName.replace(/\.aep$/i, ".json"));
        } else {
            outputFile = File.saveDialog("Save JSON export", "JSON:*.json");
        }

        if (outputFile) {
            outputFile.open("w");
            outputFile.encoding = "UTF-8";
            outputFile.write(jsonString);
            outputFile.close();
            $.writeln("Exported to: " + outputFile.fsName);
        }
    }

    // Run main() only if not used as a library
    if (typeof AEP_EXPORT_AS_LIBRARY === "undefined" || !AEP_EXPORT_AS_LIBRARY) {
        main();
    }

})(AepExport);
