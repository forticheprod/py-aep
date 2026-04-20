"""Property specification tables for synthesis and defaults.

These tables define the canonical child properties for standard After Effects
property groups (Material Options, Layer Styles, etc.) and their default values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

from ...enums import PropertyValueType

if TYPE_CHECKING:
    from collections.abc import Sequence

_USE_VALUE = object()
"""Sentinel indicating `_PropSpec.default_value` should mirror `value`."""


class _PropSpec(NamedTuple):
    """Metadata for a synthesized property."""

    match_name: str
    auto_name: str
    value: Any
    pvt: PropertyValueType
    dimensions: int = 1
    is_spatial: bool = False
    color: bool = False
    min_value: float | None = None
    max_value: float | None = None
    default_value: Any = _USE_VALUE
    can_vary_over_time: bool | None = None


class _GroupSpec(NamedTuple):
    """Metadata for a synthesized property group."""

    match_name: str
    auto_name: str


# Color min/max bounds used by Layer Styles and Material Shadow Color.
_COLOR_MIN: float = -3921568.62745098
_COLOR_MAX: float = 3921568.62745098

# Canonical children of "ADBE Material Options Group" as reported by
# ExtendScript.  Properties already parsed from binary are skipped.
_MATERIAL_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Casts Shadows",
        "Casts Shadows",
        0.0,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Light Transmission",
        "Light Transmission",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Accepts Shadows",
        "Accepts Shadows",
        1.0,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Accepts Lights",
        "Accepts Lights",
        1.0,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Shadow Color",
        "Shadow Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "ADBE Appears in Reflections",
        "Appears in Reflections",
        1.0,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Ambient Coefficient",
        "Ambient",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Diffuse Coefficient",
        "Diffuse",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Specular Coefficient",
        "Specular Intensity",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Shininess Coefficient",
        "Specular Shininess",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Metal Coefficient",
        "Metal",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Reflection Coefficient",
        "Reflection Intensity",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Glossiness Coefficient",
        "Reflection Sharpness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Fresnel Coefficient",
        "Reflection Rolloff",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Transparency Coefficient",
        "Transparency",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Transp Rolloff",
        "Transparency Rolloff",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Index of Refraction",
        "Index of Refraction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=5,
    ),
]

# Canonical children of "ADBE Extrsn Options Group".
_EXTRUSION_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Bevel Styles",
        "Bevel Style",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=4,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Bevel Direction",
        "Bevel Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Bevel Depth",
        "Bevel Depth",
        2.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Hole Bevel Depth",
        "Hole Bevel Depth",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Extrsn Depth",
        "Extrusion Depth",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=10000,
    ),
]

# Canonical children of "ADBE Plane Options Group".
_PLANE_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Plane Curvature",
        "Curvature",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Plane Subdivision",
        "Segments",
        4.0,
        PropertyValueType.OneD,
        min_value=2,
        max_value=256,
    ),
]

# Canonical children of "ADBE Audio Group".
_AUDIO_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Audio Levels",
        "Audio Levels",
        [0.0, 0.0],
        PropertyValueType.TwoD,
        dimensions=2,
        min_value=-192,
        max_value=24,
    ),
]

# Canonical children of "ADBE Source Options Group".
_SOURCE_OPTIONS_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Layer Source Alternate",
        "Item Cache Entry",
        None,
        PropertyValueType.NO_VALUE,
        default_value=0,
        can_vary_over_time=True,
    ),
]

# Canonical children of "ADBE Effect Built In Params" (Compositing Options).
_COMPOSITING_OPTIONS_SPECS: list[_PropSpec | _GroupSpec] = [
    _GroupSpec("ADBE Effect Mask Parade", "Masks"),
    _PropSpec(
        "ADBE Effect Mask Opacity",
        "Effect Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Force CPU GPU",
        "GPU Rendering",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
]

# Canonical children of a mask atom ("ADBE Mask Atom").
# Mask Path is parsed separately (complex shape data) and only present in
# binary for some samples; placing it in specs ensures correct ordering.
_MASK_ATOM_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Mask Shape",
        "Mask Path",
        None,
        PropertyValueType.CUSTOM_VALUE,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Mask Feather",
        "Mask Feather",
        [0.0, 0.0],
        PropertyValueType.TwoD,
        dimensions=2,
        min_value=0,
        max_value=32000,
    ),
    _PropSpec(
        "ADBE Mask Opacity",
        "Mask Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec("ADBE Mask Offset", "Mask Expansion", 0.0, PropertyValueType.OneD),
]

# Canonical children of "ADBE Light Options Group" as reported by ExtendScript.
_LIGHT_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Light Env Atom",
        "Source",
        None,
        PropertyValueType.NO_VALUE,
    ),
    _PropSpec(
        "ADBE Light Backgd Visible",
        "Background Visible",
        0.0,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Light Backgd Opacity",
        "Background Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Light Backgd Blur",
        "Background Blur",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Light Intensity",
        "Intensity",
        100.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Light Color",
        "Color",
        [1.0, 1.0, 1.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "ADBE Light Cone Angle",
        "Cone Angle",
        90.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=180,
    ),
    _PropSpec(
        "ADBE Light Cone Feather 2",
        "Cone Feather",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Light Falloff Type",
        "Falloff",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
    ),
    _PropSpec(
        "ADBE Light Falloff Start",
        "Radius",
        500.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Light Falloff Distance",
        "Falloff Distance",
        500.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Casts Shadows",
        "Casts Shadows",
        0.0,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Light Shadow Darkness",
        "Shadow Darkness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Light Shadow Diffusion",
        "Shadow Diffusion",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
]

# Canonical children of "ADBE Camera Options Group" as reported by ExtendScript.
_CAMERA_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Camera Zoom",
        "Zoom",
        0.0,
        PropertyValueType.OneD,
        min_value=1,
    ),
    _PropSpec(
        "ADBE Camera Depth of Field",
        "Depth of Field",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Camera Focus Distance",
        "Focus Distance",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Camera Aperture",
        "Aperture",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Camera Blur Level",
        "Blur Level",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Iris Shape",
        "Iris Shape",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=10,
    ),
    _PropSpec(
        "ADBE Iris Rotation",
        "Iris Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Iris Roundness",
        "Iris Roundness",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Iris Aspect Ratio",
        "Iris Aspect Ratio",
        1.0,
        PropertyValueType.OneD,
        min_value=0.00999999977648,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Iris Diffraction Fringe",
        "Iris Diffraction Fringe",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=500,
    ),
    _PropSpec(
        "ADBE Iris Highlight Gain",
        "Highlight Gain",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Iris Highlight Threshold",
        "Highlight Threshold",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "ADBE Iris Hightlight Saturation",
        "Highlight Saturation",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

# Canonical children of "ADBE Text Path Options".
_TEXT_PATH_OPTIONS_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Text Path",
        "Path",
        0.0,
        PropertyValueType.CUSTOM_VALUE,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Text Reverse Path",
        "Reverse Path",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Text Perpendicular To Path",
        "Perpendicular To Path",
        1.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Text Force Align Path",
        "Force Alignment",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Text First Margin",
        "First Margin",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Text Last Margin",
        "Last Margin",
        0.0,
        PropertyValueType.OneD,
    ),
]

# Canonical children of "ADBE Text More Options".
_TEXT_MORE_OPTIONS_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Text Anchor Point Option",
        "Anchor Point Grouping",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=4,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Text Anchor Point Align",
        "Grouping Alignment",
        [0.0, 0.0],
        PropertyValueType.TwoD,
        dimensions=2,
    ),
    _PropSpec(
        "ADBE Text Render Order",
        "Fill & Stroke",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Text Character Blend Mode",
        "Inter-Character Blending",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=29,
        can_vary_over_time=False,
    ),
]

# Canonical children of "ADBE Vector Shape - Star" (Polystar path).
_VECTOR_STAR_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Shape Direction",
        "Shape Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Star Type",
        "Type",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Star Points",
        "Points",
        5.0,
        PropertyValueType.OneD,
        min_value=3,
    ),
    _PropSpec(
        "ADBE Vector Star Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Vector Star Rotation",
        "Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Vector Star Inner Radius",
        "Inner Radius",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Star Outer Radius",
        "Outer Radius",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Star Inner Roundess",
        "Inner Roundness",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Vector Star Outer Roundess",
        "Outer Roundness",
        0.0,
        PropertyValueType.OneD,
    ),
]

# Canonical children of "ADBE Vector Graphic - Fill".
_VECTOR_FILL_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Blend Mode",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=29,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Composite Order",
        "Composite",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Fill Rule",
        "Fill Rule",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Fill Color",
        "Color",
        [1.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "ADBE Vector Fill Opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

# Canonical children of "ADBE Vector Graphic - Stroke".
_VECTOR_STROKE_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Blend Mode",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=29,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Composite Order",
        "Composite",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Stroke Color",
        "Color",
        [1.0, 1.0, 1.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "ADBE Vector Stroke Opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Stroke Width",
        "Stroke Width",
        2.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Stroke Line Cap",
        "Line Cap",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Stroke Line Join",
        "Line Join",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Stroke Miter Limit",
        "Miter Limit",
        4.0,
        PropertyValueType.OneD,
        min_value=1,
    ),
]

# Canonical children of "ADBE Vector Stroke Dashes".
_VECTOR_STROKE_DASHES_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Stroke Dash 1",
        "Dash",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Stroke Gap 1",
        "Gap",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Stroke Dash 2",
        "Dash 2",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Stroke Gap 2",
        "Gap 2",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Stroke Dash 3",
        "Dash 3",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Stroke Gap 3",
        "Gap 3",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Stroke Offset",
        "Offset",
        0.0,
        PropertyValueType.OneD,
    ),
]

# Canonical children of "ADBE Vector Stroke Taper".
_VECTOR_STROKE_TAPER_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Taper Length Units",
        "Length Units",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Taper Start Length",
        "Start Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Taper End Length",
        "End Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Taper StartWidthPx",
        "Start Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Taper EndWidthPx",
        "End Length",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Taper Start Width",
        "Start Width",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Taper End Width",
        "End Width",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Taper Start Ease",
        "Start Ease",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Taper End Ease",
        "End Ease",
        0.0,
        PropertyValueType.OneD,
        min_value=-100,
        max_value=100,
    ),
]

# Canonical children of "ADBE Vector Stroke Wave".
_VECTOR_STROKE_WAVE_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Taper Wave Amount",
        "Amount",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Taper Wave Units",
        "Units",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Taper Wavelength",
        "Wavelength",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Taper Wave Cycles",
        "Cycles",
        10.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Taper Wave Phase",
        "Phase",
        0.0,
        PropertyValueType.OneD,
    ),
]

# Canonical children of "ADBE Vector Group" (shape group container).
_VECTOR_GROUP_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Blend Mode",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=29,
        can_vary_over_time=False,
    ),
]

# Canonical children of "ADBE Vector Transform Group".
_VECTOR_TRANSFORM_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Anchor",
        "Anchor Point",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Vector Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Vector Scale",
        "Scale",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        dimensions=2,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Skew",
        "Skew",
        0.0,
        PropertyValueType.OneD,
        min_value=-85,
        max_value=85,
    ),
    _PropSpec(
        "ADBE Vector Skew Axis",
        "Skew Axis",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Vector Rotation",
        "Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Vector Group Opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]


def _vec3d_face_specs(face: str) -> list[_PropSpec]:
    """Return 12 material property specs for one face (Front/Bevel/Side/Back)."""
    return [
        _PropSpec(
            f"ADBE Vec3D {face} RGB",
            f"{face} Color",
            [1.0, 0.0, 0.0, 1.0],
            PropertyValueType.COLOR,
            dimensions=4,
            is_spatial=True,
            color=True,
            min_value=_COLOR_MIN,
            max_value=_COLOR_MAX,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Ambient",
            f"{face} Ambient",
            100.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Diffuse",
            f"{face} Diffuse",
            50.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Specular",
            f"{face} Specular Intensity",
            50.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Shininess",
            f"{face} Specular Shininess",
            5.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Metal",
            f"{face} Metal",
            100.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Reflection",
            f"{face} Reflection Intensity",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Gloss",
            f"{face} Reflection Sharpness",
            100.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Fresnel",
            f"{face} Reflection Rolloff",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} Xparency",
            f"{face} Transparency",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} XparRoll",
            f"{face} Transparency Rolloff",
            0.0,
            PropertyValueType.OneD,
            min_value=0,
            max_value=100,
        ),
        _PropSpec(
            f"ADBE Vec3D {face} IOR",
            f"{face} Index of Refraction",
            1.0,
            PropertyValueType.OneD,
            min_value=1,
            max_value=5,
        ),
    ]


# Canonical children of "ADBE Vector Materials Group" (shape material options).
_VECTOR_MATERIALS_SPECS: list[_PropSpec] = [
    spec
    for face in ("Front", "Bevel", "Side", "Back")
    for spec in _vec3d_face_specs(face)
]

# Canonical children of "ADBE Vector Shape - Ellipse".
_VECTOR_ELLIPSE_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Shape Direction",
        "Shape Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Ellipse Size",
        "Size",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        dimensions=2,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Ellipse Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
]

# Canonical children of "ADBE Vector Shape - Rect".
_VECTOR_RECT_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Shape Direction",
        "Shape Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
        can_vary_over_time=False,
    ),
    _PropSpec(
        "ADBE Vector Rect Size",
        "Size",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        dimensions=2,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Rect Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Vector Rect Roundness",
        "Roundness",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
]

# Canonical children of "ADBE Vector Repeater Transform".
_VECTOR_REPEATER_TRANSFORM_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Vector Repeater Anchor",
        "Anchor Point",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Vector Repeater Position",
        "Position",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Vector Repeater Scale",
        "Scale",
        [100.0, 100.0],
        PropertyValueType.TwoD,
        dimensions=2,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Repeater Rotation",
        "Rotation",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Vector Repeater Opacity 1",
        "Start Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE Vector Repeater Opacity 2",
        "End Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

# Canonical children of "ADBE Vector Filter - Repeater".
_VECTOR_REPEATER_SPECS: list[_PropSpec | _GroupSpec] = [
    _PropSpec(
        "ADBE Vector Repeater Copies",
        "Copies",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
    ),
    _PropSpec(
        "ADBE Vector Repeater Offset",
        "Offset",
        0.0,
        PropertyValueType.OneD,
    ),
    _PropSpec(
        "ADBE Vector Repeater Order",
        "Composite",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
        can_vary_over_time=False,
    ),
    _GroupSpec("ADBE Vector Repeater Transform", "Transform"),
]

# Canonical children of "ADBE Blend Options Group".
_BLEND_OPTIONS_SPECS: list[_PropSpec | _GroupSpec] = [
    _PropSpec(
        "ADBE Global Angle2", "Global Light Angle", 120.0, PropertyValueType.OneD
    ),
    _PropSpec(
        "ADBE Global Altitude2", "Global Light Altitude", 30.0, PropertyValueType.OneD
    ),
    _GroupSpec("ADBE Adv Blend Group", "Advanced Blending"),
]

_ADV_BLEND_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Layer Fill Opacity2",
        "Fill Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "ADBE R Channel Blend",
        "Red",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "ADBE G Channel Blend",
        "Green",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "ADBE B Channel Blend",
        "Blue",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "ADBE Blend Interior",
        "Blend Interior Styles as Group",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "ADBE Blend Ranges",
        "Use Blend Ranges from Source",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
]

# Mapping from group match_name to ordered list of child property specs.
_GROUP_CHILD_SPECS: dict[str, Sequence[_PropSpec | _GroupSpec]] = {
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
    "ADBE Text Properties": [
        _PropSpec(
            "ADBE Text Document",
            "Source Text",
            None,
            PropertyValueType.TEXT_DOCUMENT,
        ),
        _GroupSpec("ADBE Text Path Options", "Path Options"),
        _GroupSpec("ADBE Text More Options", "More Options"),
        _GroupSpec("ADBE Text Animators", "Animators"),
    ],
    "ADBE Text Path Options": _TEXT_PATH_OPTIONS_SPECS,
    "ADBE Text More Options": _TEXT_MORE_OPTIONS_SPECS,
    "ADBE Vector Shape - Star": _VECTOR_STAR_SPECS,
    "ADBE Vector Graphic - Fill": _VECTOR_FILL_SPECS,
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
}

# Canonical children for Layer Styles sub-groups.

_DROP_SHADOW_SPECS: list[_PropSpec] = [
    _PropSpec(
        "dropShadow/mode2",
        "Blend Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "dropShadow/color",
        "Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "dropShadow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "dropShadow/useGlobalAngle",
        "Use Global Light",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec("dropShadow/localLightingAngle", "Angle", 120.0, PropertyValueType.OneD),
    _PropSpec(
        "dropShadow/distance",
        "Distance",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=30000,
    ),
    _PropSpec(
        "dropShadow/chokeMatte",
        "Spread",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "dropShadow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _PropSpec(
        "dropShadow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "dropShadow/layerConceals",
        "Layer Knocks Out Drop Shadow",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
]

_INNER_SHADOW_SPECS: list[_PropSpec] = [
    _PropSpec(
        "innerShadow/mode2",
        "Blend Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "innerShadow/color",
        "Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "innerShadow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "innerShadow/useGlobalAngle",
        "Use Global Light",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec("innerShadow/localLightingAngle", "Angle", 120.0, PropertyValueType.OneD),
    _PropSpec(
        "innerShadow/distance",
        "Distance",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=30000,
    ),
    _PropSpec(
        "innerShadow/chokeMatte",
        "Choke",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "innerShadow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _PropSpec(
        "innerShadow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_OUTER_GLOW_SPECS: list[_PropSpec] = [
    _PropSpec(
        "outerGlow/mode2",
        "Blend Mode",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "outerGlow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "outerGlow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "outerGlow/AEColorChoice",
        "Color Type",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _PropSpec(
        "outerGlow/color",
        "Color",
        [1.0, 1.0, 0.74509803921569, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "outerGlow/gradient",
        "Colors",
        None,
        PropertyValueType.NO_VALUE,
        is_spatial=True,
        can_vary_over_time=True,
    ),
    _PropSpec(
        "outerGlow/gradientSmoothness",
        "Gradient Smoothness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "outerGlow/glowTechnique",
        "Technique",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _PropSpec(
        "outerGlow/chokeMatte",
        "Spread",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "outerGlow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _PropSpec(
        "outerGlow/inputRange",
        "Range",
        50.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
    ),
    _PropSpec(
        "outerGlow/shadingNoise",
        "Jitter",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_INNER_GLOW_SPECS: list[_PropSpec] = [
    _PropSpec(
        "innerGlow/mode2",
        "Blend Mode",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "innerGlow/opacity",
        "Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "innerGlow/noise",
        "Noise",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "innerGlow/AEColorChoice",
        "Color Type",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _PropSpec(
        "innerGlow/color",
        "Color",
        [1.0, 1.0, 0.74509803921569, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "innerGlow/gradient",
        "Colors",
        None,
        PropertyValueType.NO_VALUE,
        is_spatial=True,
        can_vary_over_time=True,
    ),
    _PropSpec(
        "innerGlow/gradientSmoothness",
        "Gradient Smoothness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "innerGlow/glowTechnique",
        "Technique",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _PropSpec(
        "innerGlow/innerGlowSource",
        "Source",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _PropSpec(
        "innerGlow/chokeMatte",
        "Choke",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "innerGlow/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _PropSpec(
        "innerGlow/inputRange",
        "Range",
        50.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=100,
    ),
    _PropSpec(
        "innerGlow/shadingNoise",
        "Jitter",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_BEVEL_EMBOSS_SPECS: list[_PropSpec] = [
    _PropSpec(
        "bevelEmboss/bevelStyle",
        "Style",
        2.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=5,
    ),
    _PropSpec(
        "bevelEmboss/bevelTechnique",
        "Technique",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
    ),
    _PropSpec(
        "bevelEmboss/strengthRatio",
        "Depth",
        100.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=1000,
    ),
    _PropSpec(
        "bevelEmboss/bevelDirection",
        "Direction",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=2,
    ),
    _PropSpec(
        "bevelEmboss/blur",
        "Size",
        5.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _PropSpec(
        "bevelEmboss/softness",
        "Soften",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=16,
    ),
    _PropSpec(
        "bevelEmboss/useGlobalAngle",
        "Use Global Light",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec("bevelEmboss/localLightingAngle", "Angle", 120.0, PropertyValueType.OneD),
    _PropSpec(
        "bevelEmboss/localLightingAltitude", "Altitude", 30.0, PropertyValueType.OneD
    ),
    _PropSpec(
        "bevelEmboss/highlightMode",
        "Highlight Mode",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "bevelEmboss/highlightColor",
        "Highlight Color",
        [1.0, 1.0, 1.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "bevelEmboss/highlightOpacity",
        "Highlight Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "bevelEmboss/shadowMode",
        "Shadow Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "bevelEmboss/shadowColor",
        "Shadow Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "bevelEmboss/shadowOpacity",
        "Shadow Opacity",
        75.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_SATIN_SPECS: list[_PropSpec] = [
    _PropSpec(
        "chromeFX/mode2",
        "Blend Mode",
        5.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "chromeFX/color",
        "Color",
        [0.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "chromeFX/opacity",
        "Opacity",
        50.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec("chromeFX/localLightingAngle", "Angle", 19.0, PropertyValueType.OneD),
    _PropSpec(
        "chromeFX/distance",
        "Distance",
        11.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=250,
    ),
    _PropSpec(
        "chromeFX/blur",
        "Size",
        14.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=250,
    ),
    _PropSpec(
        "chromeFX/invert",
        "Invert",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
]

_COLOR_OVERLAY_SPECS: list[_PropSpec] = [
    _PropSpec(
        "solidFill/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "solidFill/color",
        "Color",
        [1.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "solidFill/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
]

_GRADIENT_OVERLAY_SPECS: list[_PropSpec] = [
    _PropSpec(
        "gradientFill/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "gradientFill/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "gradientFill/gradient",
        "Colors",
        None,
        PropertyValueType.NO_VALUE,
        is_spatial=True,
        can_vary_over_time=True,
    ),
    _PropSpec(
        "gradientFill/gradientSmoothness",
        "Gradient Smoothness",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec("gradientFill/angle", "Angle", 90.0, PropertyValueType.OneD),
    _PropSpec(
        "gradientFill/type",
        "Style",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=5,
    ),
    _PropSpec(
        "gradientFill/reverse",
        "Reverse",
        0.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "gradientFill/align",
        "Align with Layer",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "gradientFill/scale",
        "Scale",
        100.0,
        PropertyValueType.OneD,
        min_value=10,
        max_value=150,
    ),
    _PropSpec(
        "gradientFill/offset",
        "Offset",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
]

_PATTERN_OVERLAY_SPECS: list[_PropSpec] = [
    _PropSpec(
        "patternFill/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "patternFill/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "patternFill/align",
        "Link with Layer",
        1.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=1,
    ),
    _PropSpec(
        "patternFill/scale",
        "Scale",
        100.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=1000,
    ),
    _PropSpec(
        "patternFill/phase",
        "Offset",
        [0.0, 0.0],
        PropertyValueType.TwoD_SPATIAL,
        dimensions=2,
        is_spatial=True,
    ),
]

_STROKE_SPECS: list[_PropSpec] = [
    _PropSpec(
        "frameFX/mode2",
        "Blend Mode",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=33,
    ),
    _PropSpec(
        "frameFX/color",
        "Color",
        [1.0, 0.0, 0.0, 1.0],
        PropertyValueType.COLOR,
        dimensions=4,
        is_spatial=True,
        color=True,
        min_value=_COLOR_MIN,
        max_value=_COLOR_MAX,
    ),
    _PropSpec(
        "frameFX/size", "Size", 3.0, PropertyValueType.OneD, min_value=1, max_value=250
    ),
    _PropSpec(
        "frameFX/opacity",
        "Opacity",
        100.0,
        PropertyValueType.OneD,
        min_value=0,
        max_value=100,
    ),
    _PropSpec(
        "frameFX/style",
        "Position",
        1.0,
        PropertyValueType.OneD,
        min_value=1,
        max_value=3,
    ),
]

# Layer Styles sub-group specs (keyed by sub-group match name).
_LAYER_STYLE_CHILD_SPECS: dict[str, list[_PropSpec]] = {
    "dropShadow/enabled": _DROP_SHADOW_SPECS,
    "innerShadow/enabled": _INNER_SHADOW_SPECS,
    "outerGlow/enabled": _OUTER_GLOW_SPECS,
    "innerGlow/enabled": _INNER_GLOW_SPECS,
    "bevelEmboss/enabled": _BEVEL_EMBOSS_SPECS,
    "chromeFX/enabled": _SATIN_SPECS,
    "solidFill/enabled": _COLOR_OVERLAY_SPECS,
    "gradientFill/enabled": _GRADIENT_OVERLAY_SPECS,
    "patternFill/enabled": _PATTERN_OVERLAY_SPECS,
    "frameFX/enabled": _STROKE_SPECS,
}


# ---------------------------------------------------------------------------
# Transform property specifications
# ---------------------------------------------------------------------------

# Canonical order of transform properties as reported by ExtendScript.
# Spatial values (Anchor Point, Position, Position_0, Position_1) are
# computed from layer/comp dimensions; all others use a fixed default.
_TRANSFORM_SPECS: list[_PropSpec] = [
    _PropSpec(
        "ADBE Anchor Point",
        "Anchor Point",
        None,
        PropertyValueType.ThreeD_SPATIAL,
        dimensions=3,
        is_spatial=True,
    ),
    _PropSpec(
        "ADBE Position",
        "Position",
        None,
        PropertyValueType.ThreeD_SPATIAL,
        dimensions=3,
        is_spatial=True,
    ),
    _PropSpec("ADBE Position_0", "X Position", None, PropertyValueType.OneD),
    _PropSpec("ADBE Position_1", "Y Position", None, PropertyValueType.OneD),
    _PropSpec("ADBE Position_2", "Z Position", None, PropertyValueType.OneD),
    _PropSpec(
        "ADBE Scale",
        "Scale",
        None,
        PropertyValueType.ThreeD,
        dimensions=3,
    ),
    _PropSpec(
        "ADBE Orientation",
        "Orientation",
        None,
        PropertyValueType.ThreeD_SPATIAL,
        dimensions=3,
        is_spatial=True,
    ),
    _PropSpec("ADBE Rotate X", "X Rotation", None, PropertyValueType.OneD),
    _PropSpec("ADBE Rotate Y", "Y Rotation", None, PropertyValueType.OneD),
    _PropSpec("ADBE Rotate Z", "Rotation", None, PropertyValueType.OneD),
    _PropSpec("ADBE Opacity", "Opacity", None, PropertyValueType.OneD),
    _PropSpec(
        "ADBE Envir Appear in Reflect",
        "Appears in Reflections",
        None,
        PropertyValueType.OneD,
        can_vary_over_time=False,
    ),
]

# Map of match_name > fixed default for standard transform properties.
# Position and Anchor Point defaults depend on layer/comp dimensions and
# are handled separately.
_TRANSFORM_FIXED_DEFAULTS: dict[str, Any] = {
    "ADBE Scale": [100.0, 100.0, 100.0],
    "ADBE Rotate X": 0.0,
    "ADBE Rotate Y": 0.0,
    "ADBE Rotate Z": 0.0,
    "ADBE Opacity": 100.0,
    "ADBE Orientation": [0.0, 0.0, 0.0],
    "ADBE Position_2": 0.0,
    "ADBE Envir Appear in Reflect": 1.0,
}


_TOP_LEVEL_SPECS: list[_PropSpec | _GroupSpec] = [
    _PropSpec("ADBE Marker", "Marker", None, PropertyValueType.MARKER, dimensions=0),
    _GroupSpec("ADBE Text Properties", "Text"),
    _GroupSpec("ADBE Root Vectors Group", "Contents"),
    _PropSpec("ADBE Time Remapping", "Time Remap", None, PropertyValueType.OneD),
    _GroupSpec("ADBE MTrackers", "Motion Trackers"),
    _GroupSpec("ADBE Mask Parade", "Masks"),
    _GroupSpec("ADBE Effect Parade", "Effects"),
    _GroupSpec("ADBE Transform Group", "Transform"),
    _GroupSpec("ADBE Layer Styles", "Layer Styles"),
    _GroupSpec("ADBE Plane Options Group", "Geometry Options"),
    _GroupSpec("ADBE Extrsn Options Group", "Geometry Options"),
    _GroupSpec("ADBE Material Options Group", "Material Options"),
    _GroupSpec("ADBE Audio Group", "Audio"),
    _GroupSpec("ADBE Data Group", "Data"),
    _GroupSpec("ADBE Layer Overrides", "Essential Properties"),
    _GroupSpec("ADBE Layer Sets", "Sets"),
    _GroupSpec("ADBE Source Options Group", "Replace Source"),
]

# Groups only present on regular AVLayers, NOT on TextLayer or ShapeLayer.
_REGULAR_AV_ONLY_GROUPS: frozenset[str] = frozenset(
    {
        "ADBE Time Remapping",
        "ADBE MTrackers",
        "ADBE Plane Options Group",
        "ADBE Data Group",
        "ADBE Layer Overrides",
        "ADBE Source Options Group",
    }
)

# Layer-type-specific groups that should be skipped for other types.
_TEXT_ONLY_GROUPS: frozenset[str] = frozenset({"ADBE Text Properties"})
_SHAPE_ONLY_GROUPS: frozenset[str] = frozenset({"ADBE Root Vectors Group"})
