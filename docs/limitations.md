# Known Limitations

This page documents limitations of py_aep that arise from the nature of
parsing a binary file format rather than querying a running After Effects
instance.


## Property.value_at_time Accuracy on spatial Properties (~0.015 Maximum Error)

`Property.value_at_time()` for spatial properties (position, 2D/3D) has a
systematic ±0.015 deviation from After Effects' `valueAtTime()`. This is
**not** a bug in the parser - it is caused by After Effects' internal spatial
evaluation pipeline.

**Evidence:** even a perfectly straight, LINEAR-interpolated path shows a
sinusoidal deviation pattern in After Effects' own output, peaking at ±0.011.
The same deviation appears regardless of whether the keyframe interpolation
type is LINEAR or BEZIER.

After Effects appears to process all spatial properties through an arc-length
reparameterisation pipeline (likely a polyline or spline approximation) that
does not degrade gracefully to exact linear interpolation for straight paths.

## Runtime-Only Attributes

Many ExtendScript attributes reflect the live state of After Effects and cannot
be derived from the `.aep` file alone:

| Attribute | Reason |
|-----------|--------|
| `Application.effects` | Installed effects on the system |
| `Application.fonts` | Installed fonts on the system |
| `Application.isRenderEngine` | Launch mode flag |
| `Application.isWatchFolder` | Launch mode flag |
| `Application.memoryInUse` | Runtime memory state |
| `Item.selected` | Runtime-only Selection state |
| `Project.dirty` | Unsaved changes flag |
| `RenderQueue.queueNotify` | Runtime state |
| `RenderQueue.rendering` | Runtime state |
| `Viewer.maximized` | Non-persisting window state |

## Composed Lines Are a Layout Cache

`TextDocument.composed_line_count`, `composed_line_range()` and
`composed_line_character_indexes_at()` read the line-layout cache After
Effects persisted into the `.aep` at save time. py_aep has no text engine
and cannot recompose text, so after py-side edits the cache goes stale.

This matches ExtendScript's own behavior for a TextDocument value that has
not been reapplied to a layer: the composed-line count stays cached, line
boundaries clamp to the current text, and lines falling wholly outside it
raise. The difference is that AE recomposes when the document is applied
back to a layer (`setValue`), while a file written by py_aep keeps the
stale cache until After Effects itself opens and resaves it. Character
and paragraph ranges are unaffected - they derive from the style runs,
which py_aep keeps consistent.

## Expressions

### Property.value When Expressions Are Enabled

When `Property.expression_enabled` is `True`, the `value` attribute contains
the **last static or keyframed value** stored in the binary file - not the
result of evaluating the expression. After Effects computes expression results
at runtime using its expression engine; py_aep has no expression evaluator.

```python
prop = layer.transform.property("ADBE Position")
if prop.expression_enabled:
    # prop.value is the pre-expression value, not the expression result
    print(prop.expression)  # the expression string is available
```

### Property.expression_error

`Property.expression_error` is always an empty string. After Effects computes
expression errors at runtime when it evaluates the expression engine; this
information is not stored in the binary `.aep` file.

## Property Metadata

### Property.default_value

Default values are set **heuristically** by the parser in `synthesis/`, not
read from the binary format. They are used for `Property.is_modified` checks.
Some default values may be inaccurate for non-standard property types.

### Property.units_text

`Property.units_text` is not read from the binary format, it is based on a
collection of samples. For some properties, the value may be an empty string
even though After Effects displays a unit string in the UI.

### Property.canSetExpression

`Property.can_set_expression` combines binary signals with a pure-logic
resolver. For effect parameters, an expressions-disabled flag in the
`pard` definition header is authoritative; the remaining logic covers
what After Effects determines at runtime from context: the layer type
(camera, light, etc.), whether the layer is 3D, whether position
dimensions are separated, and the light type. Small match-name tables
cover non-effect quirks (extrusion materials, text path options). The
result matches ExtendScript ground truth on 99.9% of 51,000+ validated
properties; the residual mismatches are instance-state cases (e.g.
plugin-supervised parameters whose enablement depends on other
parameter values).

