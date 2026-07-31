# Known Limitations

This page documents limitations of py_aep that arise from the nature of
parsing a binary file format rather than querying a running After Effects
instance.


## Property.value_at_time accuracy on spatial Properties (~0.015 Maximum Error)

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

## Composed Lines After py-side Edits

Point text never goes stale: its composed lines are derived from the
paragraphs. For box text, py_aep ships a composed-line resolver
(`resolvers/text_composition.py`, which needs `uharfbuzz` on Python 3.8+) that
recomposes lines like AE's single-line Latin composer, calibrated against each
document's own cache (line spans and baselines) so a calibrated document
recomposes freshly after every layout-affecting edit. The limitations are in
what it refuses or cannot cover:

- Out-of-envelope features are refused, never guessed: the every-line
  composer, optical or disabled auto kerning, enabled ligatures, tabs,
  no-break spaces, right-to-left scripts, vertical orientation, tsume,
  baseline shift, manual kerning, paragraph space before/after,
  non-default box vertical alignment / auto-fit / first-baseline
  alignment, case maps that change the text length, and fonts not
  installed on this machine.
- When the resolver is unavailable, refuses a document, or calibration
  fails, the stale cache remains with ExtendScript's un-reapplied-value
  semantics: counts stay cached, boundaries clamp to the current text,
  and lines falling wholly outside it raise. Check
  `TextDocument.composition_stale` to detect this - within the editing
  session only: the flag lives on the in-memory document object, so a
  py-written file that is re-parsed (or a layer duplicated after an
  edit) starts clean even though its persisted cache is still AE's old
  layout.
- The `.aep` file always keeps AE's own cache bytes untouched (AE
  requires them and recomposes on open); recomposition only feeds
  py-side reads.

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

`Property.can_set_expression` is resolved from binary signals plus a pure-logic
model of what After Effects decides at runtime (layer type, 3D, separated
position dimensions, light type). The residual mismatches against ExtendScript
are instance-state cases the file cannot capture - e.g. plugin-supervised
parameters whose enablement depends on the live values of other parameters.

### Property.min_value / Property.max_value

About a dozen non-effect properties report bounds where ExtendScript reports
none - `ADBE Position_0`/`_1` and `ADBE Scale` carry placeholder `[0.0]` bound
chunks in the binary, and a few layer-style and light properties carry
synthesized bounds. Values are unaffected.

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

Most color management settings are read/write, but embedding ICC profiles for
**Adobe CMS mode** has constraints. py_aep discovers the profile at write time
from the installed Adobe Color directories, the per-user Adobe Color cache, and
the OS color-profile store (override with `Project.icc_profile_dirs`), so the
target profile must be installed or `ColorProfileNotFoundError` is raised.

- A handful of profiles (Apple RGB, Adobe RGB (1998), ColorMatch RGB, ROMM-RGB)
  are stored by After Effects as a private variant that differs by a few bytes
  from the distributed `.icc` file; py_aep embeds the installed copy, which AE
  still recognizes and re-saves, but the bytes are not identical to an AE save.
- `e-sRGB` has no `.icc` file on disk and cannot be embedded. (`* wsRGB` /
  `* wscRGB` embed only after After Effects has cached them as `.icc` in
  `%LOCALAPPDATA%\Adobe\Color\Profiles`.)

**Not writable:**

- `display_color_space` in Adobe CMS mode: Adobe uses the operating system's
  monitor profile, which is not stored in the project (`NotImplementedError`).

