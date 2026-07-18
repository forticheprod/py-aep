"""Property override tables keyed by match name.

These lookup tables correct or supplement binary data:
- _PROPERTY_MIN_MAX: min/max bounds for non-effect properties
- _PROPERTY_DEFAULTS: fallback values for synthesized effect properties
- _ALWAYS_MODIFIED: match names always reported as modified by ExtendScript
- _ISSPATIAL_OVERRIDES: binary stores incorrect is_spatial value
- _NAME_OVERRIDES: binary stores incorrect display name
- _CANVARY_OVERRIDES: binary stores incorrect can_vary_over_time value
"""

from __future__ import annotations

# Bounds for properties without effect parameter definitions (effect
# parameters derive their valid range from the pard chunk).
_PROPERTY_MIN_MAX: dict[str, tuple[float, float]] = {
    # Transform
    "ADBE Opacity": (0, 100),
    # Geometry Options
    "ADBE Bevel Direction": (1, 2),
    # Material Options
    "ADBE Reflection Coefficient": (0, 100),
    "ADBE Glossiness Coefficient": (0, 100),
    "ADBE Fresnel Coefficient": (0, 100),
    "ADBE Transparency Coefficient": (0, 100),
    "ADBE Transp Rolloff": (0, 100),
    "ADBE Index of Refraction": (1, 5),
    # Mask properties
    "ADBE Mask Feather": (0, 32000),
    "ADBE Mask Opacity": (0, 100),
    "ADBE Mask Offset": (-32000, 32000),
}

# Non-effect properties that ExtendScript reports as having NO min/max
# bounds, but whose binary carries an all-zero `[0.0]` tdum/tduM placeholder
# (AE writes these for Scale and the separated-Position followers). The
# placeholder bytes are preserved on disk for round-trip fidelity; they are
# suppressed only when surfacing `min_value`/`max_value` so `has_min`/
# `has_max` match ExtendScript.
#
# `ADBE Time Remapping` also carries a `[0.0]` placeholder, but ExtendScript
# DOES report `hasMax=True`/`maxValue=0` for it, so it is intentionally
# excluded here (suppressing it would diverge from ground truth). Its
# spurious value-setter rejection is handled separately in `_get_max`.
_PLACEHOLDER_UNBOUNDED: frozenset[str] = frozenset(
    {
        "ADBE Scale",
        "ADBE Position_0",
        "ADBE Position_1",
        "ADBE Position_2",
        # Light/Camera props that carry an all-zero [0.0] tduM (and tdum):
        # ExtendScript reports hasMax=False for all, and hasMin=False for
        # Light Intensity (the others keep a real min via their fallback).
        "ADBE Light Falloff Distance",
        "ADBE Light Falloff Start",
        "ADBE Light Shadow Darkness",
        "ADBE Light Shadow Diffusion",
        "ADBE Light Intensity",
        "ADBE Camera Zoom",
        # Material-assignment 2D params carry all-zero [0.0] tdum/tduM;
        # ExtendScript reports hasMin=hasMax=False.
        "ADBE3D Material Texturre Offset",
        "ADBE3D Material Scale",
    }
)

# Non-effect properties ExtendScript reports as FULLY unbounded (hasMin=False
# AND hasMax=False) but for which a synthesis spec sets a min/max fallback
# (a UI range AE does not expose via the scripting bounds API). The bounds are
# suppressed on read so `has_min`/`has_max` and the value setter match
# ExtendScript; `is_modified`/`default_value` (which read the spec directly,
# not `min_value`) are unaffected.
_UNBOUNDED_MATCH_NAMES: frozenset[str] = frozenset(
    {
        "ADBE R Channel Blend",
        "ADBE G Channel Blend",
        "ADBE B Channel Blend",
        "ADBE Blend Interior",
        "ADBE Blend Ranges",
        "ADBE Vector Scale",
        "ADBE Vector Repeater Scale",
    }
)