### Property.canVaryOverTime

For effect parameters, `Property.can_vary_over_time` is derived from the
parameter definition (`pard`) flags byte, which matches the After Effects
SDK's `PF_ParamFlag_CANNOT_TIME_VARY`. For other properties it combines
the `tdb4` `can_vary_over_time` flag with the `no_value` flag (NO_VALUE
properties always report `canVaryOverTime = true` in ExtendScript). A
six-entry override table covers the residue (one light option that has no
pard, and the Puppet pin internals). Validated against ExtendScript ground
truth across 51,000+ properties covering every bundled and several
third-party effects, with zero mismatches.

### Property.min_value / Property.max_value

For effect parameters, the valid range is read from the parameter
definition (`pard`): plain integers for Integer controls, 16.16 fixed
point for Scalar controls, and 32-bit floats for Slider controls (a
non-finite float means that side is unbounded). A small override table
covers non-effect properties (transform, material, mask).

Known mismatch: about a dozen non-effect properties report bounds where
ExtendScript reports none - `ADBE Position_0`/`_1` and `ADBE Scale` carry
placeholder `[0.0]` bound chunks in the binary, and a few layer-style and
light properties carry synthesized bounds. Values are unaffected.

## Templates

Render settings and output module templates are not stored in the `.aep`
file - After Effects keeps them in the user preferences. Pass the AE
preferences directory to `parse()` to make them available:

```python
app = py_aep.parse("myproject.aep", ae_preferences_dir=prefs_dir)
rq_item = app.project.render_queue.add(comp)
print(rq_item.templates)  # available render settings templates
rq_item.output_modules[0].apply_template("TIFF Sequence with Alpha")
```

Without `ae_preferences_dir`, `RenderQueueItem.templates` and
`OutputModule.templates` return an empty list, and `RenderQueue.add()`
raises (it needs the default templates to build the new item's settings).
The settings of items already in the queue remain available through
`OutputModule.settings` and `RenderQueueItem.settings` either way.

## Color Space Profiles

`Project.working_space`, `Project.display_color_space` and
`FootageSource.media_color_space` are read/write, with the constraints below.
The binary chunks store the profile name plus either a small OCIO descriptor
JSON or the full ICC profile data (base64-encoded, up to ~50 KB).

**OCIO mode** (`color_management_system == OCIO`) needs no external files: the
color space is identified by name in a small JSON, so working space, display
space (a `(display, view)` pair) and footage media color space are all writable
directly.

**Adobe CMS mode** embeds the full ICC profile, which py_aep discovers at write
time from the installed Adobe Color directories, the per-user Adobe Color cache,
and the operating system's color-profile store (override the search path with
`Project.icc_profile_dirs`). The target profile must therefore be installed -
`ColorProfileNotFoundError` is raised otherwise. This covers `working_space`
and footage `media_color_space`. Notes:

- A handful of profiles (Apple RGB, Adobe RGB (1998), ColorMatch RGB, ROMM-RGB)
  are stored by After Effects as a private variant that differs by a few bytes
  from the distributed `.icc` file; py_aep embeds the installed copy, which AE
  still recognizes and re-saves, but the bytes are not identical to an AE save.
- The Windows Color System profiles `* wsRGB` and `* wscRGB` are generated by
  the Adobe Color Engine at runtime, but After Effects caches them as `.icc`
  files in the per-user Adobe Color directory
  (`%LOCALAPPDATA%\Adobe\Color\Profiles` on Windows), which py_aep scans, so
  they embed once After Effects has created them. `e-sRGB` has no `.icc` file on
  disk and cannot be embedded.

**Not writable:**

- `display_color_space` in Adobe CMS mode: Adobe uses the operating system's
  monitor profile, which is not stored in the project (`NotImplementedError`).
- The render-queue output color space in OCIO mode: After Effects identifies it
  by a 16-byte hash of a runtime-generated ICC wrapper that cannot be
  reproduced without AE's color engine.

