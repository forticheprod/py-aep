"""Property specification tables for synthesis and defaults.

These tables define the canonical child properties for standard After Effects
property groups (Material Options, Layer Styles, etc.) and their default values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

from ..data.text_animator_pool import TEXT_ANIMATOR_POOL
from ..enums import PropertyValueType

if TYPE_CHECKING:
    from collections.abc import Sequence

_USE_VALUE = object()
"""Sentinel indicating `PropSpec.default_value` should mirror `value`."""


class PropSpec(NamedTuple):
    """Metadata for a synthesized property."""

    match_name: str
    auto_name: str
    value: int | float | list[float] | None
    pvt: PropertyValueType
    dimensions: int = 1
    is_spatial: bool = False
    color: bool = False
    integer: bool = False
    min_value: float | None = None
    max_value: float | None = None
    default_value: Any = _USE_VALUE
    can_vary_over_time: bool | None = None
    has_time_base: bool = False
    min_major: int | None = None
    spatial_flags: int | None = None
    cvot: int | None = None
    value_hint_type: int | None = None
    units_text: str | None = None
    """Explicit units string; when `None`, units resolve from
    `UNITS_TEXT_MAP` by match name (the default for most specs). Set
    for bulk-generated specs (e.g. the text-animator pool) to keep
    their units self-contained."""
    bound_chunks: bool | None = None
    """Whether AE writes `tdum`/`tduM` placeholder bound chunks for this
    property when materialized. `None` derives it from `min_value` /
    `max_value` (bounded, non-integer, non-color, non-spatial)."""
    chunk_bounds_are_hints: bool = False
    """Whether this property's binary `tdum`/`tduM` chunks hold UI slider
    hints rather than real bounds (mesh option streams store 0/100
    regardless of the actual clamp, e.g. Smoothing Angle is 0-180 with a
    0/100 tduM). When True, `min_value`/`max_value` resolve ONLY from the
    spec (`None` = unbounded) and the chunk values are ignored."""
    hint_bounds: tuple[float, float] | None = None
    """The `tdum`/`tduM` values AE writes when this property materializes -
    UI slider hints, which can differ from the real clamp (a Layer Styles
    Size is 0-250 with a 0/100 tduM). `None` keeps the family default
    (the `[0.0]` placeholders or no bound chunks at all)."""
    property_category: int | None = None
    """Override for the `tdb4` `_property_category` byte; `None` keeps the
    kind-branch default (integer 0x04, color 0x01, vector 0x09). Layer
    Styles angles use 0x06."""
    pad2a: int | None = None
    """Override for the `tdb4` `_pad2a` field; `None` keeps 0. Layer
    Styles colors carry 1."""


class GroupSpec(NamedTuple):
    """Metadata for a synthesized property group."""

    match_name: str
    auto_name: str
    min_major: int | None = None
    enable_flags: int = 1
    """`tdsb` enable-flags byte for the synthesized group: bit 0 is the
    `enabled` toggle, bit 1 the collapsed/UI bit. Defaults to `1`
    (enabled). The Layer Styles toggles are `2` (disabled - AE leaves
    every layer style off until one is added; a stray `1` would make AE
    apply the style, e.g. a default-red Color Overlay), and groups AE
    writes collapsed (Layer Styles parent, Blending Options) are `3`."""


# A property's (dimensions, is_spatial, color) kind is a pure function of its
# value type, so `_spec()` derives it from this table instead of every spec
# repeating it. (ExtendScript reports color properties as spatial.) Value types
# absent here - NO_VALUE, CUSTOM_VALUE, MARKER, TEXT_DOCUMENT - have no single
# kind, so those specs pass `dimensions`/`is_spatial`/`color` explicitly.
_PVT_KIND: dict[int, tuple[int, bool, bool]] = {
    PropertyValueType.ThreeD_SPATIAL: (3, True, False),
    PropertyValueType.ThreeD: (3, False, False),
    PropertyValueType.TwoD_SPATIAL: (2, True, False),
    PropertyValueType.TwoD: (2, False, False),
    PropertyValueType.OneD: (1, False, False),
    PropertyValueType.COLOR: (4, True, True),
    PropertyValueType.VARIABLE_FONT_AXIS: (1, False, False),
}


def _spec(
    match_name: str,
    auto_name: str,
    value: int | float | list[float] | None,
    pvt: PropertyValueType,
    **kwargs: Any,
) -> PropSpec:
    """Build a `PropSpec`, deriving `dimensions`/`is_spatial`/`color` from
    `pvt` via `_PVT_KIND` unless given explicitly."""
    if pvt in _PVT_KIND:
        dimensions, is_spatial, color = _PVT_KIND[pvt]
        kwargs.setdefault("dimensions", dimensions)
        kwargs.setdefault("is_spatial", is_spatial)
        kwargs.setdefault("color", color)
    return PropSpec(match_name, auto_name, value, pvt, **kwargs)


# Color min/max bounds used by Layer Styles and Material Shadow Color.
_COLOR_MIN: float = -3921568.62745098
_COLOR_MAX: float = 3921568.62745098

# Canonical children of "ADBE Material Options Group" as reported by
# ExtendScript.  Properties already parsed from binary are skipped.
_MATERIAL_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Casts Shadows",
        "Casts Shadows",
        0.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Light Transmission",
        "Light Transmission",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Accepts Shadows",
        "Accepts Shadows",
        1.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Accepts Lights",
        "Accepts Lights",
        1.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Shadow Color",
        "Shadow Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
        has_time_base=True,
        spatial_flags=0x07,
        value_hint_type=2,
    ),
    _spec(
        "ADBE Appears in Reflections",
        "Appears in Reflections",
        1.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Ambient Coefficient",
        "Ambient",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Diffuse Coefficient",
        "Diffuse",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Specular Coefficient",
        "Specular Intensity",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Shininess Coefficient",
        "Specular Shininess",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Metal Coefficient",
        "Metal",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Reflection Coefficient",
        "Reflection Intensity",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Glossiness Coefficient",
        "Reflection Sharpness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Fresnel Coefficient",
        "Reflection Rolloff",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Transparency Coefficient",
        "Transparency",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Transp Rolloff",
        "Transparency Rolloff",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Index of Refraction",
        "Index of Refraction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=5,
        has_time_base=True,
        value_hint_type=0xFFFF,
    ),
]

# Canonical children of "ADBE Extrsn Options Group".
_EXTRUSION_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Bevel Styles",
        "Bevel Style",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=4,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Bevel Direction",
        "Bevel Direction",
        1.0,
        PropertyValueType.OneD,
        integer=True,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
        has_time_base=True,
        cvot=0x00,
        value_hint_type=2,
    ),
    _spec(
        "ADBE Bevel Depth",
        "Bevel Depth",
        2.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Hole Bevel Depth",
        "Hole Bevel Depth",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Extrsn Depth",
        "Extrusion Depth",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=10000,
    ),
]

# Canonical children of "ADBE Plane Options Group".
_PLANE_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Plane Curvature",
        "Curvature",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Plane Subdivision",
        "Segments",
        4.0,
        PropertyValueType.OneD,
        min_value=2,
        max_value=256,
    ),
]

# Canonical children of "ADBE Audio Group".
_AUDIO_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Audio Levels",
        "Audio Levels",
        [0.0, 0.0],
        PropertyValueType.TwoD,
        min_value=-192,
        max_value=24,
    ),
]

# Canonical children of "ADBE Source Options Group".
_SOURCE_OPTIONS_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Layer Source Alternate",
        "Item Cache Entry",
        None,
        PropertyValueType.NO_VALUE,
        default_value=0,
        can_vary_over_time=True,
        has_time_base=True,
    ),
]

# Canonical children of "ADBE Effect Built In Params" (Compositing Options).
_COMPOSITING_OPTIONS_SPECS: list[PropSpec | GroupSpec] = [
    GroupSpec("ADBE Effect Mask Parade", "Masks"),
    _spec(
        "ADBE Effect Mask Opacity",
        "Effect Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Force CPU GPU",
        "GPU Rendering",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
]

_3D_COMPOSITING_OPTIONS_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Casts Shadows",
        "Casts Shadows",
        1.0,
        PropertyValueType.OneD,
        # ExtendScript reports isModified=True on mesh layers: the value
        # is On (1) but the shared Casts Shadows default is Off (0).
        default_value=0.0,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Accepts Shadows",
        "Accepts Shadows",
        1.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Accepts Lights",
        "Accepts Lights",
        1.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Appears in Reflections",
        "Appears in Reflections",
        1.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Shadow Color",
        "Shadow Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
        has_time_base=True,
        spatial_flags=0x07,
        value_hint_type=2,
    ),
]

# Canonical children of a mask atom ("ADBE Mask Atom").
# Mask Path is parsed separately (complex shape data) and only present in
# binary for some samples; placing it in specs ensures correct ordering.
_MASK_ATOM_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Mask Shape",
        "Mask Path",
        None,
        PropertyValueType.CUSTOM_VALUE,
        is_spatial=True,
    ),
    _spec(
        "ADBE Mask Feather",
        "Mask Feather",
        [0.0, 0.0],
        PropertyValueType.TwoD,
        min_value=0,
        max_value=32000,
    ),
    _spec(
        "ADBE Mask Opacity",
        "Mask Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec("ADBE Mask Offset", "Mask Expansion", 0.0, PropertyValueType.OneD),
]

# Canonical children of "ADBE Light Options Group" as reported by ExtendScript.
_LIGHT_SPECS: list[PropSpec | GroupSpec] = [
    GroupSpec("ADBE Light Env Atom", "Source"),
    _spec(
        "ADBE Light Backgd Visible",
        "Background Visible",
        0.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Light Backgd Opacity",
        "Background Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Light Backgd Blur",
        "Background Blur",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        has_time_base=True,
    ),
    _spec(
        "ADBE Light Intensity",
        "Intensity",
        100.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Light Color",
        "Color",
        [1.0, 1.0, 1.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "ADBE Light Cone Angle",
        "Cone Angle",
        90.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=180,
    ),
    _spec(
        "ADBE Light Cone Feather 2",
        "Cone Feather",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Light Falloff Type",
        "Falloff",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
    ),
    _spec(
        "ADBE Light Falloff Start",
        "Radius",
        500.0,
        PropertyValueType.OneD,
        min_value=0,
        has_time_base=True,
    ),
    _spec(
        "ADBE Light Falloff Distance",
        "Falloff Distance",
        500.0,
        PropertyValueType.OneD,
        min_value=0,
        has_time_base=True,
    ),
    _spec(
        "ADBE Casts Shadows",
        "Casts Shadows",
        0.0,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
    _spec(
        "ADBE Light Shadow Darkness",
        "Shadow Darkness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Light Shadow Diffusion",
        "Shadow Diffusion",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
]


# Canonical children of "ADBE3D Para Mat Parade" as reported by ExtendScript.
_PARA_MAT_SPEC: list[PropSpec] = [
    _spec(
        "ADBE3D Material Projection",
        "Projection Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec(
        "ADBE3D Material Texturre Offset",
        "Texture Offset",
        [0.0, 0.0],
        PropertyValueType.TwoD,
        units_text="percent",
    ),
    _spec(
        "ADBE3D Material Rotation",
        "Rotation",
        0.0,
        PropertyValueType.OneD,
        units_text="degrees",
    ),
    _spec(
        "ADBE3D Material Scale",
        "Scale",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        units_text="percent",
    ),
    _spec(
        "ADBE3D Base Color",
        "Base Color",
        [0.8, 0.8, 0.8, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "ADBE3D Roughness",
        "Roughness",
        30.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        units_text="percent",
    ),
    _spec(
        "ADBE3D Metallic",
        "Metallic",
        30.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        units_text="percent",
    ),
    _spec(
        "ADBE3D Emission",
        "Emission Color",
        [0.99607843137255, 0.99607843137255, 0.99607843137255, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "ADBE3D Emission Intensity",
        "Emission Intensity",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        units_text="percent",
    ),
    _spec(
        "ADBE3D Ambient",
        "Ambient Response",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        units_text="percent",
    ),
]

# Canonical children of "ADBE CubeMeshOptionsSGrp" as reported by ExtendScript.
# Every mesh option / bevel stream sets `chunk_bounds_are_hints=True`: their
# tdum/tduM store 0/100 UI slider hints regardless of the actual clamp
# (verified against AE 2026 ExtendScript min/max).
_CUBE_MESH_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE CubeWidthStrm",
        "Width",
        200.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CubeHeightStrm",
        "Height",
        200.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CubeDepthStrm",
        "Depth",
        200.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CubeSmoothingAngleStrm",
        "Smoothing Angle",
        40.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=180,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE CubeBevelOptionsSGrp".
_CUBE_BEVEL_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE CubeBevelRadiusStrm",
        "Radius",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CubeBevelSidesStrm",
        "Sides",
        20.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE SphereMeshOptionsSGrp".
_SPHERE_MESH_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE SphereRadiusStrm",
        "Radius",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE SphereSidesStrm",
        "Sides",
        48.0,
        PropertyValueType.OneD,
        min_value=3,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE SphereSliceCapsStrm",
        "Slice Caps",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE SphereStartAngleStrm",
        "Slice Start",
        0.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE SphereEndAngleStrm",
        "Slice End",
        360.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE SphereInvertSliceStrm",
        "Invert Slice",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE SphereSmoothingAngleStrm",
        "Smoothing Angle",
        40.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=180,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE PlaneMeshOptionsSGrp".
_PLANE_MESH_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE PlaneWidthStrm",
        "Width",
        200.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE PlaneLengthStrm",
        "Length",
        200.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        # Default 1: AE reports the active (empty) Plane group's Corner
        # Radius as 1/unmodified, while inactive groups store 0 (modified).
        "ADBE PlaneCornerRadiusStrm",
        "Corner Radius",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE PlaneCornerSidesStrm",
        "Corner Sides",
        20.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE TorusMeshOptionsSGrp".
_TORUS_MESH_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE TorusRingRadiusStrm",
        "Ring Radius",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusPipeRadiusStrm",
        "Pipe Radius",
        20.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusRingSidesStrm",
        "Ring Sides",
        48.0,
        PropertyValueType.OneD,
        min_value=3,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusPipeSidesStrm",
        "Pipe Sides",
        48.0,
        PropertyValueType.OneD,
        min_value=3,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusCapsStrm",
        "Caps",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusStartAngleStrm",
        "Slice Start",
        0.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusEndAngleStrm",
        "Slice End",
        360.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusInvertSliceStrm",
        "Invert Slice",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE TorusSmoothingAngleStrm",
        "Smoothing Angle",
        40.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=180,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE ConeMeshOptionsSGrp".
_CONE_MESH_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE ConeTopRadiusStrm",
        "Top Radius",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeBottomRadiusStrm",
        "Bottom Radius",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeHeightStrm",
        "Height",
        200.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeSidesStrm",
        "Sides",
        48.0,
        PropertyValueType.OneD,
        min_value=3,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeTopCapStrm",
        "Top Cap",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeBottomCapStrm",
        "Bottom Cap",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeSliceCapsStrm",
        "Slice Caps",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeStartAngleStrm",
        "Slice Start",
        0.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeEndAngleStrm",
        "Slice End",
        360.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeInvertSliceStrm",
        "Invert Slice",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeSmoothingAngleStrm",
        "Smoothing Angle",
        40.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=180,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE ConeBevelBevelSGrp".
_CONE_BEVEL_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE ConeBevelTopRadiusStrm",
        "Top Radius",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeBevelTopSidesStrm",
        "Top Sides",
        20.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeBevelBottomRadiusStrm",
        "Bottom Radius",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE ConeBevelBottomSidesStrm",
        "Bottom Sides",
        20.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE CylinderMeshOptionsSGrp".
_CYLINDER_MESH_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE CylinderRadiusStrm",
        "Radius",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderHeightStrm",
        "Height",
        200.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderSidesStrm",
        "Sides",
        48.0,
        PropertyValueType.OneD,
        min_value=3,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderTopCapStrm",
        "Top Cap",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderBottomCapStrm",
        "Bottom Cap",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderSliceCapsStrm",
        "Slice Caps",
        1.0,
        PropertyValueType.OneD,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderStartAngleStrm",
        "Slice Start",
        0.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderEndAngleStrm",
        "Slice End",
        360.0,
        PropertyValueType.OneD,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderInvertSliceStrm",
        "Invert Slice",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderSmoothingAngleStrm",
        "Smoothing Angle",
        40.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=180,
        units_text="degrees",
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE CylinderBevelOptionsSGrp".
_CYLINDER_BEVEL_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE CylinderBevelRadiusStrm",
        "Radius",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE CylinderBevelSidesStrm",
        "Sides",
        20.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
        chunk_bounds_are_hints=True,
    ),
]


# Canonical children of "ADBE Displacement Options" (parametric mesh
# layers). AE 26.0 does not write the group for a new mesh layer; 26.1+
# writes and reports it, so it is synthesized for ExtendScript parity but
# never materialized at creation.
_DISPLACEMENT_OPTIONS_SPEC: list[PropSpec] = [
    _spec(
        "ADBE Displacement Intensity",
        "Intensity",
        100.0,
        PropertyValueType.OneD,
        min_value=-1000,
        max_value=1000,
        units_text="percent",
    ),
    _spec(
        "ADBE Subdivision Count",
        "Subdivision Count",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=6,
        can_vary_over_time=False,
        chunk_bounds_are_hints=True,
    ),
]

# Canonical children of "ADBE Camera Options Group" as reported by ExtendScript.
_CAMERA_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Camera Zoom",
        "Zoom",
        0.0,
        PropertyValueType.OneD,
        min_value=1,
    ),
    _spec(
        "ADBE Camera Depth of Field",
        "Depth of Field",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Camera Focus Distance",
        "Focus Distance",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Camera Aperture",
        "Aperture",
        # AE's constant default aperture for a fresh camera (probed AE 2026
        # at comp widths 1920/1280/640 - width-independent, unlike Zoom and
        # Focus Distance, which are overridden per comp in synthesis).
        25.3093363329584,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Camera Blur Level",
        "Blur Level",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    # Added in After Effects 2026 (major 26); AE 25 reports 13 camera
    # options, AE 26 reports 15 (probed type.json AE25 vs camera_defaults
    # AE26). Gated so older-AE files keep the 13-option layout.
    _spec(
        "ADBE Camera Focus Area Width",
        "Focus Area Width",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        min_major=26,
        # AE writes tdum/tduM bound chunks but ExtendScript reports no max
        # (hasMax False): the chunk bounds are UI hints, so the spec (min 0,
        # no max) is authoritative.
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE Camera Split Blur Level",
        "Near, Far Blur Level",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        min_value=0,
        min_major=26,
        chunk_bounds_are_hints=True,
    ),
    _spec(
        "ADBE Iris Shape",
        "Iris Shape",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=10,
    ),
    _spec(
        "ADBE Iris Rotation",
        "Iris Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Iris Roundness",
        "Iris Roundness",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Iris Aspect Ratio",
        "Iris Aspect Ratio",
        1.0,
        PropertyValueType.OneD,
        min_value=0.00999999977648,
        max_value=100,
    ),
    _spec(
        "ADBE Iris Diffraction Fringe",
        "Iris Diffraction Fringe",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=500,
    ),
    _spec(
        "ADBE Iris Highlight Gain",
        "Highlight Gain",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Iris Highlight Threshold",
        "Highlight Threshold",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _spec(
        "ADBE Iris Hightlight Saturation",
        "Highlight Saturation",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

# Canonical children of "ADBE Text Path Options".
_TEXT_PATH_OPTIONS_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Text Path",
        "Path",
        0.0,
        PropertyValueType.CUSTOM_VALUE,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Reverse Path",
        "Reverse Path",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Text Perpendicular To Path",
        "Perpendicular To Path",
        1.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Text Force Align Path",
        "Force Alignment",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Text First Margin",
        "First Margin",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Text Last Margin",
        "Last Margin",
        0.0,
        PropertyValueType.OneD,
    ),
]

# Canonical children of "ADBE Text More Options".
_TEXT_MORE_OPTIONS_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Text Anchor Point Option",
        "Anchor Point Grouping",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=4,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Anchor Point Align",
        "Grouping Alignment",
        [0.0, 0.0],
        PropertyValueType.TwoD,
    ),
    _spec(
        "ADBE Text Render Order",
        "Fill & Stroke",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Character Blend Mode",
        "Inter-Character Blending",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=29,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Variable Font Spacing",
        "Variable Font Spacing",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
        min_major=26,
    ),
]

# Canonical children of "ADBE Vector Shape - Star" (Polystar path).
_VECTOR_STAR_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Shape Direction",
        "Shape Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Star Type",
        "Type",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Star Points",
        "Points",
        5.0,
        PropertyValueType.OneD,
        min_value=3,
    ),
    _spec(
        "ADBE Vector Star Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Star Rotation",
        "Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Vector Star Inner Radius",
        "Inner Radius",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Star Outer Radius",
        "Outer Radius",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Star Inner Roundess",
        "Inner Roundness",
        0.0,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Vector Star Outer Roundess",
        "Outer Roundness",
        0.0,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
]

# Shared vector property specs used across Fill, G-Fill, G-Stroke, Stroke,
# and Group lists.
_VECTOR_BLEND_MODE = _spec(
    "ADBE Vector Blend Mode",
    "Blend Mode",
    1.0,
    PropertyValueType.OneD,
    min_value=1,
    max_value=29,
    can_vary_over_time=False,
)
_VECTOR_COMPOSITE_ORDER = _spec(
    "ADBE Vector Composite Order",
    "Composite",
    1.0,
    PropertyValueType.OneD,
    min_value=1,
    max_value=2,
    can_vary_over_time=False,
)
_VECTOR_FILL_RULE = _spec(
    "ADBE Vector Fill Rule",
    "Fill Rule",
    1.0,
    PropertyValueType.OneD,
    min_value=1,
    max_value=2,
    can_vary_over_time=False,
)
_VECTOR_FILL_OPACITY = _spec(
    "ADBE Vector Fill Opacity",
    "Opacity",
    100.0,
    PropertyValueType.OneD,
    min_value=0,
    max_value=100,
)
_VECTOR_GRAD_TYPE = _spec(
    "ADBE Vector Grad Type",
    "Type",
    1.0,
    PropertyValueType.OneD,
    min_value=1,
    max_value=2,
    can_vary_over_time=False,
)
_VECTOR_GRAD_START_PT = _spec(
    "ADBE Vector Grad Start Pt",
    "Start Point",
    [0.0, 0.0],
    PropertyValueType.TwoD_SPATIAL,
)
_VECTOR_GRAD_END_PT = _spec(
    "ADBE Vector Grad End Pt",
    "End Point",
    [100.0, 0.0],
    PropertyValueType.TwoD_SPATIAL,
)
_VECTOR_GRAD_HILITE_LENGTH = _spec(
    "ADBE Vector Grad HiLite Length",
    "Highlight Length",
    0.0,
    PropertyValueType.OneD,
    min_value=-100,
    max_value=100,
)
_VECTOR_GRAD_HILITE_ANGLE = _spec(
    "ADBE Vector Grad HiLite Angle",
    "Highlight Angle",
    0.0,
    PropertyValueType.OneD,
)
# Grad Scale / Grad Rotation were added to the gradient fill/stroke groups in
# AE 2026 (major 26); 2018-2025 stop at HiLite Angle -> Colors. Probed across
# AE CC 2018, 2022, 2023, 2024, 2025, 2026 (only 26.0 exposes them).
_VECTOR_GRAD_SCALE = _spec(
    "ADBE Vector Grad Scale",
    "Scale",
    [100.0, 100.0],
    PropertyValueType.TwoD,
    min_major=26,
)
_VECTOR_GRAD_ROTATION = _spec(
    "ADBE Vector Grad Rotation",
    "Rotation",
    0.0,
    PropertyValueType.OneD,
    min_major=26,
)
_VECTOR_GRAD_COLORS = _spec(
    "ADBE Vector Grad Colors",
    "Colors",
    None,
    PropertyValueType.NO_VALUE,
    is_spatial=True,
)
_VECTOR_STROKE_OPACITY = _spec(
    "ADBE Vector Stroke Opacity",
    "Opacity",
    100.0,
    PropertyValueType.OneD,
    min_value=0,
    max_value=100,
)
_VECTOR_STROKE_WIDTH = _spec(
    "ADBE Vector Stroke Width",
    "Stroke Width",
    2.0,
    PropertyValueType.OneD,
    min_value=0,
)
_VECTOR_STROKE_LINE_CAP = _spec(
    "ADBE Vector Stroke Line Cap",
    "Line Cap",
    1.0,
    PropertyValueType.OneD,
    min_value=1,
    max_value=3,
    can_vary_over_time=False,
)
_VECTOR_STROKE_LINE_JOIN = _spec(
    "ADBE Vector Stroke Line Join",
    "Line Join",
    1.0,
    PropertyValueType.OneD,
    min_value=1,
    max_value=3,
    can_vary_over_time=False,
)
_VECTOR_STROKE_MITER_LIMIT = _spec(
    "ADBE Vector Stroke Miter Limit",
    "Miter Limit",
    4.0,
    PropertyValueType.OneD,
    min_value=1,
)

# Canonical children of "ADBE Vector Graphic - Fill".
_VECTOR_FILL_SPECS: list[PropSpec] = [
    _VECTOR_BLEND_MODE,
    _VECTOR_COMPOSITE_ORDER,
    _VECTOR_FILL_RULE,
    _spec(
        "ADBE Vector Fill Color",
        "Color",
        [1.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _VECTOR_FILL_OPACITY,
]

# Canonical children of "ADBE Vector Graphic - G-Fill".
_VECTOR_G_FILL_SPECS: list[PropSpec] = [
    _VECTOR_BLEND_MODE,
    _VECTOR_COMPOSITE_ORDER,
    _VECTOR_FILL_RULE,
    _VECTOR_GRAD_TYPE,
    _VECTOR_GRAD_START_PT,
    _VECTOR_GRAD_END_PT,
    _VECTOR_GRAD_HILITE_LENGTH,
    _VECTOR_GRAD_HILITE_ANGLE,
    _VECTOR_GRAD_SCALE,
    _VECTOR_GRAD_ROTATION,
    _VECTOR_GRAD_COLORS,
    _VECTOR_FILL_OPACITY,
]

# Canonical children of "ADBE Vector Graphic - G-Stroke".
_VECTOR_G_STROKE_SPECS: list[PropSpec | GroupSpec] = [
    _VECTOR_BLEND_MODE,
    _VECTOR_COMPOSITE_ORDER,
    _VECTOR_GRAD_TYPE,
    _VECTOR_GRAD_START_PT,
    _VECTOR_GRAD_END_PT,
    _VECTOR_GRAD_HILITE_LENGTH,
    _VECTOR_GRAD_HILITE_ANGLE,
    _VECTOR_GRAD_SCALE,
    _VECTOR_GRAD_ROTATION,
    _VECTOR_GRAD_COLORS,
    _VECTOR_STROKE_OPACITY,
    _VECTOR_STROKE_WIDTH,
    _VECTOR_STROKE_LINE_CAP,
    _VECTOR_STROKE_LINE_JOIN,
    _VECTOR_STROKE_MITER_LIMIT,
    GroupSpec("ADBE Vector Stroke Dashes", "Dashes"),
    GroupSpec("ADBE Vector Stroke Taper", "Taper"),
    GroupSpec("ADBE Vector Stroke Wave", "Wave"),
]

# Canonical children of "ADBE Vector Graphic - Stroke".
_VECTOR_STROKE_SPECS: list[PropSpec] = [
    _VECTOR_BLEND_MODE,
    _VECTOR_COMPOSITE_ORDER,
    _spec(
        "ADBE Vector Stroke Color",
        "Color",
        [1.0, 1.0, 1.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _VECTOR_STROKE_OPACITY,
    _VECTOR_STROKE_WIDTH,
    _VECTOR_STROKE_LINE_CAP,
    _VECTOR_STROKE_LINE_JOIN,
    _VECTOR_STROKE_MITER_LIMIT,
]

# Canonical children of "ADBE Vector Stroke Dashes".
_VECTOR_STROKE_DASHES_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Stroke Dash 1",
        "Dash",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Stroke Gap 1",
        "Gap",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Stroke Dash 2",
        "Dash 2",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Stroke Gap 2",
        "Gap 2",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Stroke Dash 3",
        "Dash 3",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Stroke Gap 3",
        "Gap 3",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Stroke Offset",
        "Offset",
        0.0,
        PropertyValueType.OneD,
    ),
]

# Canonical children of "ADBE Vector Stroke Taper".
_VECTOR_STROKE_TAPER_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Taper Length Units",
        "Length Units",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Taper Start Length",
        "Start Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Taper End Length",
        "End Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Taper StartWidthPx",
        "Start Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Taper EndWidthPx",
        "End Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Taper Start Width",
        "Start Width",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Taper End Width",
        "End Width",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Taper Start Ease",
        "Start Ease",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Taper End Ease",
        "End Ease",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
]

# Canonical children of "ADBE Vector Stroke Wave".
_VECTOR_STROKE_WAVE_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Taper Wave Amount",
        "Amount",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Taper Wave Units",
        "Units",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Taper Wavelength",
        "Wavelength",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Taper Wave Cycles",
        "Cycles",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Taper Wave Phase",
        "Phase",
        0.0,
        PropertyValueType.OneD,
    ),
]

# Canonical children of "ADBE Vector Group" (shape group container).
_VECTOR_GROUP_SPECS: list[PropSpec] = [
    _VECTOR_BLEND_MODE,
]

# Canonical children of "ADBE Vector Transform Group".
_VECTOR_TRANSFORM_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Anchor",
        "Anchor Point",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Scale",
        "Scale",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Skew",
        "Skew",
        0.0,
        PropertyValueType.OneD,
        min_value=-85,
        max_value=85,
    ),
    _spec(
        "ADBE Vector Skew Axis",
        "Skew Axis",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Vector Rotation",
        "Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Vector Group Opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]


def _vec3d_face_specs(face: str) -> list[PropSpec]:
    """Return 12 material property specs for one face (Front/Bevel/Side/Back)."""
    return [
        _spec(
            f"ADBE Vec3D {face} RGB",
            f"{face} Color",
            [1.0, 0.0, 0.0, 1.0],
            PropertyValueType.COLOR,
            min_value=_COLOR_MIN,
            max_value=_COLOR_MAX,
        ),
        _spec(
            f"ADBE Vec3D {face} Ambient",
            f"{face} Ambient",
            100.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Diffuse",
            f"{face} Diffuse",
            50.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Specular",
            f"{face} Specular Intensity",
            50.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Shininess",
            f"{face} Specular Shininess",
            5.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Metal",
            f"{face} Metal",
            100.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Reflection",
            f"{face} Reflection Intensity",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Gloss",
            f"{face} Reflection Sharpness",
            100.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Fresnel",
            f"{face} Reflection Rolloff",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} Xparency",
            f"{face} Transparency",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} XparRoll",
            f"{face} Transparency Rolloff",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _spec(
            f"ADBE Vec3D {face} IOR",
            f"{face} Index of Refraction",
            1.0,
            PropertyValueType.OneD,
            min_value=1,
            max_value=5,
        ),
    ]


# Canonical children of "ADBE Vector Materials Group" (shape material options).
_VECTOR_MATERIALS_SPECS: list[PropSpec] = [
    spec
    for face in ("Front", "Bevel", "Side", "Back")
    for spec in _vec3d_face_specs(face)
]

# Canonical children of "ADBE Vector Shape - Ellipse".
_VECTOR_ELLIPSE_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Shape Direction",
        "Shape Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Ellipse Size",
        "Size",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Ellipse Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
]

# Canonical children of "ADBE Vector Shape - Rect".
_VECTOR_RECT_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Shape Direction",
        "Shape Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Rect Size",
        "Size",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Rect Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Rect Roundness",
        "Roundness",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
]

# Canonical children of "ADBE Vector Repeater Transform".
_VECTOR_REPEATER_TRANSFORM_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Repeater Anchor",
        "Anchor Point",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Repeater Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Repeater Scale",
        "Scale",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Repeater Rotation",
        "Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Vector Repeater Opacity 1",
        "Start Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Repeater Opacity 2",
        "End Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

# Canonical children of "ADBE Vector Filter - Repeater".
_VECTOR_REPEATER_SPECS: list[PropSpec | GroupSpec] = [
    _spec(
        "ADBE Vector Repeater Copies",
        "Copies",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Repeater Offset",
        "Offset",
        0.0,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Vector Repeater Order",
        "Composite",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    GroupSpec("ADBE Vector Repeater Transform", "Transform"),
]

# Shape-element child specs (from AE 2026 ExtendScript ground truth via
# export_project_json; min/max/units match what ExtendScript reports).

# "ADBE Vector Shape - Group" (Path): Shape Direction + the bezier path.
_VECTOR_PATH_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Shape Direction",
        "Shape Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Shape",
        "Path",
        None,
        PropertyValueType.CUSTOM_VALUE,
        is_spatial=True,
    ),
]

# "ADBE Vector Filter - Merge".
_VECTOR_MERGE_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Merge Type",
        "Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=5,
        can_vary_over_time=False,
    ),
]

# "ADBE Vector Filter - Offset".
_VECTOR_OFFSET_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Offset Amount",
        "Amount",
        10.0,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Vector Offset Line Join",
        "Line Join",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Vector Offset Miter Limit",
        "Miter Limit",
        4.0,
        PropertyValueType.OneD,
        min_value=1,
    ),
    _spec(
        "ADBE Vector Offset Copies",
        "Copies",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec("ADBE Vector Offset Copy Offset", "Copy Offset", 1.0, PropertyValueType.OneD),
]

# "ADBE Vector Filter - PB" (Pucker & Bloat).
_VECTOR_PUCKER_BLOAT_SPECS: list[PropSpec] = [
    _spec("ADBE Vector PuckerBloat Amount", "Amount", 10.0, PropertyValueType.OneD),
]

# "ADBE Vector Filter - RC" (Round Corners).
_VECTOR_ROUND_CORNERS_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector RoundCorner Radius",
        "Radius",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
]

# "ADBE Vector Filter - Trim" (Trim Paths).
_VECTOR_TRIM_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Trim Start",
        "Start",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Trim End",
        "End",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec("ADBE Vector Trim Offset", "Offset", 0.0, PropertyValueType.OneD),
    _spec(
        "ADBE Vector Trim Type",
        "Trim Multiple Shapes",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
]

# "ADBE Vector Filter - Twist".
_VECTOR_TWIST_SPECS: list[PropSpec] = [
    _spec("ADBE Vector Twist Angle", "Angle", 10.0, PropertyValueType.OneD),
    _spec(
        "ADBE Vector Twist Center",
        "Center",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
]

# "ADBE Vector Filter - Roughen" (Wiggle Paths).
_VECTOR_ROUGHEN_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Roughen Size",
        "Size",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Roughen Detail",
        "Detail",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Roughen Points",
        "Points",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec("ADBE Vector Temporal Freq", "Wiggles/Second", 2.0, PropertyValueType.OneD),
    _spec(
        "ADBE Vector Correlation",
        "Correlation",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec("ADBE Vector Temporal Phase", "Temporal Phase", 0.0, PropertyValueType.OneD),
    _spec("ADBE Vector Spatial Phase", "Spatial Phase", 0.0, PropertyValueType.OneD),
    _spec(
        "ADBE Vector Random Seed",
        "Random Seed",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=10000,
    ),
]

# Canonical children of "ADBE Vector Wiggler Transform".
_VECTOR_WIGGLER_TRANSFORM_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Wiggler Anchor",
        "Anchor Point",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Wiggler Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
    _spec(
        "ADBE Vector Wiggler Scale",
        "Scale",
        [0.0, 0.0],
        PropertyValueType.TwoD,
    ),
    _spec("ADBE Vector Wiggler Rotation", "Rotation", 0.0, PropertyValueType.OneD),
]

# "ADBE Vector Filter - Wiggler" (Wiggle Transform).
_VECTOR_WIGGLER_SPECS: list[PropSpec | GroupSpec] = [
    _spec(
        "ADBE Vector Xform Temporal Freq",
        "Wiggles/Second",
        2.0,
        PropertyValueType.OneD,
    ),
    _spec(
        "ADBE Vector Correlation",
        "Correlation",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec("ADBE Vector Temporal Phase", "Temporal Phase", 0.0, PropertyValueType.OneD),
    _spec("ADBE Vector Spatial Phase", "Spatial Phase", 0.0, PropertyValueType.OneD),
    _spec(
        "ADBE Vector Random Seed",
        "Random Seed",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=10000,
    ),
    GroupSpec("ADBE Vector Wiggler Transform", "Transform"),
]

# "ADBE Vector Filter - Zigzag" (Zig Zag).
_VECTOR_ZIGZAG_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Vector Zigzag Size",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _spec(
        "ADBE Vector Zigzag Detail",
        "Ridges per segment",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Vector Zigzag Points",
        "Points",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
]

# Text-selector child specs (AE 2026 ExtendScript ground truth).

# "ADBE Text Range Advanced" - the Range Selector's Advanced subgroup.
_TEXT_RANGE_ADVANCED_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Text Range Units",
        "Units",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Range Type2",
        "Based On",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=4,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Selector Mode",
        "Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=6,
    ),
    _spec(
        "ADBE Text Selector Max Amount",
        "Amount",
        100.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Range Shape",
        "Shape",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=6,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Selector Smoothness",
        "Smoothness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Text Levels Max Ease",
        "Ease High",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Levels Min Ease",
        "Ease Low",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Randomize Order",
        "Randomize Order",
        0.0,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Random Seed",
        "Random Seed",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=10000,
    ),
]

# "ADBE Text Selector" - Range Selector.
_TEXT_RANGE_SELECTOR_SPECS: list[PropSpec | GroupSpec] = [
    _spec(
        "ADBE Text Percent Start",
        "Start",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Percent End",
        "End",
        100.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Percent Offset",
        "Offset",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Index Start",
        "Start",
        0.0,
        PropertyValueType.OneD,
        min_value=-99999,
        max_value=99999,
    ),
    _spec(
        "ADBE Text Index End",
        "End",
        0.0,
        PropertyValueType.OneD,
        min_value=-99999,
        max_value=99999,
    ),
    _spec(
        "ADBE Text Index Offset",
        "Offset",
        0.0,
        PropertyValueType.OneD,
        min_value=-99999,
        max_value=99999,
    ),
    GroupSpec("ADBE Text Range Advanced", "Advanced"),
]

# "ADBE Text Wiggly Selector".
_TEXT_WIGGLY_SELECTOR_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Text Selector Mode",
        "Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=6,
    ),
    _spec(
        "ADBE Text Wiggly Max Amount",
        "Max Amount",
        100.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Wiggly Min Amount",
        "Min Amount",
        -100.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _spec(
        "ADBE Text Range Type2",
        "Based On",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=4,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Temporal Freq",
        "Wiggles/Second",
        2.0,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Text Character Correlation",
        "Correlation",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "ADBE Text Temporal Phase",
        "Temporal Phase",
        0.0,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Text Spatial Phase",
        "Spatial Phase",
        0.0,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
    _spec("ADBE Text Wiggly Lock Dim", "Lock Dimensions", 0.0, PropertyValueType.OneD),
    _spec(
        "ADBE Text Wiggly Random Seed",
        "Random Seed",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=10000,
    ),
]

# "ADBE Text Expressible Selector" - Expression Selector.
_TEXT_EXPRESSIBLE_SELECTOR_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Text Range Type2",
        "Based On",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=4,
        can_vary_over_time=False,
    ),
    _spec(
        "ADBE Text Expressible Amount",
        "Amount",
        [100.0, 100.0, 100.0],
        PropertyValueType.ThreeD,
        min_value=-100,
        max_value=100,
    ),
]

# Canonical children of "ADBE Blend Options Group".
# tdb4 canon from the psd_layer_styles*.aep fixtures: the global-light
# angles are vector-typed with value hint 2 and no bound chunks; Fill
# Opacity carries the 0/100 slider hints; the channel/interior/range
# toggles are integer-typed with the default 0xFFFF hint.
_BLEND_OPTIONS_SPECS: list[PropSpec | GroupSpec] = [
    _spec(
        "ADBE Global Angle2",
        "Global Light Angle",
        120.0,
        PropertyValueType.OneD,
        value_hint_type=2,
    ),
    _spec(
        "ADBE Global Altitude2",
        "Global Light Altitude",
        30.0,
        PropertyValueType.OneD,
        value_hint_type=2,
    ),
    GroupSpec("ADBE Adv Blend Group", "Advanced Blending"),
]

_ADV_BLEND_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Layer Fill Opacity2",
        "Fill Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
        value_hint_type=0xFFFF,
        hint_bounds=(0.0, 100.0),
    ),
    _spec(
        "ADBE R Channel Blend",
        "Red",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        integer=True,
    ),
    _spec(
        "ADBE G Channel Blend",
        "Green",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        integer=True,
    ),
    _spec(
        "ADBE B Channel Blend",
        "Blue",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        integer=True,
    ),
    _spec(
        "ADBE Blend Interior",
        "Blend Interior Styles as Group",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        integer=True,
    ),
    _spec(
        "ADBE Blend Ranges",
        "Use Blend Ranges from Source",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
        integer=True,
    ),
]


def _build_text_animator_pool_specs() -> list[PropSpec]:
    """Build the `ADBE Text Animator Properties` pool from baked data.

    The pool is a fixed set AE exposes for every text animator; py
    synthesizes it so the group matches ExtendScript. Units are carried
    on the spec (`units_text`) to keep the bulk table self-contained.
    """
    specs: list[PropSpec] = []
    for e in TEXT_ANIMATOR_POOL:
        pvt = PropertyValueType(e["pvt"])
        # AE writes the [0.0] placeholder tdum/tduM for animatable 1D
        # animator scalars (Tracking Amount, Rotation, Skew Axis, the Hues)
        # even though ExtendScript exposes no min/max; a materialized one
        # that lacks them is rejected ("missing data in file"). Bounded 1D
        # entries already get the bounds via _bound_chunks_hint.
        unbounded_1d = (
            pvt == PropertyValueType.OneD
            and e["min"] is None
            and e["max"] is None
            and e["cv"] is not False
        )
        specs.append(
            _spec(
                e["mn"],
                e["name"],
                e["value"],
                pvt,
                # dimensions/is_spatial/color derive from pvt (_PVT_KIND).
                min_value=e["min"],
                max_value=e["max"],
                # canVary defaults True for the pool; only record False.
                can_vary_over_time=False if e["cv"] is False else None,
                units_text=e["units"],
                bound_chunks=True if unbounded_1d else None,
            )
        )
    return specs


_TEXT_ANIMATOR_POOL_SPECS: list[PropSpec] = _build_text_animator_pool_specs()

# Canonical children for Layer Styles sub-groups.

_DROP_SHADOW_SPECS: list[PropSpec] = [
    _spec(
        "dropShadow/mode2",
        "Blend Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "dropShadow/color",
        "Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "dropShadow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "dropShadow/useGlobalAngle",
        "Use Global Light",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _spec("dropShadow/localLightingAngle", "Angle", 120.0, PropertyValueType.OneD),
    _spec(
        "dropShadow/distance",
        "Distance",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=30000,
    ),
    _spec(
        "dropShadow/chokeMatte",
        "Spread",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "dropShadow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _spec(
        "dropShadow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "dropShadow/layerConceals",
        "Layer Knocks Out Drop Shadow",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
]

_INNER_SHADOW_SPECS: list[PropSpec] = [
    _spec(
        "innerShadow/mode2",
        "Blend Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "innerShadow/color",
        "Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "innerShadow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "innerShadow/useGlobalAngle",
        "Use Global Light",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _spec("innerShadow/localLightingAngle", "Angle", 120.0, PropertyValueType.OneD),
    _spec(
        "innerShadow/distance",
        "Distance",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=30000,
    ),
    _spec(
        "innerShadow/chokeMatte",
        "Choke",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "innerShadow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _spec(
        "innerShadow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_OUTER_GLOW_SPECS: list[PropSpec] = [
    _spec(
        "outerGlow/mode2",
        "Blend Mode",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "outerGlow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "outerGlow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "outerGlow/AEColorChoice",
        "Color Type",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec(
        "outerGlow/color",
        "Color",
        [1.0, 1.0, 0.74509803921569, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "outerGlow/gradient",
        "Colors",
        None,
        PropertyValueType.NO_VALUE,
        is_spatial=True,
        can_vary_over_time=True,
    ),
    _spec(
        "outerGlow/gradientSmoothness",
        "Gradient Smoothness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "outerGlow/glowTechnique",
        "Technique",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec(
        "outerGlow/chokeMatte",
        "Spread",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "outerGlow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _spec(
        "outerGlow/inputRange",
        "Range",
        50.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
    ),
    _spec(
        "outerGlow/shadingNoise",
        "Jitter",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_INNER_GLOW_SPECS: list[PropSpec] = [
    _spec(
        "innerGlow/mode2",
        "Blend Mode",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "innerGlow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "innerGlow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "innerGlow/AEColorChoice",
        "Color Type",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec(
        "innerGlow/color",
        "Color",
        [1.0, 1.0, 0.74509803921569, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "innerGlow/gradient",
        "Colors",
        None,
        PropertyValueType.NO_VALUE,
        is_spatial=True,
        can_vary_over_time=True,
    ),
    _spec(
        "innerGlow/gradientSmoothness",
        "Gradient Smoothness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "innerGlow/glowTechnique",
        "Technique",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec(
        "innerGlow/innerGlowSource",
        "Source",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec(
        "innerGlow/chokeMatte",
        "Choke",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "innerGlow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _spec(
        "innerGlow/inputRange",
        "Range",
        50.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
    ),
    _spec(
        "innerGlow/shadingNoise",
        "Jitter",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_BEVEL_EMBOSS_SPECS: list[PropSpec] = [
    _spec(
        "bevelEmboss/bevelStyle",
        "Style",
        2.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=5,
    ),
    _spec(
        "bevelEmboss/bevelTechnique",
        "Technique",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
    ),
    _spec(
        "bevelEmboss/strengthRatio",
        "Depth",
        100.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=1000,
    ),
    _spec(
        "bevelEmboss/bevelDirection",
        "Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _spec(
        "bevelEmboss/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _spec(
        "bevelEmboss/softness",
        "Soften",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=16,
    ),
    _spec(
        "bevelEmboss/useGlobalAngle",
        "Use Global Light",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _spec("bevelEmboss/localLightingAngle", "Angle", 120.0, PropertyValueType.OneD),
    _spec(
        "bevelEmboss/localLightingAltitude", "Altitude", 30.0, PropertyValueType.OneD
    ),
    _spec(
        "bevelEmboss/highlightMode",
        "Highlight Mode",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "bevelEmboss/highlightColor",
        "Highlight Color",
        [1.0, 1.0, 1.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "bevelEmboss/highlightOpacity",
        "Highlight Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "bevelEmboss/shadowMode",
        "Shadow Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "bevelEmboss/shadowColor",
        "Shadow Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "bevelEmboss/shadowOpacity",
        "Shadow Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_SATIN_SPECS: list[PropSpec] = [
    _spec(
        "chromeFX/mode2",
        "Blend Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "chromeFX/color",
        "Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "chromeFX/opacity",
        "Opacity",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec("chromeFX/localLightingAngle", "Angle", 19.0, PropertyValueType.OneD),
    _spec(
        "chromeFX/distance",
        "Distance",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=250,
    ),
    _spec(
        "chromeFX/blur",
        "Size",
        14.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _spec(
        "chromeFX/invert",
        "Invert",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
]

_COLOR_OVERLAY_SPECS: list[PropSpec] = [
    _spec(
        "solidFill/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "solidFill/color",
        "Color",
        [1.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "solidFill/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_GRADIENT_OVERLAY_SPECS: list[PropSpec] = [
    _spec(
        "gradientFill/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "gradientFill/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "gradientFill/gradient",
        "Colors",
        None,
        PropertyValueType.NO_VALUE,
        is_spatial=True,
        can_vary_over_time=True,
    ),
    _spec(
        "gradientFill/gradientSmoothness",
        "Gradient Smoothness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec("gradientFill/angle", "Angle", 90.0, PropertyValueType.OneD),
    _spec(
        "gradientFill/type",
        "Style",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=5,
    ),
    _spec(
        "gradientFill/reverse",
        "Reverse",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _spec(
        "gradientFill/align",
        "Align with Layer",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _spec(
        "gradientFill/scale",
        "Scale",
        100.0,
        PropertyValueType.OneD,
        min_value=10,
        max_value=150,
    ),
    _spec(
        "gradientFill/offset",
        "Offset",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
]

_PATTERN_OVERLAY_SPECS: list[PropSpec] = [
    _spec(
        "patternFill/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "patternFill/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "patternFill/align",
        "Link with Layer",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _spec(
        "patternFill/scale",
        "Scale",
        100.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=1000,
    ),
    _spec(
        "patternFill/phase",
        "Offset",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
    ),
]

_STROKE_SPECS: list[PropSpec] = [
    _spec(
        "frameFX/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _spec(
        "frameFX/color",
        "Color",
        [1.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _spec(
        "frameFX/size", "Size", 3.0, PropertyValueType.OneD, min_value=1, max_value=250
    ),
    _spec(
        "frameFX/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _spec(
        "frameFX/style",
        "Position",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
    ),
]

# AE 2026 tdb4/bounds canon for Layer Styles leaves, keyed by the leaf's
# match-name suffix (byte-diffed from the psd_layer_styles*.aep fixtures).
# The menu/toggle leaves are integer-typed with value hint 1; angles are
# integer-typed with property category 0x06 and the default 0xFFFF hint;
# scalars keep the vector kind with a 0xFFFF hint and carry the UI slider
# hints (NOT the real clamp) in tdum/tduM; colors add `_pad2a` = 1.
# The enum/angle/scalar classification below is the single source of truth:
# `models/project.py` `_STYLE_TDB4_CANON` is built from these same tables so
# the write-time tdb4 stamp cannot drift from the synthesis-time one. Keep the
# two in sync - inlining these onto the per-style specs would fork them.
_STYLE_ENUM_SUFFIXES = frozenset(
    {
        "mode2",
        "highlightMode",
        "shadowMode",
        "useGlobalAngle",
        "layerConceals",
        "AEColorChoice",
        "glowTechnique",
        "innerGlowSource",
        "bevelStyle",
        "bevelTechnique",
        "bevelDirection",
        "invert",
        "type",
        "reverse",
        "align",
        "style",
    }
)
_STYLE_ANGLE_SUFFIXES = frozenset(
    {"localLightingAngle", "localLightingAltitude", "angle"}
)
_STYLE_HINT_BOUNDS: dict[str, tuple[float, float]] = {
    "opacity": (0.0, 100.0),
    "highlightOpacity": (0.0, 100.0),
    "shadowOpacity": (0.0, 100.0),
    "chokeMatte": (0.0, 100.0),
    "noise": (0.0, 100.0),
    "shadingNoise": (0.0, 100.0),
    "gradientSmoothness": (0.0, 100.0),
    "inputRange": (1.0, 100.0),
    "strengthRatio": (1.0, 1000.0),
    "softness": (0.0, 16.0),
    "distance": (0.0, 100.0),
    "blur": (0.0, 100.0),
    "size": (1.0, 100.0),
}
# Full-match-name exceptions to the suffix rules.
_STYLE_HINT_BOUNDS_EXCEPTIONS: dict[str, tuple[float, float]] = {
    "chromeFX/distance": (1.0, 100.0),
    "bevelEmboss/blur": (0.0, 250.0),
    "gradientFill/scale": (10.0, 150.0),
    "patternFill/scale": (1.0, 1000.0),
}


def _style_leaf_canon(spec: PropSpec) -> PropSpec:
    """Stamp the AE materialization canon onto a Layer Styles leaf spec."""
    suffix = spec.match_name.rsplit("/", 1)[-1]
    if spec.color:
        return spec._replace(pad2a=1)
    if suffix in _STYLE_ENUM_SUFFIXES:
        return spec._replace(integer=True, value_hint_type=1)
    if suffix in _STYLE_ANGLE_SUFFIXES:
        return spec._replace(integer=True, property_category=0x06)
    bounds = _STYLE_HINT_BOUNDS_EXCEPTIONS.get(
        spec.match_name, _STYLE_HINT_BOUNDS.get(suffix)
    )
    if bounds is not None:
        return spec._replace(value_hint_type=0xFFFF, hint_bounds=bounds)
    return spec


def _style_canon_list(specs: list[PropSpec]) -> list[PropSpec]:
    return [_style_leaf_canon(spec) for spec in specs]


# Layer Styles sub-group specs (keyed by sub-group match name).
_LAYER_STYLE_CHILD_SPECS: dict[str, list[PropSpec]] = {
    "dropShadow/enabled": _style_canon_list(_DROP_SHADOW_SPECS),
    "innerShadow/enabled": _style_canon_list(_INNER_SHADOW_SPECS),
    "outerGlow/enabled": _style_canon_list(_OUTER_GLOW_SPECS),
    "innerGlow/enabled": _style_canon_list(_INNER_GLOW_SPECS),
    "bevelEmboss/enabled": _style_canon_list(_BEVEL_EMBOSS_SPECS),
    "chromeFX/enabled": _style_canon_list(_SATIN_SPECS),
    "solidFill/enabled": _style_canon_list(_COLOR_OVERLAY_SPECS),
    "gradientFill/enabled": _style_canon_list(_GRADIENT_OVERLAY_SPECS),
    "patternFill/enabled": _style_canon_list(_PATTERN_OVERLAY_SPECS),
    "frameFX/enabled": _style_canon_list(_STROKE_SPECS),
}

# Canonical children of "ADBE Layer Styles" (Blending Options + 10 styles).
# AE leaves every layer style disabled (enable_flags 2) until one is added;
# only Blending Options is enabled+collapsed (3). Synthesizing a style toggle
# as enabled (1) makes AE apply that style on open - e.g. a default-red Color
# Overlay - so the whole layer renders red.
_LAYER_STYLES_SPECS: list[GroupSpec] = [
    GroupSpec("ADBE Blend Options Group", "Blending Options", enable_flags=3),
    GroupSpec("dropShadow/enabled", "Drop Shadow", enable_flags=2),
    GroupSpec("innerShadow/enabled", "Inner Shadow", enable_flags=2),
    GroupSpec("outerGlow/enabled", "Outer Glow", enable_flags=2),
    GroupSpec("innerGlow/enabled", "Inner Glow", enable_flags=2),
    GroupSpec("bevelEmboss/enabled", "Bevel and Emboss", enable_flags=2),
    GroupSpec("chromeFX/enabled", "Satin", enable_flags=2),
    GroupSpec("solidFill/enabled", "Color Overlay", enable_flags=2),
    GroupSpec("gradientFill/enabled", "Gradient Overlay", enable_flags=2),
    GroupSpec("patternFill/enabled", "Pattern Overlay", enable_flags=2),
    GroupSpec("frameFX/enabled", "Stroke", enable_flags=2),
]


# ---------------------------------------------------------------------------
# Transform property specifications
# ---------------------------------------------------------------------------

# Canonical order of transform properties as reported by ExtendScript.
# Spatial values (Anchor Point, Position, Position_0, Position_1) are
# computed from layer/comp dimensions; all others use a fixed default.
_TRANSFORM_SPECS: list[PropSpec] = [
    _spec(
        "ADBE Anchor Point",
        "Anchor Point",
        None,
        PropertyValueType.ThreeD_SPATIAL,
    ),
    _spec(
        "ADBE Position",
        "Position",
        None,
        PropertyValueType.ThreeD_SPATIAL,
    ),
    _spec(
        "ADBE Position_0",
        "X Position",
        None,
        PropertyValueType.OneD,
        has_time_base=True,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Position_1",
        "Y Position",
        None,
        PropertyValueType.OneD,
        has_time_base=True,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Position_2",
        "Z Position",
        None,
        PropertyValueType.OneD,
        bound_chunks=True,
    ),
    _spec(
        "ADBE Scale",
        "Scale",
        None,
        PropertyValueType.ThreeD,
    ),
    _spec(
        "ADBE Orientation",
        "Orientation",
        None,
        PropertyValueType.ThreeD_SPATIAL,
        has_time_base=True,
        spatial_flags=0x07,
        cvot=0x07,
        value_hint_type=6,
    ),
    _spec(
        "ADBE Rotate X", "X Rotation", None, PropertyValueType.OneD, has_time_base=True
    ),
    _spec(
        "ADBE Rotate Y", "Y Rotation", None, PropertyValueType.OneD, has_time_base=True
    ),
    _spec("ADBE Rotate Z", "Rotation", None, PropertyValueType.OneD),
    _spec("ADBE Opacity", "Opacity", None, PropertyValueType.OneD),
    _spec(
        "ADBE Envir Appear in Reflect",
        "Appears in Reflections",
        None,
        PropertyValueType.OneD,
        integer=True,
        can_vary_over_time=False,
        has_time_base=True,
    ),
]

# Map of match_name > fixed default for standard transform properties.
# Position and Anchor Point defaults depend on layer/comp dimensions and
# are handled separately.
_TRANSFORM_FIXED_DEFAULTS: dict[str, float | list[float]] = {
    "ADBE Scale": [100.0, 100.0, 100.0],
    "ADBE Rotate X": 0.0,
    "ADBE Rotate Y": 0.0,
    "ADBE Rotate Z": 0.0,
    "ADBE Opacity": 100.0,
    "ADBE Orientation": [0.0, 0.0, 0.0],
    "ADBE Position_2": 0.0,
    "ADBE Envir Appear in Reflect": 1.0,
}


# Mapping from group match_name to ordered list of child property specs.
_GROUP_CHILD_SPECS: dict[str, Sequence[PropSpec | GroupSpec]] = {
    "ADBE Effect Built In Params": _COMPOSITING_OPTIONS_SPECS,
    "ADBE Mask Atom": _MASK_ATOM_SPECS,
    "ADBE Blend Options Group": _BLEND_OPTIONS_SPECS,
    "ADBE Adv Blend Group": _ADV_BLEND_SPECS,
    "ADBE Material Options Group": _MATERIAL_SPECS,
    "ADBE Extrsn Options Group": _EXTRUSION_SPECS,
    "ADBE Plane Options Group": _PLANE_SPECS,
    "ADBE Audio Group": _AUDIO_SPECS,
    "ADBE Source Options Group": _SOURCE_OPTIONS_SPECS,
    "ADBE Light Options Group": _LIGHT_SPECS,
    "ADBE Camera Options Group": _CAMERA_SPECS,
    "ADBE Layer Styles": _LAYER_STYLES_SPECS,
    "ADBE Text Properties": [
        _spec(
            "ADBE Text Document",
            "Source Text",
            None,
            PropertyValueType.TEXT_DOCUMENT,
        ),
        GroupSpec("ADBE Text Path Options", "Path Options"),
        GroupSpec("ADBE Text More Options", "More Options"),
        GroupSpec("ADBE Text Animators", "Animators"),
    ],
    "ADBE Text Path Options": _TEXT_PATH_OPTIONS_SPECS,
    "ADBE Text More Options": _TEXT_MORE_OPTIONS_SPECS,
    "ADBE Vector Shape - Star": _VECTOR_STAR_SPECS,
    "ADBE Vector Graphic - Fill": _VECTOR_FILL_SPECS,
    "ADBE Vector Graphic - G-Fill": _VECTOR_G_FILL_SPECS,
    "ADBE Vector Graphic - G-Stroke": _VECTOR_G_STROKE_SPECS,
    "ADBE Vector Graphic - Stroke": _VECTOR_STROKE_SPECS,
    "ADBE Vector Stroke Dashes": _VECTOR_STROKE_DASHES_SPECS,
    "ADBE Vector Stroke Taper": _VECTOR_STROKE_TAPER_SPECS,
    "ADBE Vector Stroke Wave": _VECTOR_STROKE_WAVE_SPECS,
    "ADBE Vector Group": _VECTOR_GROUP_SPECS,
    "ADBE Vector Transform Group": _VECTOR_TRANSFORM_SPECS,
    "ADBE Vector Materials Group": _VECTOR_MATERIALS_SPECS,
    "ADBE Vector Shape - Ellipse": _VECTOR_ELLIPSE_SPECS,
    "ADBE Vector Shape - Rect": _VECTOR_RECT_SPECS,
    "ADBE Vector Filter - Repeater": _VECTOR_REPEATER_SPECS,
    "ADBE Vector Repeater Transform": _VECTOR_REPEATER_TRANSFORM_SPECS,
    "ADBE Vector Shape - Group": _VECTOR_PATH_SPECS,
    "ADBE Vector Filter - Merge": _VECTOR_MERGE_SPECS,
    "ADBE Vector Filter - Offset": _VECTOR_OFFSET_SPECS,
    "ADBE Vector Filter - PB": _VECTOR_PUCKER_BLOAT_SPECS,
    "ADBE Vector Filter - RC": _VECTOR_ROUND_CORNERS_SPECS,
    "ADBE Vector Filter - Trim": _VECTOR_TRIM_SPECS,
    "ADBE Vector Filter - Twist": _VECTOR_TWIST_SPECS,
    "ADBE Vector Filter - Roughen": _VECTOR_ROUGHEN_SPECS,
    "ADBE Vector Filter - Wiggler": _VECTOR_WIGGLER_SPECS,
    "ADBE Vector Wiggler Transform": _VECTOR_WIGGLER_TRANSFORM_SPECS,
    "ADBE Vector Filter - Zigzag": _VECTOR_ZIGZAG_SPECS,
    "ADBE Text Selector": _TEXT_RANGE_SELECTOR_SPECS,
    "ADBE Text Range Advanced": _TEXT_RANGE_ADVANCED_SPECS,
    "ADBE Text Wiggly Selector": _TEXT_WIGGLY_SELECTOR_SPECS,
    "ADBE Text Expressible Selector": _TEXT_EXPRESSIBLE_SELECTOR_SPECS,
    "ADBE Text Animator Properties": _TEXT_ANIMATOR_POOL_SPECS,
    # A text animator exposes an (initially empty) Selectors group and
    # the Properties pool; AE writes only the latter to binary.
    "ADBE Text Animator": [
        GroupSpec("ADBE Text Selectors", "Selectors"),
        GroupSpec("ADBE Text Animator Properties", "Properties"),
    ],
    "ADBE Compositing Options Group": _3D_COMPOSITING_OPTIONS_SPECS,
    "ADBE3D Para Mat Parade": [GroupSpec("ADBE3D Param Mat Atom", "Material")],
    "ADBE3D Param Mat Atom": _PARA_MAT_SPEC,
    "ADBE CubeMeshOptionsSGrp": _CUBE_MESH_OPTIONS_SPEC,
    "ADBE CubeBevelOptionsSGrp": _CUBE_BEVEL_OPTIONS_SPEC,
    "ADBE SphereMeshOptionsSGrp": _SPHERE_MESH_OPTIONS_SPEC,
    "ADBE PlaneMeshOptionsSGrp": _PLANE_MESH_OPTIONS_SPEC,
    "ADBE TorusMeshOptionsSGrp": _TORUS_MESH_OPTIONS_SPEC,
    "ADBE ConeMeshOptionsSGrp": _CONE_MESH_OPTIONS_SPEC,
    "ADBE ConeBevelBevelSGrp": _CONE_BEVEL_OPTIONS_SPEC,
    "ADBE CylinderMeshOptionsSGrp": _CYLINDER_MESH_OPTIONS_SPEC,
    "ADBE CylinderBevelOptionsSGrp": _CYLINDER_BEVEL_OPTIONS_SPEC,
    "ADBE Displacement Options": _DISPLACEMENT_OPTIONS_SPEC,
}

_MARKER_SPEC: PropSpec = _spec(
    "ADBE Marker", "Marker", None, PropertyValueType.MARKER, dimensions=0
)

_TOP_LEVEL_SPECS: list[PropSpec | GroupSpec] = [
    _MARKER_SPEC,
    GroupSpec("ADBE Text Properties", "Text"),
    GroupSpec("ADBE Root Vectors Group", "Contents"),
    _spec(
        "ADBE Time Remapping",
        "Time Remap",
        None,
        PropertyValueType.OneD,
        min_value=0,
        has_time_base=True,
    ),
    GroupSpec("ADBE MTrackers", "Motion Trackers"),
    GroupSpec("ADBE Mask Parade", "Masks"),
    GroupSpec("ADBE Effect Parade", "Effects"),
    GroupSpec("ADBE Transform Group", "Transform"),
    GroupSpec("ADBE Camera Options Group", "Camera Options"),
    GroupSpec("ADBE Light Options Group", "Light Options"),
    GroupSpec("ADBE Layer Styles", "Layer Styles", enable_flags=3),
    GroupSpec("ADBE Plane Options Group", "Geometry Options"),
    GroupSpec("ADBE Extrsn Options Group", "Geometry Options"),
    GroupSpec("ADBE Material Options Group", "Material Options"),
    GroupSpec("ADBE Compositing Options Group", "Compositing Options"),
    GroupSpec("ADBE Audio Group", "Audio"),
    GroupSpec("ADBE Data Group", "Data"),
    GroupSpec("ADBE Layer Overrides", "Essential Properties"),
    GroupSpec("ADBE Layer Sets", "Sets"),
    GroupSpec("ADBE3D Para Mat Parade", "Material Assignment"),
    GroupSpec("ADBE Source Options Group", "Replace Source"),
]

# Canonical top-level groups of a parametric mesh layer, in the order
# ExtendScript reports AND AE writes to binary (identical; verified against
# parametric_meshes.aep and its ExtendScript export). Note the order differs
# from other AV layers: Geometry Options (Plane) and Essential Properties
# come after Material Assignment. Group `enable_flags` mirror the tdsb
# bytes AE writes for a new mesh layer; the ACTIVE mesh type's option and
# bevel groups get `1` at creation time instead (see
# `CompItem.add_parametric_mesh`).
_PARAMETRIC_MESH_TOP_LEVEL_SPECS: list[PropSpec | GroupSpec] = [
    _MARKER_SPEC,
    GroupSpec("ADBE MTrackers", "Motion Trackers"),
    GroupSpec("ADBE Mask Parade", "Masks"),
    GroupSpec("ADBE Effect Parade", "Effects"),
    GroupSpec("ADBE Transform Group", "Transform"),
    GroupSpec("ADBE Layer Styles", "Layer Styles", enable_flags=3),
    GroupSpec("ADBE Extrsn Options Group", "Geometry Options", enable_flags=3),
    GroupSpec("ADBE Material Options Group", "Material Options", enable_flags=3),
    GroupSpec("ADBE Compositing Options Group", "Compositing Options"),
    GroupSpec("ADBE Audio Group", "Audio", enable_flags=3),
    GroupSpec("ADBE Layer Sets", "Sets", enable_flags=3),
    GroupSpec("ADBE3D Para Mat Parade", "Material Assignment"),
    GroupSpec("ADBE Displacement Options", "Displacement Options", enable_flags=3),
    GroupSpec("ADBE Plane Options Group", "Geometry Options", enable_flags=3),
    GroupSpec("ADBE Layer Overrides", "Essential Properties", enable_flags=3),
    GroupSpec("ADBE Source Options Group", "Replace Source", enable_flags=3),
    GroupSpec("ADBE CubeMeshOptionsSGrp", "Mesh Options", enable_flags=3),
    GroupSpec("ADBE CubeBevelOptionsSGrp", "Bevel Options", enable_flags=3),
    GroupSpec("ADBE SphereMeshOptionsSGrp", "Mesh Options", enable_flags=3),
    GroupSpec("ADBE PlaneMeshOptionsSGrp", "Mesh Options", enable_flags=3),
    GroupSpec("ADBE TorusMeshOptionsSGrp", "Mesh Options", enable_flags=3),
    GroupSpec("ADBE ConeMeshOptionsSGrp", "Mesh Options", enable_flags=3),
    GroupSpec("ADBE ConeBevelBevelSGrp", "Bevel Options", enable_flags=3),
    GroupSpec("ADBE CylinderMeshOptionsSGrp", "Mesh Options", enable_flags=3),
    GroupSpec("ADBE CylinderBevelOptionsSGrp", "Bevel Options", enable_flags=3),
]

# Groups only present on camera / light layers.
_CAMERA_LIGHT_GROUPS: frozenset[str] = frozenset(
    {
        "ADBE Camera Options Group",
        "ADBE Light Options Group",
    }
)

# Groups only present on regular AVLayers, NOT on TextLayer or ShapeLayer.
_REGULAR_AV_ONLY_GROUPS: frozenset[str] = frozenset(
    {
        "ADBE Time Remapping",
        "ADBE MTrackers",
        "ADBE Data Group",
        "ADBE Layer Overrides",
    }
)
_REGULAR_AV_AND_PARAMETRIC_MESH_ONLY_GROUPS: frozenset[str] = frozenset(
    {
        "ADBE Source Options Group",
        "ADBE Plane Options Group",
    }
)

# Layer-type-specific groups that should be skipped for other types.
_TEXT_ONLY_GROUPS: frozenset[str] = frozenset({"ADBE Text Properties"})
_SHAPE_ONLY_GROUPS: frozenset[str] = frozenset({"ADBE Root Vectors Group"})
# Groups only present on Advanced-3D-native layers (parametric mesh /
# 3D model); still listed in _TOP_LEVEL_SPECS so a parsed occurrence keeps
# its canonical position, but never synthesized for other layer types.
_ADVANCED_3D_ONLY_GROUPS: frozenset[str] = frozenset(
    {
        "ADBE Compositing Options Group",
        "ADBE3D Para Mat Parade",
    }
)

# Per-layer-class skip sets for top-level group synthesis (the negative
# space of which canonical groups each layer type exposes). Built once at
# import: _synthesize_missing_top_level_groups runs for every parsed layer.
# Parametric mesh layers have no skip set: they use their own full spec
# list (_PARAMETRIC_MESH_TOP_LEVEL_SPECS).
_SKIP_FOR_TEXT: frozenset[str] = (
    _REGULAR_AV_AND_PARAMETRIC_MESH_ONLY_GROUPS
    | _REGULAR_AV_ONLY_GROUPS
    | _SHAPE_ONLY_GROUPS
    | _CAMERA_LIGHT_GROUPS
    | _ADVANCED_3D_ONLY_GROUPS
)
_SKIP_FOR_SHAPE: frozenset[str] = (
    _REGULAR_AV_AND_PARAMETRIC_MESH_ONLY_GROUPS
    | _REGULAR_AV_ONLY_GROUPS
    | _TEXT_ONLY_GROUPS
    | _CAMERA_LIGHT_GROUPS
    | _ADVANCED_3D_ONLY_GROUPS
)
_SKIP_FOR_REGULAR_AV: frozenset[str] = (
    _TEXT_ONLY_GROUPS
    | _SHAPE_ONLY_GROUPS
    | _CAMERA_LIGHT_GROUPS
    | _ADVANCED_3D_ONLY_GROUPS
)


def _camera_light_skip(own_options: str) -> frozenset[str]:
    """Cameras/lights expose only Marker, Transform and their own options."""
    return frozenset(
        s.match_name
        for s in _TOP_LEVEL_SPECS
        if s.match_name not in ("ADBE Marker", "ADBE Transform Group", own_options)
    )


_SKIP_FOR_CAMERA: frozenset[str] = _camera_light_skip("ADBE Camera Options Group")
_SKIP_FOR_LIGHT: frozenset[str] = _camera_light_skip("ADBE Light Options Group")

# Empty groups AE omits from a freshly created layer (it writes them only
# once they have content).
_OMITTED_EMPTY_GROUPS: frozenset[str] = frozenset(
    {
        "ADBE MTrackers",
        "ADBE Mask Parade",
        "ADBE Effect Parade",
        "ADBE Root Vectors Group",
        "ADBE Text Animators",
    }
)

# Transform properties AE does NOT write for a new camera / light layer
# (two-node cameras auto-orient, so the orientation trio stays unset);
# everything else in the Transform group is written.
_CAMERA_LIGHT_TRANSFORM_SKIP: frozenset[str] = frozenset(
    {
        "ADBE Orientation",
        "ADBE Rotate X",
        "ADBE Rotate Y",
    }
)

# The mesh-option / bevel groups owned by each mesh type (raw ldta value).
# AE writes the ACTIVE type's option/bevel groups expanded (tdsb bit 1
# clear -> 1) while every other top-level mesh group is collapsed (tdsb=3).
# Used at creation to match AE's tdsb; see `_PARAMETRIC_MESH_TOP_LEVEL_SPECS`.
_PARAMETRIC_MESH_ACTIVE_GROUPS: dict[int, tuple[str, ...]] = {
    0: ("ADBE CubeMeshOptionsSGrp", "ADBE CubeBevelOptionsSGrp"),
    1: ("ADBE SphereMeshOptionsSGrp",),
    2: ("ADBE PlaneMeshOptionsSGrp",),
    3: ("ADBE TorusMeshOptionsSGrp",),
    4: ("ADBE ConeMeshOptionsSGrp", "ADBE ConeBevelBevelSGrp"),
    5: ("ADBE CylinderMeshOptionsSGrp", "ADBE CylinderBevelOptionsSGrp"),
}