# Default values for synthesized effect properties whose pard `default`
# field could not be verified against ExtendScript ground truth. Defaults
# normally come straight from the pard default field (validated across
# the whole sample corpus: 140/140 parameters match); an entry here is
# removable once a sample containing the parameter shows the pard
# prediction matches ExtendScript output.
_PROPERTY_DEFAULTS: dict[str, int | float | list[float]] = {
    "ADBE Lumetri-0130": 27,  # Color Space
    "ADBE Playgnd-0253": 0,  # Selection Map
    "ADBE Playgnd-0501": 0,  # Use Layer As Map
    "/fm_quality": 1,  # Roto Brush Quality
}

# ---------------------------------------------------------------------------

# Properties that ExtendScript always reports as is_modified=True, even when
# their value is at the default state. Most are effect CUSTOM_VALUE data blobs
# (curves, meshes, LUTs, separators) in specific GPU effects where AE considers
# the property modified on creation; the media-replacement slot
# `ADBE Layer Source Alternate` is likewise always reported modified by AE
# (confirmed on both its Essential-Properties override and Source-Options copies).
_ALWAYS_MODIFIED: frozenset[str] = frozenset(
    {
        # Media replacement source slot (Essential Properties + Source Options)
        "ADBE Layer Source Alternate",
        # Liquify
        "ADBE LIQUIFY-0014",
        # Lumetri Color
        "ADBE Lumetri-0001",
        "ADBE Lumetri-0004",
        "ADBE Lumetri-0024",
        "ADBE Lumetri-0032",
        "ADBE Lumetri-0039",
        "ADBE Lumetri-0042",
        "ADBE Lumetri-0047",
        "ADBE Lumetri-0060",
        "ADBE Lumetri-0073",
        "ADBE Lumetri-0085",
        "ADBE Lumetri-0093",
        "ADBE Lumetri-0095",
        "ADBE Lumetri-0096",
        "ADBE Lumetri-0098",
        "ADBE Lumetri-0099",
        "ADBE Lumetri-0100",
        "ADBE Lumetri-0106",
        "ADBE Lumetri-0108",
        "ADBE Lumetri-0110",
        "ADBE Lumetri-0112",
        "ADBE Lumetri-0122",
        "ADBE Lumetri-0125",
        "ADBE Lumetri-0126",
        "ADBE Lumetri-0129",
        # OCIO effects
        "ADBE OCIO CDL Transform-0006",
        "ADBE OCIO FILE Transform-0005",
    }
)

# ---------------------------------------------------------------------------
# Binary flag corrections
# ---------------------------------------------------------------------------

# Match names where the binary stores an incorrect is_spatial value.
_ISSPATIAL_OVERRIDES: dict[str, bool] = {
    "ADBE Orientation": True,
    "ADBE Fill-0002": True,  # Fill > Color
    "ADBE Mask Shape": True,
    "ADBE Vector Shape": True,  # shape-layer Path
    "ADBE Shadow Color": True,
    "ADBE Vector Fill Color": True,
    # Text-animator color properties report isSpatial=True in AE.
    "ADBE Text Fill Color": True,
    "ADBE Text Stroke Color": True,
    "ADBE 3DText Front RGB": True,
    "ADBE 3DText Bevel RGB": True,
    "ADBE 3DText Side RGB": True,
    "ADBE 3DText Back RGB": True,
    "ADBE HUE SATURATION-0003": True,  # Channel Range
    "ADBE CurvesCustom-0001": True,
    "ADBE Easy Levels-0002": True,
    "ADBE Easy Levels2-0002": True,
    "ADBE LIQUIFY-0014": True,
    "ADBE Lumetri-0032": True,
    "ADBE Lumetri-0047": True,
    "ADBE Lumetri-0073": True,
    "ADBE Lumetri-0085": True,
    "ADBE MESH WARP-0004": True,
    "ADBE RESHAPE-0006": True,
    "APC Colorama-0012": True,
}