Other color management settings (`color_management_system`,
`lut_interpolation_method`, `ocio_configuration_file`, `working_gamma`,
`linearize_working_space`, `linear_blending`,
`compensate_for_scene_referred_profiles`) are read/write and depend on no
embedded ICC data.

## Essential Properties

The UUID linkage between a precomp layer's Essential Property overrides and
their source-composition controller definitions is resolved:

- `Layer.essential_property_uuids` contains the override UUIDs from the
  layer's `LIST:OvG2`.
- `EssentialGraphicsController.uuid` contains the controller's identity UUID
  from the `LIST:CCtl` definition.
- `AVLayer.essential_property_controllers` resolves the link automatically,
  returning the source comp's controllers matched to the layer's overrides by
  shared UUID, in override order.

One caveat: After Effects synthesizes an
extra runtime-only "drop zone" controller (named e.g. `GropDropZone`) that is
**not stored in the file**, so it is absent from `motion_graphics_controllers`
and `motion_graphics_template_controller_count` is one lower than
ExtendScript's `motionGraphicsTemplateControllerCount` (by one per group). The media-replacement controller itself, by contrast, matches ExtendScript
exactly (no synthesized drop zone).

Media-replacement overrides on a precomp layer are parsed: the layer's
`"ADBE Layer Overrides"` group exposes its `ADBE Layer Source Alternate`
child, and these `Property` attributes are available:

- `Property.can_set_alternate_source` - `True` for a media-replacement slot
  (decoded from the slot's `blsi` item-id).
- `Property.alternate_source` - the replacement `AVItem`. After Effects wraps
  the replacement footage in a composition, so this is that wrapper comp.
  Set it with `Property.alternate_source = <value>`, which requires an existing
  slot; unlike the After Effects UI it does **not** auto-wrap a footage item
  in a composition, so pass the wrapper `CompItem` for an AE-faithful result.
- `Property.essential_property_source` - the source `AVLayer` a
  media-replacement override points at (matched via the controller's source
  comp/layer ids). `None` for Property-source essential properties, which are
  not yet resolved.

Other (non-media-replacement) override *values* are still not exposed: for
those overrides the `"ADBE Layer Overrides"` group parses with no children,
so ExtendScript's `numProperties`/`isModified` on the group (and its nested
`ADBE Layer Overrides Group` for a grouped override) are not reflected.

## Missing Classes

The following ExtendScript classes do not exist in py_aep:

| Class | Reason |
|-------|--------|
| `System` | OS/machine info - not stored in `.aep` |
| `FontsObject` | Runtime collection of installed fonts |
| `CharacterRange` | Text engine range object (AE 24.6+) |
| `ComposedLineRange` | Text engine range object (AE 24.6+) |
| `ParagraphRange` | Text engine range object (AE 24.6+) |
| `ItemCollection` | Use `project.items` (Python dict[int, Item]) instead |
| `LayerCollection` | Use `comp.layers` (Python list) instead |
| `Settings` | Application settings - methods only, not stored in `.aep` |
| `Preferences` | Application preferences - methods only, not stored in `.aep` |

## File Paths

File paths in `.aep` files are stored as they were saved on the original
system. They may be platform-specific (Windows backslashes vs. Unix forward
slashes) and may not resolve on the current system. `FileSource.file` returns
the path as stored without modification. `FileSource.missing_footage_path`
provides the path that After Effects would display for missing footage.

## Importing Footage (Project.import_file)

`Project.import_file()` creates footage from a file by reading the media
header (see [media_probe][py_aep.resolvers.media_probe]). After Effects caches
footage metadata (dimensions, duration, frame rate, alpha, audio) in the
project and does not re-read the media when the project is opened, so these
values are extracted from the source file at import time.

- **Supported import types**: `FOOTAGE` for still images, video, audio, and
  merged PSD/PSB; `COMP` for a layered Illustrator/PDF (`.ai`/`.pdf`) or
  Photoshop (`.psd`/`.psb`) file (one footage layer per source layer); and
  `COMP_CROPPED_LAYERS` for an SVG or a layered `.psd`/`.psb`. `PROJECT` import
  (importing an `.aep`/`.aet`) is not supported. An extension that the requested
  type does not cover raises `ValueError`.