The render-queue output color space is writable in **both** modes: an Adobe ICC
profile name in Adobe CMS mode, or any color space / role / alias / display-view
pair in OCIO mode (the 16-byte id is computed from the `.ocio` configuration -
it is the color space's `Guid`, a two-stage MurmurHash3-128).

## Essential Properties

Essential Property overrides on a precomp layer are parsed and linked to their
source-composition controllers by shared UUID
(`AVLayer.essential_property_controllers`). One residue remains:

- After Effects synthesizes an extra runtime-only "drop zone" controller
  (named e.g. `GropDropZone`) that is **not stored in the file**, so it is
  absent from `motion_graphics_controllers` and
  `motion_graphics_template_controller_count` is one lower than ExtendScript's
  `motionGraphicsTemplateControllerCount` (by one per group).

## Missing Classes

The following ExtendScript classes do not exist in py_aep:

| Class | Reason |
|-------|--------|
| `System` | OS/machine info - not stored in `.aep` |
| `FontsObject` | Runtime collection of installed fonts |
| `ItemCollection` | Use `project.items` (Python dict[int, Item]) instead |
| `LayerCollection` | Use `comp.layers` (Python list) instead |
| `Settings` | Application settings - methods only, not stored in `.aep` |

## File Paths

File paths in `.aep` files are stored as they were saved on the original
system. They may be platform-specific (Windows backslashes vs. Unix forward
slashes) and may not resolve on the current system. `FileSource.file` returns
the path as stored without modification. `FileSource.missing_footage_path`
provides the path that After Effects would display for missing footage.

## Importing Footage (Project.import_file)

`Project.import_file()` reads footage metadata (dimensions, duration, frame
rate, alpha, audio) from the source file at import time, since After Effects
caches those values in the project rather than re-reading the media on open
(see [media_probe][py_aep.resolvers.media_probe]). The limitations of importing
from a static file rather than through AE's live media engine:

- **`PROJECT` import is not supported** - importing an `.aep`/`.aet` raises. An
  extension a requested import type does not cover also raises `ValueError`.
- **SVG** imports only as `COMP_CROPPED_LAYERS` (native vector shape layers);
  importing an SVG as `FOOTAGE` raises. `<text>`/`<tspan>` require the
  `font-family` to be installed - an unresolved font is skipped - and raster
  `<image>` and `<textPath>` are not yet rendered.
- **Layer-size dimensions for AI/PDF single-layer import**: an AI/PDF layer's
  artwork bounds would require rendering the PDF content, so
  `ImportOptions.layer_dimensions = "layer"` raises `NotImplementedError` for
  `.ai`/`.pdf` (`.psd`/`.psb` are supported).
- **`has_alpha` is a per-format heuristic**, not a full media decode. Alpha is
  inferred from the format and header - allocated for PNG/TIFF/BMP/GIF, opaque
  for JPEG, and derived from the channel list (EXR), bit depth (TGA), codec
  depth (MOV), or layer transparency/channel count (PSD/PSB). These match AE's
  import for the tested samples but are not a guaranteed media-accurate decode.

### PSD layer styles (ImportOptions.layer_styles)

Editable-layer-styles imports translate each layer's effects descriptor
(`lmfx`/`lfx2`) into the comp layer's `ADBE Layer Styles` tree, byte-matched
against AE 2026 for the sample documents. The differences from AE:

- **Merging styles into footage stores approximate bounds.** After Effects
  rasterizes the styled layer at import and stores the style-expanded content
  box in the footage `opti` (plus the matching `data_size` cache); py_aep
  cannot run AE's style renderer, so it writes the raw layer bounds. AE
  restores the expanded box itself when it next opens the project (verified
  by resave), and tolerates the stale `data_size`. Because a
  `COMP_CROPPED_LAYERS` import (or `layer_dimensions="layer"`) derives the
  footage size and layer transforms from that expanded box - state AE does
  not recompute - those combinations raise `NotImplementedError` for layers
  that have styles.
- **Multi-instance styles are dropped whole** (imported as a disabled style),
  matching After Effects exactly - AE does not keep even a representable
  instance of e.g. a double stroke. py_aep emits a `UserWarning` where AE is
  silent.
- **Constructs AE cannot represent are dropped like AE drops them**: contours,
  anti-alias flags, a stroke's gradient fill (the stroke itself imports with
  its color), the Pattern Overlay pattern reference, a **noise-type gradient**
  (the owning style imports with every other parameter, only the gradient
  colors are omitted - matching AE), and Photoshop's master Scale Effects
  factor (values import unscaled, matching AE).
- **Styles on a layer GROUP are dropped** (the group's nested-comp layer
  keeps the plain disabled skeleton), matching After Effects exactly -
  probed with a drop shadow on a group (`lfxs` block), AE 2026 discards it
  silently. py_aep emits a `UserWarning` where AE is silent.
- **Legacy 4-character blend-mode spellings resolve exactly like AE.** Old
  writers store descriptor enums as zero-length 4-char typeIDs. A spliced
  27-mode probe pinned AE 2026's behavior: the 16 true-legacy typeIDs
  (`Nrml`, `Mltp`, `SftL`, ...) resolve, while the post-CS modes' typeIDs
  (`lbrn`, `vLit`, `fsub`, ...) do not - AE silently keeps the default
  blend mode. py_aep maps the same 16 and imports the rest as the default,
  emitting a `UserWarning` where AE is silent.
- **Only `lmfx`/`lfx2` descriptors are read** (plus `lfxs` for group
  headers). A pre-Photoshop-6 document carrying styles solely in the legacy
  `lrFX` block imports with the plain disabled skeleton.

## guessAlphaMode / guessPulldown

`FootageSource.guess_alpha_mode()` and `guess_pulldown()` are not implemented.
Both inspect the actual media at runtime (edge premultiplication detection,
3:2 pulldown cadence), which requires decoding the footage. When creating
footage, py_aep uses fixed defaults instead: alpha mode STRAIGHT (PREMULTIPLIED
for EXR), and pulldown OFF.

## Ray-traced 3D Renderer Options

`RayTracedRenderOptions` exposes nothing at all. The Ray-traced 3D renderer has
been removed since AE 2020 (17.0). Files using the renderer can be parsed and 
re-saved byte-exact, but there is nothing safe to expose, and no supported
version of After Effects can author a file that uses it.
