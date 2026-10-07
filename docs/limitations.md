# Known Limitations

This page documents limitations of py_aep that arise from the nature of
parsing a binary file format rather than querying a running After Effects
instance.


## Property.value_at_time on spatial Properties

`Property.value_at_time()` on a spatial property (Position, Anchor Point,
an effect point) reproduces After Effects' own motion-path model, so it
matches `valueAtTime()` to the digits ExtendScript prints (verified to
1e-9 against AE 2026, including non-square pixel comps, normalized effect
points, roving runs and temporal auto-bezier) - including where AE itself
departs from the exact curve:

- **AE is not exact.** It measures distance along the path approximately,
  so even a straight LINEAR path is up to ~0.01 px off the exact line (a
  0->100 px segment reports 50.00078 at half time).
- **An in-side HOLD on a spatial property holds at the segment's START**,
  where a non-spatial property jumps to the next key's value - both as AE
  does.
- **A 2-D layer ignores Z.** `value`, a keyframe's `value` and
  `value_at_time()` report Z as 0 there, as AE does, while the file keeps
  the stored Z. That stored Z still counts in the path's length, and so in
  its timing and ease speeds, in both.

## Property.value_at_time on paths and Orientation

A mask path, a shape-layer path and an Orientation carry one temporal ease
per side rather than one per component, and After Effects blends the whole
value along that single eased progress - a path vertex by vertex, an
Orientation as a quaternion slerp along the shortest arc. Two keyframes
holding different vertex counts are handled the way After Effects handles
them: the shorter path is resampled up to the longer one first, bisecting
breadth-first (every segment in path order, then every half) and splitting
each segment with de Casteljau so the outline does not move.

All of it is verified per frame against AE 2026 - paths to 1e-4, which is
the float32 the vertices are stored as, and Orientation to 1e-8 - with one
representation caveat:

- **Near a Y orientation of +/-90 degrees the reported X and Z are not
  unique.** The two axes turn about the same line there, so only their sum
  is determined and any split of it describes the same rotation. After
  Effects is not self-consistent about which split it reports, switching
  between them from one frame to the next; py_aep reports the continuous
  one. The rotation itself is identical either way.

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

The same holds for the layer geometry methods:
`AVLayer.source_point_to_comp`, `AVLayer.comp_point_to_source` and
`AVLayer.source_rect_at_time` evaluate the transform chain (parents and the
active camera included) and the layer content from **pre-expression**
values. A layer whose transform, or a parent's, is driven by an expression
converts points as if the expression were off; After Effects uses the
expression results.

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

