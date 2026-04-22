# ExtendScript Coverage

Implementation progress of ExtendScript API attributes in py_aep.

Each row lists the attributes from the
[After Effects Scripting Guide](https://ae-scripting.docsforadobe.dev/)
not yet implemented.
Only attributes are counted for now - methods are excluded.

- ✅ = all attributes implemented
- 🚧 = partially implemented
- ❌ = class does not exist in py_aep


## General

| Class | Status | Missing |
|-------|--------|---------|
| Application | 🚧 | `availableGPUAccelTypes`, `effects`, `fonts`, `isoLanguage`, `preferences`, `settings` |
| System | ❌ | |
| Project | 🚧 | `selection`, `toolType` |

Note:
    `Application` and `System` attributes reflect runtime state
    (memory usage, OS info, render engine mode) that is not stored in `.aep`
    files.


## Items

| Class | Status | Missing |
|-------|--------|---------|
| Item | 🚧 | `dynamicLinkGUID` |
| AVItem | 🚧 | `isMediaReplacementCompatible`, `proxySource`, `useProxy` |
| CompItem | 🚧 | `selectedProperties` |
| FolderItem | ✅ | |
| FootageItem | ✅ | |


## Layers

| Class | Status | Missing |
|-------|--------|---------|
| Layer | 🚧 | `selectedProperties` |
| AVLayer | ✅ | |
| CameraLayer | ✅ | |
| LightLayer | ✅ | |
| TextLayer | ✅ | |
| ShapeLayer | ✅ | |
| ThreeDModelLayer | ✅ | |


## Properties

| Class | Status | Missing |
|-------|--------|---------|
| PropertyBase | ✅ | |
| PropertyGroup | ✅ | |
| Property | 🚧 | `alternateSource`, `canSetAlternateSource`, `canSetExpression`, `essentialPropertySource`, `selectedKeys`, `valueText` |
| MaskPropertyGroup | ✅ | |


## Render Queue

| Class | Status | Missing |
|-------|--------|---------|
| RenderQueue | 🚧 | `canQueueInAME`, `rendering` |
| RenderQueueItem | 🚧 | `templates` |
| OutputModule | 🚧 | `templates` |


## Sources

| Class | Status | Missing |
|-------|--------|---------|
| FootageSource | ✅ | |
| FileSource | ✅ | |
| SolidSource | ✅ | |
| PlaceholderSource | ✅ | |


## Other

| Class | Status | Missing |
|-------|--------|---------|
| Shape | ✅ | |
| KeyframeEase | ✅ | |
| MarkerValue | ✅ | |
| ImportOptions | ❌ | `file`, `forceAlphabetical`, `importAs`, `rangeEnd`, `rangeStart`, `sequence` |
| Viewer | ✅ | |
| ViewOptions | ✅ | |
| View | ✅ | |


## Text

| Class | Status | Missing |
|-------|--------|---------|
| TextDocument | ✅ | |
| FontObject | 🚧 | `otherFontsWithSameDict` |
| FontsObject | ❌ | `allFonts`, `favoriteFontFamilyList`, `fontsDuplicateByPostScriptName`, `fontServerRevision`, `fontsWithDefaultDesignAxes`, `freezeSyncSubstitutedFonts`, `missingOrSubstitutedFonts`, `mruFontFamilyList`, `substitutedFontReplacementMatchPolicy` |
| CharacterRange | ❌ | `characterEnd`, `characterStart`, `fillColor`, `isRangeValid`, `kerning`, `strokeColor`, `strokeOverFill`, `text` |
| ComposedLineRange | ❌ | `characterEnd`, `characterStart`, `isRangeValid` |
| ParagraphRange | ❌ | `characterEnd`, `characterStart`, `isRangeValid` |

Note:
    `FontsObject` is a runtime collection, not stored in `.aep` files.