# Match names where AE reports a different display name than the binary.
_NAME_OVERRIDES: dict[str, str] = {
    "ADBE Tint-0004": "",  # Swap Colors button - hidden in ExtendScript
    "ADBE 3D Tracker-0311": "Average Error: %.2f pixels",
    "ADBE 3D Tracker-0313": "Average Error: -",
    "ADBE Apply Color LUT-0001": "<LUT not set>",
    "ADBE Apply Color LUT2-0001": "<LUT not set>",
    "ADBE Arithmetic-0005": "Clipping",
    "ADBE Basic 3D-0004": "Specular Highlight",
    "ADBE Basic 3D-0005": "Preview",
    "ADBE Bulge-0007": "Pinning",
    "ADBE Camera Lens Blur-0021": "Edge Behavior",
    "ADBE Cell Pattern-0003": "Contextual Slider",
    "ADBE Channel Blur-0005": "Edge Behavior",
    "ADBE Circle-0004": "Contextual Slider",
    "ADBE Compound Blur-0003": "If Layer Sizes Differ",
    "ADBE Displacement Map-0007": "Edge Behavior",
    "ADBE Geometry2-0003": "Scale Height",
    "ADBE Geometry2-0004": "Scale Width",
    "ADBE LIQUIFY-0002": "Tool Options",
    "ADBE LIQUIFY-0017": "Clone Offset",
    "ADBE Lightning 2-0003": "Contextual Control",
    "ADBE Lightning-0025": "Simulation",
    "ADBE Noise Alpha-0005": "Contextual Control",
    "ADBE Noise Alpha2-0005": "Contextual Control",
    "ADBE Noise-0002": "Noise Type",
    "ADBE Noise-0003": "Clipping",
    "ADBE Noise2-0002": "Noise Type",
    "ADBE Noise2-0003": "Clipping",
    "ADBE OCIO Color Space Transform-0003": "Reset Control",
    "ADBE OCIO Display Transform-0005": "Reset Control",
    "ADBE OCIO Look Transform-0005": "Reset Control",
    "ADBE Paint Bucket-0005": "Contextual Slider",
    "ADBE Remove Color Matting-0002": "Clipping",
    "ADBE Scatter-0003": "Scatter Randomness",
    "ADBE Set Channels-0009": "If Layer Sizes Differ",
    "ADBE Set Matte2-0004": "If Layer Sizes Differ",
    "ADBE Set Matte3-0004": "If Layer Sizes Differ",
    "ADBE Time Displacement-0004": "If Layer Sizes Differ",
    "ADBE 3D Tracker-0001": "",
    "ADBE 3D Tracker-0011": "",
    "ADBE 3D Tracker-0400": "",
    "ADBE Ramp-0008": "",
    "ADBE SubspaceStabilizer-0001": "",
    "ADBE SubspaceStabilizer-0011": "",
    "ADBE Upscale-0003": "",
    "ADBE Upscale-0004": "",
}

# Match names where neither the tdb4 byte nor the pard param flags
# (PardChunk.param_flags bit 1, the authoritative source for effect
# parameters) yield the canVaryOverTime value ExtendScript reports,
# plus entries not yet verified against the pard flags. An entry is
# removable once a sample containing the parameter shows the pard
# prediction matches this table (and the ExtendScript JSON, when
# available).
_CANVARY_OVERRIDES: dict[str, bool] = {
    "ADBE Light Falloff Type": True,  # light option - no pard exists
    # Puppet pin internals are not regular effect parameters; the engine
    # dropdown's pard flags even disagree with ExtendScript.
    "ADBE FreePin3 Outlines": False,
    "ADBE FreePin3 Puppet Engine": False,
    "ADBE FreePin3 Mesh": False,
    "ADBE FreePin3 Mesh Tri Count": False,
    "ADBE FreePin3 PosPin Vtx Index": False,
}

# ---------------------------------------------------------------------------
# can_set_expression overrides
# ---------------------------------------------------------------------------

