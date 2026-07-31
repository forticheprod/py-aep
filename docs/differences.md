# Differences from ExtendScript

This page documents the intentional design differences between py_aep and
the After Effects ExtendScript API. These are not bugs - they are choices made
to provide a more Pythonic, convenient, or complete interface.

## Naming Conventions

ExtendScript uses `camelCase` for attributes and methods. py_aep uses
`snake_case` following Python conventions:

| ExtendScript | py_aep |
|---|---|
| `blendingMode` | `blending_mode` |
| `frameRate` | `frame_rate` |
| `isTimeVarying` | `is_time_varying` |

## Indexing

ExtendScript collections are **1-based**. Python lists and py_aep are
**0-based**:

=== "ExtendScript"

    ```javascript
    var firstLayer = comp.layer(1);
    var firstKey = prop.keyValue(1);
    ```

=== "py_aep"

    ```python
    first_layer = comp.layers[0]
    first_key = prop.keyframes[0].value
    ```

`Layer.index` and `PropertyBase.property_index` also use **0-based** numbering,
so that `comp.layers[layer.index]` and `group.properties[prop.property_index]`
work directly without offset arithmetic.

## Collections and Iterators

ExtendScript uses indexed accessor methods (`item(index)`, `layer(index)`) on
custom collection objects (`ItemCollection`, `LayerCollection`,
`OMCollection`, `RQItemCollection`). py_aep uses standard Python lists:

=== "ExtendScript"

    ```javascript
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
    }
    ```

=== "py_aep"

    ```python
    for layer in comp.layers:
        ...
    ```

## Keyframes

ExtendScript accesses keyframe data through `Property.key*()` methods that take
a 1-based key index. py_aep exposes keyframes as a list of `Keyframe` objects on
`Property.keyframes`:

=== "ExtendScript"

    ```javascript
    var time = prop.keyTime(1);
    var value = prop.keyValue(1);
    var inType = prop.keyInInterpolationType(1);
    ```

=== "py_aep"

    ```python
    kf = prop.keyframes[0]
    kf.time        # seconds
    kf.frame_time  # frames
    kf.value
    kf.in_interpolation_type
    ```

The `Keyframe` object bundles all keyframe attributes together, so you don't
need separate method calls for each attribute.

The keyframe mutation methods mirror ExtendScript but use **0-based**
key indices:

=== "ExtendScript"

    ```javascript
    prop.addKey(1.0);
    prop.setValueAtTime(1.0, value);
    prop.setValuesAtTimes(times, values);
    prop.removeKey(1);
    ```

=== "py_aep"

    ```python
    prop.add_key(1.0)
    prop.set_value_at_time(1.0, value)
    prop.set_values_at_times(times, values)
    prop.remove_key(0)
    ```

These work on every property kind, including the complex ones (mask
paths, source text, markers, orientation, gradients). Adding the first
keyframe converts a static property to an animated one, and removing the
last keyframe reverts it to a static value holding the removed keyframe's
value, matching After Effects' on-disk forms. Marker properties accept a
plain string as a comment shorthand:

```python
layer["ADBE Marker"].set_value_at_time(2.0, "my comment")
```

## Feather Points

ExtendScript exposes mask feather data as parallel arrays on `Shape`
(`featherSegLocs`, `featherRadii`, etc.). py_aep exposes a list of
`FeatherPoint` objects on `Shape.feather_points`:

=== "ExtendScript"

    ```javascript
    var locs = shape.featherSegLocs;
    var radii = shape.featherRadii;
    var types = shape.featherTypes;
    ```

=== "py_aep"

    ```python
    for fp in shape.feather_points:
        fp.seg_loc
        fp.radius
        fp.type
    ```

Each `FeatherPoint` bundles segment location, radius, interpolation,
tension, and corner angle together.

## Markers