- **Supported footage formats** (verified to open in After Effects): the
  still images PNG, JPEG, BMP, GIF, TGA, TIFF, OpenEXR, PSD/PSB and Radiance
  HDR; QuickTime MOV, M4V, WMV and MPEG video; WAV, AIFF, MP3, M4A and AAC
  audio; FBX scenes; SWF; and TXT/CSV/JSON/mgjson data footage.
  Image sequences are supported for the still-image formats. The same source
  builder backs `FootageItem.replace()`/`replace_with_sequence()` and
  `AVItem.set_proxy()`/`set_proxy_with_sequence()`.
- **SVG**: importable only as `COMP_CROPPED_LAYERS`, which converts the artwork
  into a composition of native vector shape layers (`ADBE Vector Layer`) - there
  is no file-referencing footage source. Importing an SVG as `FOOTAGE` raises.
  `<text>` / `<tspan>` are rendered as **outlined glyph shapes** (going beyond
  After Effects, whose own SVG import silently drops them); this requires the
  text's `font-family` to be installed - an unresolved font is skipped. Raster
  `<image>` and `<textPath>` are not yet rendered.
- **PSD/PSB**: as `FOOTAGE` it is imported as a single merged still (the `8BPS`
  merged-layer `opti` header is written so AE resolves it without stalling on a
  layer-interpretation modal). As `COMP`/`COMP_CROPPED_LAYERS` it becomes a
  composition with one footage layer per Photoshop layer (layer groups become
  nested compositions); a flattened (layerless) file becomes a one-layer
  composition of the merged still. Other unrecognized extensions raise.
- **Single-layer import** (py_aep extension - ExtendScript has no API for the
  "Choose Layer" option of AE's import dialog): setting
  `ImportOptions.layer_index` on a `FOOTAGE` import of a layered
  `.psd`/`.psb`/`.ai`/`.pdf` references that single layer, and
  `ImportOptions.layer_dimensions` selects Document vs Layer Size
  (`.psd`/`.psb` only - an AI/PDF layer's artwork bounds would require
  rendering the PDF content, so `"layer"` raises `NotImplementedError`
  there). The index is the layer's 0-based position in the list returned
  by [list_layers][py_aep.resolvers.source_layers.list_layers] (top layer
  first, the dropdown order); an index - not a name - selects the layer
  because layer names need not be unique, and AE's own dialog
  disambiguates duplicates by dropdown position. `FootageItem.replace()`
  takes the same optional `layer_index` argument; `layer_index=None`
  always replaces with the merged/whole document, consistent with
  `import_file`, and `py_aep.CURRENT_VALUE` rebinds the new file at the
  current source's stored layer index (PSD record index / AI document
  index).
- **`has_alpha` is a per-format heuristic**, not a full media decode. After
  Effects allocates an alpha channel for PNG/TIFF/BMP/GIF regardless of the
  file's actual channel count, treats JPEG as opaque, and derives alpha from
  the channel list (EXR), bit depth (TGA: 32-bit only), codec depth (MOV), or
  layer transparency and channel count (PSD/PSB: layered or >= 4 channels).
  These match AE's import for the tested samples.
- **Image-sequence dimensions**: image sequences - and PSD/TIFF stills - get a
  full format-specific `opti` asset-info header with the dimensions embedded
  (HDR carries them in `sspc` instead). An empty `opti` is written only for a
  single PNG/EXR/FBX still, where After Effects re-reads the located file on
  open.

## guessAlphaMode / guessPulldown

`FootageSource.guess_alpha_mode()` and `guess_pulldown()` are not implemented.
Both inspect the actual media at runtime (edge premultiplication detection,
3:2 pulldown cadence), which requires decoding the footage. When creating
footage, py_aep uses fixed defaults instead: alpha mode STRAIGHT (PREMULTIPLIED
for EXR), and pulldown OFF.