# Exact true exceptions to the broad can_set_expression reduction rules.
# These are the sampled outliers that remain expressionable even though
# their surrounding raw signatures are overwhelmingly false.
_CANSETEXPR_TRUE_OVERRIDES: frozenset[str] = frozenset(
    {
        "ADBE Block Dissolve-0002",
        "ADBE Block Dissolve-0003",
        "ADBE Cell Pattern-0003",
        "ADBE Circle-0004",
        "ADBE CurvesCustom-0001",
        "ADBE Easy Levels-0002",
        "ADBE Easy Levels2-0002",
        "ADBE Geometry2-0003",
        "ADBE Geometry2-0004",
        "ADBE HUE SATURATION-0003",
        "ADBE LIQUIFY-0014",
        "ADBE Lightning 2-0003",
        "ADBE Lumetri-0032",
        "ADBE Lumetri-0047",
        "ADBE Lumetri-0073",
        "ADBE Lumetri-0085",
        "ADBE MESH WARP-0004",
        "ADBE Paint Bucket-0005",
        "ADBE Point3D Control-0001",
        "ADBE RESHAPE-0006",
        "APC Colorama-0012",
        "ISL MochaShapeImporter-0001",
        "ISL MochaShapeImporter-0012",
    }
)

# Match names where canSetExpression is always False regardless of context.
_CANSETEXPR_FALSE_OVERRIDES: frozenset[str] = frozenset(
    {
        # Paint stroke properties
        "ADBE Paint Clone Time",
        "ADBE Paint Clone Position",
        "ADBE Paint Clone Time Shift",
        # Material coefficients (always-false, not 3D-dependent)
        "ADBE Reflection Coefficient",
        "ADBE Glossiness Coefficient",
        "ADBE Fresnel Coefficient",
        "ADBE Transparency Coefficient",
        "ADBE Transp Rolloff",
        "ADBE Index of Refraction",
        # Puppet pin
        "ADBE FreePin3 PosPin Scale",
        "ADBE FreePin3 PosPin Rotation",
        # Text on path
        "ADBE Text Reverse Path",
        "ADBE Text Perpendicular To Path",
        "ADBE Text Force Align Path",
        "ADBE Text First Margin",
        "ADBE Text Last Margin",
        # Text range-selector bounds (can keyframe but not expression);
        # the Units/Based On/Shape/Randomize props are already covered by
        # their can_vary_over_time=False.
        "ADBE Text Index Start",
        "ADBE Text Index End",
        "ADBE Text Index Offset",
        "ADBE Text Random Seed",
        # Vector stroke dashes / gaps / offset
        "ADBE Vector Stroke Dash 1",
        "ADBE Vector Stroke Dash 2",
        "ADBE Vector Stroke Dash 3",
        "ADBE Vector Stroke Gap 1",
        "ADBE Vector Stroke Gap 2",
        "ADBE Vector Stroke Gap 3",
        "ADBE Vector Stroke Offset",
        # Gradient highlight (length / angle never expressionable)
        "ADBE Vector Grad HiLite Length",
        "ADBE Vector Grad HiLite Angle",
        # Vector taper
        "ADBE Vector Taper StartWidthPx",
        "ADBE Vector Taper EndWidthPx",
        "ADBE Vector Taper Wave Cycles",
        # Light background (always false even on light layers)
        "ADBE Light Backgd Opacity",
        "ADBE Light Backgd Blur",
        # Light falloff
        "ADBE Light Falloff Start",
        "ADBE Light Falloff Distance",
        # Vec3D material properties (per-face material options - never expressionable)
        "ADBE Vec3D Front RGB",
        "ADBE Vec3D Front Ambient",
        "ADBE Vec3D Front Diffuse",
        "ADBE Vec3D Front Specular",
        "ADBE Vec3D Front Shininess",
        "ADBE Vec3D Front Metal",
        "ADBE Vec3D Front Reflection",
        "ADBE Vec3D Front Gloss",
        "ADBE Vec3D Front Fresnel",
        "ADBE Vec3D Front Xparency",
        "ADBE Vec3D Front XparRoll",
        "ADBE Vec3D Front IOR",
        "ADBE Vec3D Bevel RGB",
        "ADBE Vec3D Bevel Ambient",
        "ADBE Vec3D Bevel Diffuse",
        "ADBE Vec3D Bevel Specular",
        "ADBE Vec3D Bevel Shininess",
        "ADBE Vec3D Bevel Metal",
        "ADBE Vec3D Bevel Reflection",
        "ADBE Vec3D Bevel Gloss",
        "ADBE Vec3D Bevel Fresnel",
        "ADBE Vec3D Bevel Xparency",
        "ADBE Vec3D Bevel XparRoll",
        "ADBE Vec3D Bevel IOR",
        "ADBE Vec3D Side RGB",
        "ADBE Vec3D Side Ambient",
        "ADBE Vec3D Side Diffuse",
        "ADBE Vec3D Side Specular",
        "ADBE Vec3D Side Shininess",
        "ADBE Vec3D Side Metal",
        "ADBE Vec3D Side Reflection",
        "ADBE Vec3D Side Gloss",
        "ADBE Vec3D Side Fresnel",
        "ADBE Vec3D Side Xparency",
        "ADBE Vec3D Side XparRoll",
        "ADBE Vec3D Side IOR",
        "ADBE Vec3D Back RGB",
        "ADBE Vec3D Back Ambient",
        "ADBE Vec3D Back Diffuse",
        "ADBE Vec3D Back Specular",
        "ADBE Vec3D Back Shininess",
        "ADBE Vec3D Back Metal",
        "ADBE Vec3D Back Reflection",
        "ADBE Vec3D Back Gloss",
        "ADBE Vec3D Back Fresnel",
        "ADBE Vec3D Back Xparency",
        "ADBE Vec3D Back XparRoll",
        "ADBE Vec3D Back IOR",
        # Replace Source / Item Cache Entry
        "ADBE Layer Source Alternate",
        # Shadow Color (true=5 vs false=1024; accept rare mismatches)
        "ADBE Shadow Color",
        # Match-specific effect params whose broader signatures are still mixed.
    }
)