In ExtendScript, `CompItem.markerProperty` and `Layer.marker` are
`Property` objects accessed via `keyValue()`. In py_aep,
`CompItem.marker_property` and `Layer.marker` expose the underlying
`Property` (with keyframes holding marker times), while
`CompItem.markers` and `Layer.markers` provide a convenient flat
`list[MarkerValue]`:

=== "ExtendScript"

    ```javascript
    var marker = comp.markerProperty.keyValue(1);
    marker.comment;
    ```

=== "py_aep"

    ```python
    marker = comp.markers[0]
    marker.comment
    marker.time        # seconds
    marker.frame_time  # frames
    ```

## Frame-Based Time Attributes

ExtendScript expresses all times in seconds (floating-point). py_aep adds
integer frame-based equivalents for convenience:

| ExtendScript (seconds) | py_aep (seconds) | py_aep (frames) |
|---|---|---|
| `Layer.inPoint` | `layer.in_point` | `layer.frame_in_point` |
| `Layer.outPoint` | `layer.out_point` | `layer.frame_out_point` |
| `Layer.startTime` | `layer.start_time` | `layer.frame_start_time` |
| `Item.time` | `item.time` | `item.frame_time` |
| `Layer.time` | `layer.time` | `layer.frame_time` |
| - | `keyframe.time` | `keyframe.frame_time` |
| `MarkerValue.duration` | `marker.duration` | `marker.frame_duration` |

Warning:
    `AVItem.frame_duration` is the **total duration in frames** (an integer),
    not the duration of a single frame in seconds (which is
    `1/frame_rate`). This differs from ExtendScript's `AVItem.frameDuration`
    which is the duration of one frame in seconds.

## Convenience Access Properties

### Project

`Project` provides filtered views of items that ExtendScript requires manual
filtering for:

```python
project.compositions   # list[CompItem] - all compositions
project.folders        # list[FolderItem] - all folders
project.footages       # list[FootageItem] - all footages
```

### FolderItem

`FolderItem` provides filtered item lists:

```python
folder.compositions    # list[CompItem] - compositions in the folder
folder.folders         # list[FolderItem] - subfolders
folder.footages        # list[FootageItem] - footages in the folder
```

### CompItem

`CompItem` provides filtered layer lists:

```python
comp.text_layers             # list[TextLayer]
comp.shape_layers            # list[ShapeLayer]
comp.camera_layers           # list[CameraLayer]
comp.light_layers            # list[LightLayer]
comp.parametric_mesh_layers  # list[ParametricMeshLayer]
comp.null_layers             # list[Layer]
comp.solid_layers            # list[AVLayer]
comp.adjustment_layers       # list[AVLayer]
comp.three_d_layers          # list[AVLayer]
comp.guide_layers            # list[AVLayer]
comp.solo_layers             # list[Layer]
comp.composition_layers      # list[AVLayer] - layers sourced from comps
comp.footage_layers          # list[AVLayer] - layers sourced from footages
comp.file_layers             # list[AVLayer] - layers sourced from files
comp.placeholder_layers      # list[AVLayer]
comp.av_layers               # list[AVLayer] - all AV layers
```

## Extra Attributes

py_aep exposes additional attributes parsed from the binary format that are
not available in ExtendScript:

### Property

| Attribute | Description |
|-----------|-------------|
| `dimensions` | Number of dimensions (1, 2, or 3) |
| `locked_ratio` | `True` if X/Y ratio is locked |
| `default_value` | The default value of the property |
| `last_value` | The last value before animation |
| `nb_options` | Number of options in a dropdown property |

### FootageItem

| Attribute | Description |
|-----------|-------------|
| `asset_type` | The footage type (`"placeholder"`, `"solid"`, `"file"`) |
| `start_frame` | The footage start frame |
| `end_frame` | The footage end frame |

### CompItem

| Attribute | Description |
|-----------|-------------|
| `time_scale` | Internal time scale divisor for keyframe times |
| `essential_graphics_controllers` | List of Essential Graphics controllers in the comp |
| `guides` | List of [Guide][py_aep.models.guide.Guide] objects (ruler guides for alignment) |
| `render_options` | The active 3D renderer's options |

