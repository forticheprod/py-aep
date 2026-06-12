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

## Color Space Profiles Are Read-Only

`Project.working_space` and `Project.display_color_space` are **read-only**.
The binary chunks that store these settings contain both the profile name and
the full ICC profile data (base64-encoded binary, up to ~50 KB per profile).
Updating only the profile name would leave stale ICC data, producing a file
that After Effects may reject or silently revert to a default profile.

Generating the correct ICC data would require the Adobe ICC profile files
installed on disk (under `C:\Program Files (x86)\Common Files\Adobe\Color\` on
Windows), which cannot be assumed in all environments.  Bundling these profiles
is not feasible due to licensing constraints.

Other color management settings (`color_management_system`,
`lut_interpolation_method`, `ocio_configuration_file`, `working_gamma`,
`linearize_working_space`, `linear_blending`,
`compensate_for_scene_referred_profiles`) remain read/write as they do not
depend on embedded ICC data.

## Essential Properties

Essential Property override values on precomp layers are parsed as regular
properties under the `"Essential Properties"` group. The UUID linkage between
overrides and their source controller definitions is now partially exposed:

- `Layer.essential_property_uuids` contains the UUIDs of `LIST:OvG2`
  overrides on a precomp layer.
- `EssentialGraphicsController.uuid` contains the controller's identity UUID
  from the `LIST:CCtl` definition.
- Consumers can match UUIDs to link overrides to controllers, but py_aep does
  not perform this resolution automatically.

The following attributes are not parsed:

- `Property.essentialPropertySource`
- `Property.alternateSource`
- `Property.canSetAlternateSource`

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

- **Scope**: only `ImportAsType.FOOTAGE` is supported. `COMP`,
  `COMP_CROPPED_LAYERS`, and `PROJECT` import types are not.
- **Vector formats (SVG, AI, EPS) cannot be imported**: After Effects refuses
  to import these as footage (`ImportOptions.canImportAs(FOOTAGE)` is `false`);
  they are only importable as `COMP_CROPPED_LAYERS`, which converts the file
  into a composition of native vector shape layers (`ADBE Vector Layer`) rather
  than a file-referencing footage source. There is no footage `opti`/`sspc`
  representation to write, so these raise `ValueError` like any other
  unsupported extension.
- **Supported formats** (verified to open in After Effects): PNG, JPEG, BMP,
  GIF, TGA, TIFF, OpenEXR, PSD/PSB, QuickTime MOV, and WAV audio.
  Image sequences are supported for those still-image formats. The same source
  builder backs `FootageItem.replace()`/`replace_with_sequence()` and
  `AVItem.set_proxy()`/`set_proxy_with_sequence()`.
- **PSD/PSB import as merged footage only**: a `.psd`/`.psb` is imported as a
  single flattened still (the `8BPS` merged-layer `opti` header is written so
  AE resolves it without stalling on a layer-interpretation modal). Importing a
  PSD as a layered composition is not supported (see the import-type scope
  above). Other unrecognized extensions (and MP3, which has no duration prober)
  raise.
- **`has_alpha` is a per-format heuristic**, not a full media decode. After
  Effects allocates an alpha channel for PNG/TIFF/BMP/PSD/GIF regardless of the
  file's actual channel count, treats JPEG as opaque, and derives alpha from
  the channel list (EXR), bit depth (TGA: 32-bit only), or codec depth (MOV).
  These match AE's import for the tested samples.
- **Image-sequence dimensions**: the created `opti` asset-info chunk is
  minimal, so After Effects recomputes the sequence size from the first frame's
  display window on open.

## guessAlphaMode / guessPulldown

`FootageSource.guess_alpha_mode()` and `guess_pulldown()` are not implemented.
Both inspect the actual media at runtime (edge premultiplication detection,
3:2 pulldown cadence), which requires decoding the footage. When creating
footage, py_aep uses fixed defaults instead: alpha mode STRAIGHT (PREMULTIPLIED
for EXR), and pulldown OFF.