# Match names never expressionable on parametric mesh layers (AE 2026
# ExtendScript evidence from parametric_meshes.json): the material
# texture-projection params, Displacement Intensity, and Light
# Transmission (expressionable on regular 3D AV layers, not on mesh).
_PARAMETRIC_MESH_NO_EXPRESSION: frozenset[str] = frozenset(
    {
        "ADBE Light Transmission",
        "ADBE Displacement Intensity",
        "ADBE3D Material Projection",
        "ADBE3D Material Texturre Offset",
        "ADBE3D Material Rotation",
        "ADBE3D Material Scale",
    }
)

# Mesh option / bevel group -> owning mesh type (raw ldta value).
# ExtendScript allows expressions only on the ACTIVE mesh type's numeric
# streams; the inactive types' streams report canSetExpression=False.
# (Creation-side counterpart: `property._PARAMETRIC_MESH_ACTIVE_GROUPS`.)
_PARAMETRIC_MESH_GROUP_TYPE: dict[str, int] = {
    "ADBE CubeMeshOptionsSGrp": 0,
    "ADBE CubeBevelOptionsSGrp": 0,
    "ADBE SphereMeshOptionsSGrp": 1,
    "ADBE PlaneMeshOptionsSGrp": 2,
    "ADBE TorusMeshOptionsSGrp": 3,
    "ADBE ConeMeshOptionsSGrp": 4,
    "ADBE ConeBevelBevelSGrp": 4,
    "ADBE CylinderMeshOptionsSGrp": 5,
    "ADBE CylinderBevelOptionsSGrp": 5,
}