### Layer

| Attribute | Description |
|-----------|-------------|
| `layer_type` | The layer type (`"AVLayer"`, `"Layer"`, `"CameraLayer"`, `"LightLayer"` `"ParametricMeshLayer"`) |

### RenderQueueItem

| Attribute | Description |
|-----------|-------------|
| `comment` | A comment describing the render queue item |
| `name` | The render settings template name |
| `settings` | Full render settings as a dict |

### OutputModule

| Attribute | Description |
|-----------|-------------|
| `file_template` | Raw file path template with variables like `[compName]` |
| `format_options` | Format-specific options (JPEG quality, EXR compression, etc.) |
| `settings` | Full output module settings as a dict |

## Enums

py_aep provides many enum classes across 8 modules, covering values that
ExtendScript exposes as plain integers or doesn't expose at all:

- Format options enums: `VideoCodec`, `AudioCodec`, `OpenExrCompression`, etc.
- Render settings enums: `FieldRender`, `MotionBlurSetting`, `DiskCacheSetting`, etc.
- Output module enums: `OutputChannels`, `OutputColorDepth`, `ResizeQuality`, etc.
- Font enums: `CTFontTechnology`, `CTFontType`, `CTScript`
- Text enums: `ComposerEngine`, `BoxAutoFitPolicy`, `LineOrientation`, etc.

## Gradient Colors

ExtendScript reports gradient color properties (`ADBE Vector Grad Colors`)
with `propertyValueType = NO_VALUE` and provides no `.value` accessor.
py_aep parses the underlying XML stored in the binary and exposes it as a
`Gradient` object on `Property.value`:

```python
gfill = contents.property("ADBE Vector Graphic - G-Fill")
colors = gfill.property("ADBE Vector Grad Colors")
gradient = colors.value  # Gradient instance

for stop in gradient.color_stops:
    print(stop.offset, stop.color)  # (red, green, blue) tuple

for stop in gradient.alpha_stops:
    print(stop.offset, stop.alpha)
```


## Output Module Format Options

ExtendScript provides no access to format-specific render settings. py_aep
parses these from the binary and exposes them:

- `CineonFormatOptions` - black/white points, gamma, bit depth
- `JpegFormatOptions` - quality, format type, scans
- `OpenExrFormatOptions` - compression, luminance/chroma, bit depth
- `PngFormatOptions` - bit depth, compression, HDR10 metadata
- `TargaFormatOptions` - bits per pixel, RLE compression
- `TiffFormatOptions` - LZW compression, byte order
- `XmlFormatOptions` - video/audio codec, frame rate, MPEG settings

## 3D Renderer Options

`CompItem.renderer` names the active 3D renderer, but ExtendScript exposes
nothing about that renderer's own settings — the Options dialog beside the
3D Renderer dropdown in Composition Settings. py_aep parses them from the
binary and exposes them on `CompItem.render_options`:

=== "py_aep"

    ```python
    comp.render_options["Quality"] = 61     # keyed by dialog label
    comp.render_options.quality = 61        # or as a typed attribute
    ```

The options available depend on the active renderer:

- `ClassicRenderOptions` — shadow map resolution
- `AdvancedRenderOptions` — quality, environment light shadow resolution and
  smoothness, casting box size and centre
- `Cinema4DRenderOptions` — quality
- `RayTracedRenderOptions` — none; see [Known Limitations](limitations.md)

Every option py_aep exposes is stored in the `.aep` and survives an After
Effects preferences reset.

Advanced 3D's casting box values are stored as fractions of the composition's
raw pixel dimensions and are exposed here as the pixel values the dialog shows.
Pixel aspect ratio is not applied, and resizing a composition rescales these
options in pixel terms because the stored fraction does not move — both are
After Effects' own behaviour.

## Stricter Write Validation

py_aep validates values like After Effects' *dialogs*, which is sometimes
stricter than ExtendScript's own setters. Where AE scripting accepts a
degenerate value and silently misbehaves, py_aep raises instead:

