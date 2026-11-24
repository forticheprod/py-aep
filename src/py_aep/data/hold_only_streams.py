"""Layer streams After Effects keys with hold interpolation only."""

from __future__ import annotations

_POPUP: dict[str, int] = {
    "_value_hint_type": 0xFFFF,
    "_value_hint_flag": 0,
    "_cvot_flags": 4,
    "_type_flags": 4,
    "_property_category": 4,
}
_SLIDER: dict[str, int] = {**_POPUP, "_type_flags": 8, "_property_category": 9}
_STYLE: dict[str, int] = {**_POPUP, "_value_hint_type": 1}

#: Layer streams that vary over time but take HOLD keys only, with the `tdb4`
#: fields After Effects writes for each, static or keyed. AE 2026 reports
#: `LINEAR` and `BEZIER` invalid for these and keys them with HOLD.
#:
#: Every stream stores an interpolation mask of 4 in `_cvot_flags`, the HOLD
#: bit, and a zero `_value_hint_flag`. The other fields follow the stream's
#: control, as stored across the sample projects and written by AE 2026 when
#: a script sets or keys a stream of each group.
HOLD_ONLY_STREAMS: dict[str, dict[str, int]] = {
    **dict.fromkeys(
        (
            "ADBE Light Falloff Type",
            "ADBE Camera Depth of Field",
            "ADBE Iris Shape",
            "ADBE R Channel Blend",
            "ADBE G Channel Blend",
            "ADBE B Channel Blend",
            "ADBE Blend Interior",
            "ADBE Blend Ranges",
            "ADBE Text Reverse Path",
            "ADBE Text Perpendicular To Path",
            "ADBE Text Force Align Path",
            "ADBE Text Track Type",
            "ADBE Text Wiggly Lock Dim",
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
        ),
        _POPUP,
    ),
    "ADBE Text Selector Mode": {**_POPUP, "_value_hint_type": 2},
    "ADBE Text Temporal Freq": _SLIDER,
    "ADBE Text Character Correlation": _SLIDER,
    **dict.fromkeys(
        (
            "dropShadow/mode2",
            "dropShadow/useGlobalAngle",
            "dropShadow/layerConceals",
            "innerShadow/mode2",
            "innerShadow/useGlobalAngle",
            "outerGlow/mode2",
            "outerGlow/AEColorChoice",
            "outerGlow/glowTechnique",
            "innerGlow/mode2",
            "innerGlow/AEColorChoice",
            "innerGlow/glowTechnique",
            "innerGlow/innerGlowSource",
            "bevelEmboss/bevelStyle",
            "bevelEmboss/bevelTechnique",
            "bevelEmboss/bevelDirection",
            "bevelEmboss/useGlobalAngle",
            "bevelEmboss/highlightMode",
            "bevelEmboss/shadowMode",
            "chromeFX/mode2",
            "chromeFX/invert",
            "solidFill/mode2",
            "gradientFill/mode2",
            "gradientFill/type",
            "gradientFill/reverse",
            "gradientFill/align",
            "patternFill/mode2",
            "patternFill/align",
            "frameFX/mode2",
            "frameFX/style",
        ),
        _STYLE,
    ),
}