# Checkbox / toggle mesh streams: ExtendScript reports these as
# expressionable even in INACTIVE mesh option groups.
_PARAMETRIC_MESH_CHECKBOX_STREAMS: frozenset[str] = frozenset(
    {
        "ADBE SphereSliceCapsStrm",
        "ADBE SphereInvertSliceStrm",
        "ADBE TorusCapsStrm",
        "ADBE TorusInvertSliceStrm",
        "ADBE ConeTopCapStrm",
        "ADBE ConeBottomCapStrm",
        "ADBE ConeSliceCapsStrm",
        "ADBE ConeInvertSliceStrm",
        "ADBE CylinderTopCapStrm",
        "ADBE CylinderBottomCapStrm",
        "ADBE CylinderSliceCapsStrm",
        "ADBE CylinderInvertSliceStrm",
    }
)

# Generic always-False / 2D-only rules that DO allow expressions on
# parametric mesh layers (AE 2026 ExtendScript evidence).
_PARAMETRIC_MESH_EXPRESSION_OK: frozenset[str] = frozenset(
    {
        "ADBE Shadow Color",
        "ADBE Plane Curvature",
        "ADBE Plane Subdivision",
    }
)

# Match names that are expressionable only on 3D AV layers.
_CANSETEXPR_3D_ONLY: frozenset[str] = frozenset(
    {
        "ADBE Orientation",
        "ADBE Rotate X",
        "ADBE Rotate Y",
        "ADBE Ambient Coefficient",
        "ADBE Diffuse Coefficient",
        "ADBE Specular Coefficient",
        "ADBE Shininess Coefficient",
        "ADBE Metal Coefficient",
        "ADBE Light Transmission",
    }
)

# Match names that are expressionable only on 2D layers (not 3D).
_CANSETEXPR_2D_ONLY: frozenset[str] = frozenset(
    {
        "ADBE Plane Curvature",
        "ADBE Plane Subdivision",
    }
)

# Transform match names that are never expressionable on camera layers.
_CAMERA_NO_EXPRESSION: frozenset[str] = frozenset(
    {
        "ADBE Scale",
        "ADBE Opacity",
        # AE 2026 camera-options additions: ExtendScript reports
        # canSetExpression False for both (probed camera_defaults AE26).
        "ADBE Camera Focus Area Width",
        "ADBE Camera Split Blur Level",
    }
)

# Transform match names that are never expressionable on any light layer.
_LIGHT_NO_EXPRESSION: frozenset[str] = frozenset(
    {
        "ADBE Scale",
        "ADBE Opacity",
    }
)

# Additional match names not expressionable on ambient lights.
# Ambient lights support Color, Intensity, and (oddly) Rotate X/Y.
_LIGHT_AMBIENT_NO_EXPRESSION: frozenset[str] = frozenset(
    {
        "ADBE Position",
        "ADBE Anchor Point",
        "ADBE Orientation",
        "ADBE Rotate Z",
        "ADBE Light Cone Angle",
        "ADBE Light Cone Feather 2",
        "ADBE Light Falloff Type",
        "ADBE Light Shadow Darkness",
        "ADBE Light Shadow Diffusion",
    }
)

# Additional match names not expressionable on point / environment lights.
# Point lights have Position but not Orientation/Anchor/RotateX/Y/Z.
_LIGHT_POINT_NO_EXPRESSION: frozenset[str] = frozenset(
    {
        "ADBE Anchor Point",
        "ADBE Orientation",
        "ADBE Rotate X",
        "ADBE Rotate Y",
        "ADBE Rotate Z",
        "ADBE Light Cone Angle",
        "ADBE Light Cone Feather 2",
    }
)

# Spot and Parallel lights support all transform expressions.
# Only Cone properties are Spot-exclusive.
_LIGHT_SPOT_NO_EXPRESSION: frozenset[str] = frozenset()

_LIGHT_PARALLEL_NO_EXPRESSION: frozenset[str] = frozenset(
    {
        "ADBE Light Cone Angle",
        "ADBE Light Cone Feather 2",
    }
)
