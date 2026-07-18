# ExtendScript Coverage

Implementation progress of the ExtendScript API in py_aep.

Each row lists the attributes and methods from the
[After Effects Scripting Guide](https://ae-scripting.docsforadobe.dev/)
that are not yet implemented.

- ✅ = all attributes and methods implemented
- 🚧 = partially implemented
- ❌ = class does not exist in py_aep

Two kinds of members are excluded from the tables and do not count against
a class's status:

- **Runtime members** reflect the state of a running After Effects instance
  (UI panels, rendering, dialogs, the font server, watch folders,
  Team Projects). They are not stored in `.aep` files and are out of scope
  for a file parser; each section's note lists them.
- **Intentionally different APIs**: members py_aep exposes through a more
  Pythonic surface - keyframe `key*()` methods > `Property.keyframes`,
  collection classes (`ItemCollection`, `LayerCollection`, `OMCollection`,
  `RQItemCollection`) > plain lists plus `add_*()` methods on the owning
  model, `toString()` > `str()`. See
  [Differences from ExtendScript](differences.md).


## General

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| Application | 🚧 | `effects` | |
| System | ❌ | | |
| Project | ✅ | | |

Note:
    All `System` members and the remaining `Application` members are runtime
    state: `availableGPUAccelTypes`, `disableRendering`,
    `exitAfterLaunchAndEval`, `exitCode`, `fonts`, `isoLanguage`,
    `isRenderEngine`, `isWatchFolder`, `memoryInUse`, `onError`,
    `saveProjectOnCrash`, `settings`, and every `Application` method (undo
    groups, dialogs, watch folders, tasks, memory limits). `app.open()` and
    `app.newProject()` correspond to `py_aep.parse()` and `py_aep.new()`.
    The installed-effect names are available as `Project.effect_names`;
    `app.effects`'s per-effect category and version are not parsed.

Note:
    `Project` runtime members: `dirty`, `selection`, `toolType`, `close()`,
    `saveWithDialog()`, `importFileWithDialog()`, `showWindow()`,
    `setDefaultImportFolder()`, and the Team Projects methods.
    `itemByID(id)` is `project.items[id]` (a dict keyed by item id);
    `item(index)` indexes the same collection.


## Items

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| Item | ✅ | | |
| AVItem | ✅ | | |
| CompItem | 🚧 | `selectedLayers`, `selectedProperties` | `exportAsMotionGraphicsTemplate()` |
| FolderItem | ✅ | | |
| FootageItem | ✅ | | |

Note:
    `Item.setGuide()` is covered by the writable `Guide` objects on
    `Item.guides`. `CompItem.getMotionGraphicsTemplateControllerName()` /
    `setMotionGraphicsControllerName()` are covered by the read/write
    `EssentialGraphicsController.name`. Runtime members: `CompItem.counters`
    (an undocumented app-wide no-op), `openInViewer()`,
    `openInEssentialGraphics()`.


## Layers

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| Layer | 🚧 | `selectedProperties` | `applyPreset()` |
| AVLayer | 🚧 | | `sourceRectAtTime()` (text and shape layer content bounds) |
| CameraLayer | ✅ | | |
| LightLayer | ✅ | | |
| TextLayer | ✅ | | |
| ShapeLayer | ✅ | | |
| ThreeDModelLayer | ✅ | | |
| ParametricMeshLayer | ✅ | | |

Note:
    `sourceRectAtTime()` returns the source bounds for footage, solid,
    precomposition and adjustment layers; the text-layer ink bounding box
    (glyph extents) and shape-layer geometry bounds raise
    `NotImplementedError` (see [Differences](differences.md)).
    `Layer.doSceneEditDetection()` (which runs Adobe Sensei's AI scene-cut
    detection on the rendered media) and `openInViewer()` are runtime.


## Properties

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| PropertyBase | ✅ | | |
| PropertyGroup | ✅ | | |
| Property | 🚧 | `selectedKeys` | |
| MaskPropertyGroup | ✅ | | |

Note:
    The keyframe accessors (`keyTime()`, `keyValue()`, `keyInTemporalEase()`,
    ...) and mutators (`setValueAtKey()`, `setTemporalEaseAtKey()`, ...) are
    covered by the `Keyframe` objects on `Property.keyframes` and the 0-based
    mutation methods; `setValue()` is the `value` setter, `setPropertyParameters()`
    the `property_parameters` setter and `setAlternateSource()` the `alternate_source`
    setter (see [Differences](differences.md)). `PropertyBase.propertyGroup(countUp)` is
    covered by walking `parent_property`. Key selection (`selectedKeys`,
    `keySelected()`, `setSelectedAtKey()`) is not parsed.


## Render Queue

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| RenderQueue | ✅ | | |
| RenderQueueItem | 🚧 | | `saveAsTemplate()` |
| OutputModule | 🚧 | | `saveAsTemplate()` |

Note:
    `setSetting()` and `setSettings()` are covered by the writable `settings`
    mapping on both classes: `item.settings[key] = value` sets one setting and
    `item.settings = {...}` applies a whole dict (a round-tripped
    `dict(item.settings)` re-applies cleanly; read-only keys such as `"Format"`
    are left untouched). Runtime members: `RenderQueue.canQueueInAME`,
    `rendering`, `render()`, `pauseRendering()`, `queueNotify`, `stopRendering()`,
    `queueInAME()`, `showWindow()`, and `RenderQueueItem.onStatusChanged`.
    `RenderQueue.item(index)` and `RenderQueueItem.outputModule(index)` are the
    `items` and `output_modules` lists. `saveAsTemplate()` writes to the AE
    preference files, which py_aep treats as read-only.


## Sources

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| FootageSource | ✅ | | |
| FileSource | ✅ | | |
| SolidSource | ✅ | | |
| PlaceholderSource | ✅ | | |

Note:
    `FootageSource.guessAlphaMode()` and `guessPulldown()` analyze the media
    file at runtime; py_aep deliberately does not estimate alpha or pulldown
    on import.


## Other

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| Shape | ✅ | | |
| KeyframeEase | ✅ | | |
| MarkerValue | ✅ | | |
| ImportOptions | ✅ | | |
| Preferences | 🚧 | | `saveToDisk()` |
| Settings | ❌ | | |
| Viewer | ✅ | | |
| ViewOptions | ✅ | | |
| View | ✅ | | |

Note:
    `Shape`'s parallel feather arrays are covered by the `FeatherPoint`
    objects on `Shape.feather_points`, and `MarkerValue.getParameters()` /
    `setParameters()` by the `params` attribute (see
    [Differences](differences.md)).

Note:
    The AE preference `.txt` files are read-only in py_aep: `set_pref_as_*`
    writes an in-memory override layer, so `saveToDisk()` is deliberately
    not provided. `getPrefAsLong` / `getPrefAsFloat` merge into
    `get_pref_as_number()`, and `savePrefAs*` are the `set_pref_as_*`
    methods. `Settings` is the runtime settings store (not part of `.aep`);
    `Viewer.maximized` and `setActive()` are runtime panel state.


## Text

| Class | Status | Missing attributes | Missing methods |
|-------|--------|--------------------|-----------------|
| TextDocument | 🚧 | `fontFamily`, `fontLocation`, `fontStyle` | |
| FontObject | 🚧 | `designAxesData`, `familyName`, `fullName`, `nativeFamilyName`, `nativeFullName`, `nativeStyleName`, `styleName`, `technology`, `type`, `writingScripts` | `postScriptNameForDesignVector()` |
| FontsObject | ❌ | | |
| CharacterRange | ✅ | | |
| ComposedLineRange | ✅ | | |
| ParagraphRange | ✅ | | |

Note:
    The `.aep` file stores only a font's PostScript name, version, and
    design vector; the missing `FontObject` members describe the *installed*
    font and would require system font-database resolution. The remaining
    `FontObject` members are runtime font-server state (`fontID`,
    `isFromAdobeFonts`, `isSubstitute`, `location`,
    `otherFontsWithSameDict`, `hasGlyphsFor()`, `hasSameDict()`), as is the
    whole `FontsObject` collection. `TextDocument.fontFamily` / `fontStyle`
    / `fontLocation` likewise resolve from the installed font (py_aep
    exposes the stored `font` and `font_object` instead).