After Effects allows an expression on a property the Timeline shows, whose
value is not empty, that can vary over time, and - for an effect parameter -
whose parameter type is not a layer or mask reference. What the Timeline hides
depends on the layer (a 3D-only property on a 2D layer, another light type's
options, another renderer's material options) and, for an effect, on its
plugin. For a layer property, `Property.can_set_expression` models the layer's
state, so it follows py-side edits (the 3D switch, the light type, the comp's
renderer). For an effect parameter it reads the hidden flag After Effects
stores with each property.

Against every ExtendScript `canSetExpression` in the sample corpus, and on
solid, text, shape, 3D model and parametric mesh layers under each of the
Classic 3D, Advanced 3D and Cinema 4D renderers, the result matches except for
one case: a mask whose path was never stored reports no expressionable path in
py_aep, where After Effects shows a default rectangle. An effect parameter's
plugin can also hide or show parameters from the live values of others; py_aep
reports the state the file was saved in.

### Property.min_value / Property.max_value

About a dozen non-effect properties report bounds where ExtendScript reports
none - `ADBE Position_0`/`_1` and `ADBE Scale` carry placeholder `[0.0]` bound
chunks in the binary, and a few layer-style and light properties carry
synthesized bounds. A paint stroke's Diameter reports the 200 slider maximum
the file stores, where ExtendScript reports 2500. Values are unaffected.

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
pair in OCIO mode (the 16-byte id is computed from the `.ocio` configuration).

Footage imported into an **OCIO** project takes the input color space After
Effects assigns, read from the project's configuration: the first matching
file rule, or the `default` role of a configuration without file rules. A
replace keeps the footage's color space, as After Effects does, even when the
new file would match another rule; a proxy gets its own. A
`ColorSpaceNamePathSearch` rule is not modelled, and when the configuration
cannot be found the footage keeps an Adobe profile (with a warning).

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
(see [probe_media][py_aep.resolvers.media_probe.probe_media]). The limitations of importing
from a static file rather than through AE's live media engine:

- **`PROJECT` import is not supported** - importing an `.aep`/`.aet` raises. An
  extension a requested import type does not cover also raises `ValueError`.
- **Nikon NEF and Cinema 4D scenes are not importable** (`ValueError`). Camera
  Raw develops a NEF at a per-camera crop the file does not record, and a
  `.c4d` takes its size, frame rate and duration from the scene's render
  settings and timeline, which py_aep does not parse. Canon CRW imports.
- **SVG** imports only as `COMP_CROPPED_LAYERS` (native vector shape layers);
  importing an SVG as `FOOTAGE` raises. `<text>`/`<tspan>` require the
  `font-family` to be installed - an unresolved font is skipped - and raster
  `<image>` and `<textPath>` are not yet rendered. A radial gradient stretched
  by its `gradientTransform`, or by a non-square bounding box in
  `objectBoundingBox` units, needs an AE 2026 project: older versions have no
  gradient Scale/Rotation properties, so it renders as a circle there.
  Deliberate divergences from AE's own import (measured on AE 2026), where
  py_aep follows the SVG / CSS specifications:
    - **Placement.** AE moves the artwork vertically by up to 1.5 px, by an
      amount that depends on how the drawing's bounding box rounds to whole
      pixels and on its `<g>` nesting. py_aep keeps the SVG coordinates.
    - **Opacity attributes.** AE drops `stop-opacity`, `fill-opacity` and
      `stroke-opacity`; py_aep applies them - a gradient's in its alpha stops,
      a flat color's in the Fill or Stroke Opacity.
    - **Nested group opacity.** AE applies only one level of `opacity`
      (a 0.5 group inside a 0.5 group imports at 50 %); py_aep multiplies
      them (25 %).
    - **Stroke width under a transform.** AE keeps the SVG `stroke-width`
      even inside `scale(3)`; py_aep scales it with the drawing (by the
      square root of the transform's area factor), so strokes keep their
      rendered thickness.
    - **Units.** AE converts absolute units at 72 px per inch (`1pt` is
      1 px, `1mm` 2.835 px, `1em` 12 px); py_aep uses CSS's 96 px per inch
      (`1pt` is 1.333 px) and `1em` = the font size (16 px by default).
    - **Root size.** When the root's `width`/`height` differ from its
      `viewBox`, AE scales the drawing by them but still sizes the
      composition from the `viewBox`; py_aep keeps the drawing in `viewBox`
      units, so it fills the composition.
    - **Colors.** AE imports `#rrggbbaa`, `rgba()`, `hsl()` and `hsla()`
      colors, and a gradient with a single stop, as black; py_aep reads them
      (a single stop paints its own color).
    - **References.** AE ignores a `<use>` that uses the SVG 2 `href`
      (rather than `xlink:href`), and drops a shape whose gradient inherits
      its stops through an `href` chain; py_aep resolves both.
    - **Path data after `Z`.** A drawing command that follows `Z` without
      a move starts a new subpath at the closed one's start in py_aep; AE
      continues the same path.
    - **`auto` radii.** A `rx` / `ry` of `auto` takes the other radius in
      py_aep (SVG 2); AE reads it as 0 (a zero-width ellipse, a
      square-cornered rect).
  Clipping is not imported: a nested `<svg>` or `<symbol>` viewport is
  placed and scaled as AE places it, but py_aep does not clip its content
  to it (AE does), and it ignores `clip-path` and `mask`.
- **Layer-size dimensions for AI/PDF single-layer import** (and every layer
  of a `COMP_CROPPED_LAYERS` import) measure the layer's artwork box from the
  page content stream
  ([read_ai_layer_bounds][py_aep.resolvers.ai_bounds.read_ai_layer_bounds]),
  reproducing After Effects' own conservative estimate rather than the true
  visual extent. A cropped layer whose artwork reaches the 32768 pt limit
  keeps its true centre, where AE's 32-bit sum wraps it to the far side of
  the page. Three gaps:
    - **A document with more than one artboard diverges by design.** AE
      measures the *second* page there and reports every layer whose art is on
      the first artboard as empty (1x1); py_aep measures the first page and
      emits a `UserWarning`, since reproducing AE would mean discarding
      artwork.
    - **PDFs py_aep cannot read raise** `UnsupportedAiLayersError`:
      compressed object streams (`/ObjStm`), encryption, and content-stream
      filters other than Flate. Illustrator never writes these; other
      producers do.
    - **A font with no `/Widths`** falls back to built-in standard-14
      metrics, measured from AE 2026 itself: all fourteen faces, plus
      `/Arial` and `/TimesNewRoman`, which AE resolves onto them. Those are
      exact for character codes 32-126. Codes above 126 need the encoding's
      glyph names and are not tabulated, nor is an `/Encoding` `/Differences`
      array applied; both fall back to a nominal advance. A face outside the
      table, and Type 3 fonts, fall back to a generic estimate.
      Illustrator always embeds fonts with explicit widths, so this only
      affects PDFs from other producers.
- **Paths for the other platform are mapped by rule.** A project whose
  `platform` differs from the running system stores footage and render
  output paths in that platform's style. `C:\x` <-> `/x` mirrors how After
  Effects on Windows opens a macOS path (measured); other drives and UNC
  shares become `/Volumes/<drive or share>/...`, the usual macOS mount
  points, which is not measured against After Effects on macOS. A share
  mounted under another name needs the path fixed in After Effects. The
  relative-path fallback (`ascendcount`) is computed on the mapped paths, so
  a project and footage that keep their relative layout still relocate.
- **BMP and GIF image sequences are platform-specific.** Neither format has
  a dedicated AE importer, so AE tags them with the platform's generic still
  importer (`IMIO` on macOS, `STIL` on Windows). Measured in AE 2026 on both:
  an `IMIO` still opens on either platform, but an `IMIO` sequence never
  opens on Windows and a `STIL` sequence never opens on macOS - even in an
  AE-collected project. py-aep writes the code of the `platform` passed to
  `parse()`/`new()` (default: the running operating system) for stills and
  sequences, so a BMP/GIF sequence needs re-importing when the project
  changes platform.
- **`has_alpha` is a per-format heuristic**, not a full media decode. Alpha is
  inferred from the format and header - allocated for PNG/TIFF/BMP/GIF, opaque
  for JPEG, and derived from the channel list (EXR), bit depth (TGA), codec
  depth (MOV), descriptor (DPX) or channel count (Cineon), auxiliary
  alpha item (HEIC/HEIF), or layer transparency/channel count (PSD/PSB).
  These match AE's
  import for the tested samples but are not a guaranteed media-accurate decode.
  AE on Windows stores HEIC/HEIF without alpha, so py-aep does too when the
  project's `platform` is `"windows"`.
- **Footage is limited to 32767 px a side** (`ValueError`): After Effects
  reads the stored size as a signed 16-bit value, so a wider image opens with
  a negative width.
- **Input color profiles follow After Effects' per-format choices** (measured
  on AE 2026): an RGB TIFF/PSD, Illustrator/PDF page or Camera Raw file
  records its ICC profile (sRGB when untagged, ProPhoto RGB for Camera Raw);
  a grayscale, CMYK, Lab or indexed TIFF/PSD records only the name of its
  profile (or of AE's default for the mode) and is interpreted in the
  working space, as are DPX and Cineon, which record none. One gap: for an
  untagged 32-bit float RGB TIFF, AE embeds a linear sRGB profile it
  generates at import time (stamped with the import date), which py-aep
  cannot reproduce byte for byte; py-aep records sRGB, which renders the
  same in the tested projects.

### PSD layer styles (ImportOptions.layer_styles)

Editable-layer-styles imports translate each layer's effects descriptor
(`lmfx`/`lfx2`) into the comp layer's `ADBE Layer Styles` tree, byte-matched
against AE 2026 for the sample documents. The differences from AE:

- **Merging styles into footage** grows the layer's content box to hold the
  rasterized styles; a `COMP_CROPPED_LAYERS` import and
  `layer_dimensions="layer"` size the footage from that box. py_aep derives it
  from the style parameters the way After Effects 2026 does (measured on some
  900 single-style variants and every styled sample document), growing it
  from the masked content like AE (see below). One gap: a Stroke Emboss
  bevel, whose box was not measured, raises `NotImplementedError`.
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

### PSD layer content boxes (masks, fill layers)

Each per-layer footage of a layered PSD/PSB import is sized to the layer's
content box, which a `COMP_CROPPED_LAYERS` import and
`layer_dimensions="layer"` also crop to. py_aep derives it the way After
Effects 2026 does (byte-matched against AE for some 55 probe imports): an
enabled raster layer mask crops to where the layer's alpha and the mask are
both non-zero; a fill or shape layer spans the canvas; merging also cuts to
an enabled vector mask's path. The gaps:

- **Mask density and feather are not modeled**: a layer mask carrying either
  is ignored for the box (a `UserWarning` says so), so the footage is sized
  as if unmasked.
- **Vector-mask subpaths are united**: a subpath that subtracts from or
  intersects the others still widens the merged box to its own extent.
- **"Ignore layer styles"** (`layer_styles="ignore"`) handles vector masks like
  Editable mode; that mode's box was not measured.

## guessAlphaMode / guessPulldown

`FootageSource.guess_alpha_mode()` and `guess_pulldown()` are not implemented.
Both inspect the actual media at runtime (edge premultiplication detection,
3:2 pulldown cadence), which requires decoding the footage. When creating
footage, py_aep uses fixed defaults instead: alpha mode STRAIGHT (PREMULTIPLIED
for EXR), and pulldown OFF.

## Ray-traced 3D Renderer Options

`RayTracedRendererOptions` exposes nothing at all. The Ray-traced 3D renderer has
been removed since AE 2020 (17.0). Files using the renderer can be parsed and 
re-saved byte-exact, but there is nothing safe to expose, and no supported
version of After Effects can author a file that uses it.

## Project Versions

`py_aep.new(version)` takes the After Effects releases py_aep has a
file-format stamp for, 15 (CC 2018) to 18 and 22 to 26 (there was no After
Effects 19 to 21), and any newer release, which gets the After Effects 2026
project and stamp. `Application.version` takes any version; for a major
outside that list it changes the version alone and keeps the file-format
stamp the project already has. Setting it only
relabels the project, so it raises `ValueError` across a change After
Effects reads from the format version alone: the AE 23 layer record (a
22-or-older project relabelled 23 or later, or the reverse) and the AE 17
Media Replacement folder id. After Effects 2026 opens none of those
relabelled files. Open and re-save the project in the target release
instead.

Projects saved by After Effects CC (12.x) can be read and edited. They
store names as bare strings, so py_aep writes new names that way too, and
`Application.version` refuses to relabel them: every release it can stamp
reads names in the newer form. The settings those projects have no room
for (`working_gamma`, `gpu_accel_type`) raise on write.
