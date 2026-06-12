"""View-layer specs for a freshly created composition item.

Derived from the comp item After Effects 2026 writes for
`app.project.items.addComp()`; verify against re-captured ground truth
with `scripts/dev/gen_comp_skeleton.py`. Strings starting with `$` are
expressions evaluated at build time with the comp's parameters (see
`py_aep.binary.comp_skeleton`):

- `TB`: `cdta.internal_timebase` - `DUR_UNITS`: `round(duration * TB)`
- `W2` / `H2`: comp center - `ZV`: `width * pixel_aspect / 0.72`
- `PAR`: pixel aspect ratio - `FPS`: frame rate

The ten viewer pseudo-layers (`DLay` / `SLay` / `CLay`) share one
template and differ only in name, the secondary-view flag inside
`ldta.reserved_8c`, the per-view `ADBE Position` value, and the
presence of `ADBE Scale`. The `Markers` (`SecL`) layer is unique.

The spec structures are shared (aliased) between layers; treat them as
immutable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# ---------------------------------------------------------------------------
# Shared tdb4 layouts
# ---------------------------------------------------------------------------

# 1-D scalar property (sliders, rotations, opacity).
_TDB4_SCALAR: dict[str, Any] = {
    "value_hint_type": 1,
    "value_hint_flag": 255,
    "cvot_flags": 255,
    "time_base": "$TB",
    "type_flags": 8,
    "property_category": 9,
}

# Boolean / checkbox property.
_TDB4_BOOL: dict[str, Any] = {
    "value_hint_type": 65535,
    "cvot_flags": 4,
    "time_base": "$TB",
    "type_flags": 4,
    "property_category": 4,
}

# 3-D spatial point (Anchor Point / Position).
_TDB4_SPATIAL: dict[str, Any] = {
    "dimensions": 3,
    "spatial_static_flags": 15,
    "pad2a": 3,
    "value_hint_type": 65535,
    "value_hint_flag": 255,
    "cvot_flags": 255,
    "time_base": "$TB",
    "type_flags": 8,
    "property_category": 9,
    "pad7b": 3,
    "pad7c": 768,
    "spatial_marker": True,
    "expr_flags": 1,
}

# ---------------------------------------------------------------------------
# Shared property nodes
# ---------------------------------------------------------------------------


def _bool_prop(match_name: str, value: float) -> tuple[str, str, dict[str, Any]]:
    return (
        "prop",
        match_name,
        {
            "tdsb": {"enable_flags": 3},
            "tdsn": "-_0_/-",
            "tdb4": _TDB4_BOOL,
            "cdat": [value, 0.0, 0.0, 0.0, 0.0],
        },
    )


def _coefficient_prop(match_name: str, value: float) -> tuple[str, str, dict[str, Any]]:
    """Material-options slider with 0-100 bounds."""
    return (
        "prop",
        match_name,
        {
            "tdsb": {"enable_flags": 3},
            "tdsn": "-_0_/-",
            "tdb4": _TDB4_SCALAR,
            "cdat": [value, 0.0, 0.0, 0.0, 0.0],
            "tdum": [0.0],
            "tduM": [100.0],
        },
    )


_ANCHOR_POINT: tuple[str, str, dict[str, Any]] = (
    "prop",
    "ADBE Anchor Point",
    {
        "tdsb": {},
        "tdsn": "-_0_/-",
        "tdb4": _TDB4_SPATIAL,
        "cdat": ["$W2", "$H2", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    },
)


def _position_prop(x: Any, y: Any, z: Any) -> tuple[str, str, dict[str, Any]]:
    return (
        "prop",
        "ADBE Position",
        {
            "tdsb": {},
            "tdsn": "-_0_/-",
            "tdb4": _TDB4_SPATIAL,
            "cdat": [x, y, z, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
    )


# X / Y / Z separation followers (ADBE Position_0 / _1 / _2).
_SPLIT_POSITIONS: tuple[tuple[str, str, dict[str, Any]], ...] = tuple(
    (
        "prop",
        f"ADBE Position_{i}",
        {
            "tdsb": {"enable_flags": 3},
            "tdsn": "-_0_/-",
            "tdb4": _TDB4_SCALAR,
            "cdat": [0.0, 0.0, 0.0, 0.0, 0.0],
            "tdum": [0.0],
            "tduM": [0.0],
        },
    )
    for i in range(3)
)

_SCALE: tuple[str, str, dict[str, Any]] = (
    "prop",
    "ADBE Scale",
    {
        "tdsb": {"enable_flags": 3},
        "tdsn": "-_0_/-",
        "tdb4": {"dimensions": 3, **_TDB4_SCALAR},
        "cdat": [1.0, 1.0, 1.0] + [0.0] * 12,
        "tdum": [0.0],
        "tduM": [0.0],
    },
)

_ROTATE_Z: tuple[str, str, dict[str, Any]] = (
    "prop",
    "ADBE Rotate Z",
    {
        "tdsb": {},
        "tdsn": "-_0_/-",
        "tdb4": _TDB4_SCALAR,
        "cdat": [0.0, 0.0, 0.0, 0.0, 0.0],
    },
)

_OPACITY: tuple[str, str, dict[str, Any]] = (
    "prop",
    "ADBE Opacity",
    {
        "tdsb": {"enable_flags": 3},
        "tdsn": "-_0_/-",
        "tdb4": _TDB4_SCALAR,
        "cdat": [1.0, 0.0, 0.0, 0.0, 0.0],
        "tdum": [0.0],
        "tduM": [100.0],
    },
)

_ENVIR_APPEAR: tuple[str, str, dict[str, Any]] = _bool_prop(
    "ADBE Envir Appear in Reflect", 1.0
)

# ---------------------------------------------------------------------------
# Viewer layer template (Default + Front/Left/Top/Back/Right/Bottom +
# Custom View 1-3)
# ---------------------------------------------------------------------------


def _view_layer(
    list_type: str,
    name: str,
    position: tuple[Any, Any, Any] | None,
    *,
    has_scale: bool,
) -> dict[str, Any]:
    children: list[Any] = [_ANCHOR_POINT]
    if position is not None:
        children.append(_position_prop(*position))
    children.extend(_SPLIT_POSITIONS)
    if has_scale:
        children.append(_SCALE)
    children.extend([_ROTATE_Z, _OPACITY, _ENVIR_APPEAR])
    # reserved_8c byte 3 marks the six secondary (SLay) views.
    secondary = b"\x01" if list_type == "SLay" else b"\x00"
    return {
        "list_type": list_type,
        "name": name,
        "ldta": {
            "start_time_divisor": 600,
            "in_point_divisor": "$TB",
            "out_point_dividend": "$DUR_UNITS",
            "out_point_divisor": "$TB",
            "layer_flags_1": 68,
            "layer_flags_2": 1,
            "label": 4,
            "layer_name": name,
            "layer_type": 2,
            "reserved_8c": b"\x00\x00\x00" + secondary + b"\x01\x00\x00\x00"
            b"\x00\x00\x00\x01@Y\x83\x06\x0c\x180b",
            "matte_layer_id": 0,
        },
        "tdgp": {
            "children": [
                (
                    "group",
                    "ADBE Transform Group",
                    {"children": children, "tdsb": {}, "tdsn": "-_0_/-"},
                ),
                (
                    "group",
                    "ADBE Camera Options Group",
                    {"children": [], "tdsb": {}, "tdsn": "-_0_/-"},
                ),
            ],
            "tdsb": {},
            "tdsn": "",
        },
    }


# ---------------------------------------------------------------------------
# The unique `Markers` (SecL) layer
# ---------------------------------------------------------------------------

_LAYER_STYLE_NAMES = (
    "dropShadow",
    "innerShadow",
    "outerGlow",
    "innerGlow",
    "bevelEmboss",
    "chromeFX",
    "solidFill",
    "gradientFill",
    "patternFill",
    "frameFX",
)

_MARKERS_LAYER: dict[str, Any] = {
    "list_type": "SecL",
    "name": "Markers",
    "ldta": {
        "quality": 2,
        "start_time_divisor": 600,
        "in_point_divisor": "$TB",
        "out_point_dividend": "$DUR_UNITS",
        "out_point_divisor": "$TB",
        "layer_flags_2": 135,
        "reserved_3b": 1,
        "label": 8,
        "layer_name": "Markers",
        "blending_mode": 2,
        "layer_type": 4,
        "reserved_8c": b"\x00\x00\x00\x00\x01" + b"\x00" * 15,
        "matte_layer_id": 0,
    },
    "tdgp": {
        "children": [
            (
                "group",
                "ADBE Transform Group",
                {
                    "children": [
                        _SPLIT_POSITIONS[0],
                        _SPLIT_POSITIONS[1],
                        (
                            "orientation",
                            "ADBE Orientation",
                            {
                                "tdsb": {"enable_flags": 3},
                                "tdsn": "-_0_/-",
                                "tdb4": {
                                    "spatial_static_flags": 7,
                                    "value_hint_type": 6,
                                    "cvot_flags": 7,
                                    "time_base": "$TB",
                                    "no_value_flags": 1,
                                    "type_flags": 24,
                                    "spatial_marker": True,
                                },
                                "cdat": [0.0, 0.0, 0.0],
                                "otda": [0.0, 0.0, 0.0],
                            },
                        ),
                        (
                            "prop",
                            "ADBE Rotate X",
                            {
                                "tdsb": {"enable_flags": 3},
                                "tdsn": "-_0_/-",
                                "tdb4": _TDB4_SCALAR,
                                "cdat": [0.0, 0.0, 0.0, 0.0, 0.0],
                            },
                        ),
                        (
                            "prop",
                            "ADBE Rotate Y",
                            {
                                "tdsb": {"enable_flags": 3},
                                "tdsn": "-_0_/-",
                                "tdb4": _TDB4_SCALAR,
                                "cdat": [0.0, 0.0, 0.0, 0.0, 0.0],
                            },
                        ),
                        _ENVIR_APPEAR,
                    ],
                    "tdsb": {},
                    "tdsn": "-_0_/-",
                },
            ),
            (
                "group",
                "ADBE Layer Styles",
                {
                    "children": [
                        (
                            "group",
                            "ADBE Blend Options Group",
                            {
                                "children": [
                                    (
                                        "group",
                                        "ADBE Adv Blend Group",
                                        {"children": [], "tdsb": {}, "tdsn": "-_0_/-"},
                                    )
                                ],
                                "tdsb": {"enable_flags": 3},
                                "tdsn": "-_0_/-",
                            },
                        ),
                        *(
                            (
                                "group",
                                f"{style}/enabled",
                                {
                                    "children": [],
                                    "tdsb": {"enable_flags": 2},
                                    "tdsn": "-_0_/-",
                                },
                            )
                            for style in _LAYER_STYLE_NAMES
                        ),
                    ],
                    "tdsb": {"enable_flags": 3},
                    "tdsn": "-_0_/-",
                },
            ),
            (
                "group",
                "ADBE Extrsn Options Group",
                {
                    "children": [
                        (
                            "prop",
                            "ADBE Bevel Direction",
                            {
                                "tdsb": {"enable_flags": 3},
                                "tdsn": "-_0_/-",
                                "tdb4": {
                                    "value_hint_type": 2,
                                    "time_base": "$TB",
                                    "type_flags": 4,
                                    "property_category": 4,
                                },
                                "cdat": [1.0, 0.0, 0.0, 0.0, 0.0],
                            },
                        )
                    ],
                    "tdsb": {"enable_flags": 3},
                    "tdsn": "-_0_/-",
                },
            ),
            (
                "group",
                "ADBE Material Options Group",
                {
                    "children": [
                        _bool_prop("ADBE Casts Shadows", 0.0),
                        _coefficient_prop("ADBE Light Transmission", 0.0),
                        _bool_prop("ADBE Accepts Shadows", 1.0),
                        _bool_prop("ADBE Accepts Lights", 1.0),
                        (
                            "prop",
                            "ADBE Shadow Color",
                            {
                                "tdsb": {"enable_flags": 3},
                                "tdsn": "-_0_/-",
                                "tdb4": {
                                    "dimensions": 4,
                                    "spatial_static_flags": 7,
                                    "value_hint_type": 2,
                                    "value_hint_flag": 255,
                                    "cvot_flags": 255,
                                    "time_base": "$TB",
                                    "type_flags": 1,
                                    "property_category": 1,
                                    "spatial_marker": True,
                                },
                                "cdat": [255.0] + [0.0] * 11,
                            },
                        ),
                        _bool_prop("ADBE Appears in Reflections", 1.0),
                        _coefficient_prop("ADBE Ambient Coefficient", 100.0),
                        _coefficient_prop("ADBE Diffuse Coefficient", 50.0),
                        _coefficient_prop("ADBE Specular Coefficient", 50.0),
                        _coefficient_prop("ADBE Shininess Coefficient", 5.0),
                        _coefficient_prop("ADBE Metal Coefficient", 100.0),
                        _coefficient_prop("ADBE Reflection Coefficient", 0.0),
                        _coefficient_prop("ADBE Glossiness Coefficient", 100.0),
                        _coefficient_prop("ADBE Fresnel Coefficient", 0.0),
                        _coefficient_prop("ADBE Transparency Coefficient", 0.0),
                        _coefficient_prop("ADBE Transp Rolloff", 0.0),
                        (
                            "prop",
                            "ADBE Index of Refraction",
                            {
                                "tdsb": {"enable_flags": 3},
                                "tdsn": "-_0_/-",
                                "tdb4": {**_TDB4_SCALAR, "value_hint_type": 65535},
                                "cdat": [1.0, 0.0, 0.0, 0.0, 0.0],
                                "tdum": [1.0],
                                "tduM": [2.0],
                            },
                        ),
                    ],
                    "tdsb": {"enable_flags": 3},
                    "tdsn": "-_0_/-",
                },
            ),
            (
                "group",
                "ADBE Audio Group",
                {"children": [], "tdsb": {"enable_flags": 3}, "tdsn": "-_0_/-"},
            ),
            (
                "group",
                "ADBE Layer Sets",
                {"children": [], "tdsb": {"enable_flags": 3}, "tdsn": "-_0_/-"},
            ),
        ],
        "tdsb": {},
        "tdsn": "",
    },
}

# ---------------------------------------------------------------------------

COMP_VIEW_LAYER_SPECS: list[dict[str, Any]] = [
    _view_layer("DLay", "Default", None, has_scale=True),
    _view_layer("SLay", "Front", ("$W2", "$H2", -5000.0), has_scale=False),
    _view_layer("SLay", "Left", ("$W2 - 5000", "$H2", 0.0), has_scale=False),
    _view_layer("SLay", "Top", ("$W2", "$H2 - 5000", 0.0), has_scale=False),
    _view_layer("SLay", "Back", ("$W2", "$H2", 5000.0), has_scale=False),
    _view_layer("SLay", "Right", ("$W2 + 5000", "$H2", 0.0), has_scale=False),
    _view_layer("SLay", "Bottom", ("$W2", "$H2 + 5000", 0.0), has_scale=False),
    _view_layer(
        "CLay", "Custom View 1", ("$W2 - ZV", "$H2 - ZV", "$-ZV"), has_scale=True
    ),
    _view_layer("CLay", "Custom View 2", ("$W2", "$H2 - ZV", "$-ZV"), has_scale=True),
    _view_layer(
        "CLay", "Custom View 3", ("$W2 + ZV", "$H2 - ZV", "$-ZV"), has_scale=True
    ),
    _MARKERS_LAYER,
]