- **Render time spans**: AE scripting accepts a `timeSpanStart` before 0 or
  past the span end, then silently renders garbage (a span starting at -5
  renders 5 seconds of void lead-in; an end before the start renders a
  single frame, both with a `DONE` status - probed in AE 2026). py_aep
  rejects a negative start, a start at or past the end, and a duration
  below one frame. The *semantics* match ExtendScript: setting the start
  keeps the span end fixed (the duration is recomputed), setting the
  duration keeps the start.
- **Booleans**: AE coerces any truthy value, so `"no"` becomes `True`.
  py_aep boolean attributes and settings accept only `True` / `False`.

## Approximated Runtime Behaviors

Some ExtendScript methods gate their behavior on runtime state that only a
running After Effects has. py_aep implements the closest file-level
equivalent and documents the divergence:

- **`Project.auto_fix_expressions()`**: After Effects only rewrites
  expressions that are currently *erroring* - runtime state that is not
  stored in the project file (verified: broken and working expressions are
  chunk-identical on disk). py_aep instead replaces the quoted forms
  `"old_text"` / `'old_text'` in **every enabled expression**. Everything
  else matches AE (probed in AE 2026): both quote styles are fixed,
  disabled expressions are never touched, unquoted mentions are ignored,
  and quoted occurrences inside comments of a rewritten expression are
  replaced too. The one divergent case: an expression that evaluates
  cleanly but contains the quoted text is rewritten by py_aep, while AE
  leaves it alone.
- **`AVLayer` geometry methods** (`source_point_to_comp()`,
  `comp_point_to_source()`, `source_rect_at_time()`): After Effects
  evaluates these at the current playhead position, which py_aep reads as
  the comp's stored `time` attribute - deterministic per file, but it
  reflects wherever the playhead sat when the project was last saved. The
  two point conversions accept an optional `time` keyword (py_aep
  extension) to evaluate at an explicit time instead. Layers whose parent
  chain uses auto-orientation raise `NotImplementedError` (the transform
  math does not model it), as do text and shape layers for
  `source_rect_at_time()` (content bounds need glyph extents / shape
  geometry evaluation). `calculate_transform_from_points()` names its
  third parameter `point_bottom_left`: the AE guide calls it
  `pointBottomRight`, but After Effects treats it as the bottom-left
  corner (probed AE 2026; the guide's own example passes `bl`).
- **`TextDocument.reset_char_style()` / `reset_paragraph_style()`**: After
  Effects restores the *Character* / *Paragraph* panel defaults, which are
  application state rather than project data - they live in the AE
  preferences (`["Text Style Sheet"]` / `["Text Paragraph Sheet"]` in
  `Prefs-text.txt`), not in the `.aep`. py_aep reads those same sections
  from the preferences directory the project was parsed with (see
  `parse(..., ae_preferences_dir=...)`), so a reset restores *your* panel
  defaults exactly as AE would. Parsed without a preferences directory, it
  falls back to AE's factory values. Only the attributes present in those
  panel sheets are restored - which is why, like After Effects, a paragraph
  reset leaves `auto_hyphenate` untouched.
- **`TextDocument.baseline_locs`**: reports the layout After Effects
  persisted. The per-line pen origins and glyph advances exist only in that
  cache, so - unlike `composed_line_count` - this never recomposes; after a
  layout-affecting py-side write the values stay at the persisted layout
  (see `composition_stale`).
- **`Project.replace_font()`**: `no_font_locking` is accepted for parity and
  ignored. After Effects uses it to suppress the fallback font it picks when
  the target font lacks glyphs for the text; that is a runtime font-engine
  decision py_aep does not make, so py_aep always performs the direct
  replacement (it behaves as if `no_font_locking` were `True`). Like every
  py_aep text write, the layer's layout cache is left as-is (AE recomputes
  it on open), so glyph advances cached for the old font stay until then.
