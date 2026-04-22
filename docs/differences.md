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

### CompItem

`CompItem` provides filtered layer lists:

```python
comp.text_layers         # list[TextLayer]
comp.shape_layers        # list[ShapeLayer]
comp.camera_layers       # list[CameraLayer]
comp.light_layers        # list[LightLayer]
comp.null_layers         # list[Layer]
comp.solid_layers        # list[AVLayer]
comp.adjustment_layers   # list[AVLayer]
comp.three_d_layers      # list[AVLayer]
comp.guide_layers        # list[AVLayer]
comp.solo_layers         # list[Layer]
comp.composition_layers  # list[AVLayer] - layers sourced from comps
comp.footage_layers      # list[AVLayer] - layers sourced from footages
comp.file_layers         # list[AVLayer] - layers sourced from files
comp.placeholder_layers  # list[AVLayer]
comp.av_layers           # list[AVLayer] - all AV layers
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
| `guides` | List of [Guide][py_aep.models.guide.Guide] objects (ruler guides for alignment) |

### Layer

| Attribute | Description |
|-----------|-------------|
| `layer_type` | The layer type (`"AVLayer"`, `"Layer"`, `"CameraLayer"`, `"LightLayer"`) |

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
