"""Translate Photoshop layer-style descriptors into AE Layer Styles values.

After Effects' "Editable Layer Styles" import converts each layer's effects
descriptor (the `lmfx` tagged block, or `lfx2` for documents where no style
has multiple instances - both wrap the same ActionDescriptor serialization)
into the layer's `ADBE Layer Styles` property tree, together with the
blend-options tagged blocks (`iOpa`, `infx`, `brst`) and the document's
global-light image resources (1037/1049).

The mapping rules mirror AE 2026 (the `psd_layer_styles*.aep` fixtures and
the synthetic-descriptor probes):

- Parameter values are imported verbatim (the master `Scl ` scale factor is
  ignored, as are contours, anti-alias flags and dialog bookkeeping).
- A style with more than one instance (a `<style>Multi` list) is dropped
  entirely - AE does not import even a representable instance. A one-element
  `Multi` list imports as a normal single style.
- A single stroke imports regardless of paint type: the gradient fill itself
  is dropped and the descriptor's color imported.
"""

from __future__ import annotations

import struct
import warnings
from typing import TYPE_CHECKING, NamedTuple, cast

from ..models.properties.gradient import (
    Gradient,
    GradientAlphaStop,
    GradientColorStop,
)
from .media_probe import iter_image_resources

if TYPE_CHECKING:
    import os
    from typing import Any, Callable, Union

    from .psd_layers import PsdGroup, PsdLayer, PsdStyleBlocks

    StyleValue = Union[float, "list[float]", Gradient]


class UnsupportedStyleError(ValueError):
    """A style instance uses a construct AE's import cannot represent."""


class PsdLayerStyles(NamedTuple):
    """One layer's styles resolved to AE Layer Styles values."""

    values: dict[str, StyleValue]
    """AE property values keyed by match name (`"dropShadow/mode2"`,
    `"ADBE Global Angle2"`, ...) for every imported style, enabled or not.
    Values equal to AE's defaults are included; the import step writes only
    the non-default ones (matching AE)."""

    enabled: tuple[str, ...]
    """Match-name prefixes of the styles whose eyeball is on (`"dropShadow"`,
    ...). A style can be imported (contribute to `values`) while disabled -
    AE keeps the single-instance glow/bevel/satin styles' parameters even
    when their eyeball is off."""

    dropped: tuple[str, ...]
    """Match-name prefixes of styles present in the document but dropped
    whole: multi-instance styles (AE drops those entirely) and styles whose
    descriptor uses constructs AE cannot represent."""

    disabled: tuple[str, ...] = ()
    """Match-name prefixes of styles whose descriptor carries
    `present=True` with the eyeball off. AE imports their parameters and
    writes the distinct `tdsb` enable byte 0x00 (probed psd_fill_opacity
    fixture; a `present=False` style keeps the absent-style 0x02)."""

    blend_options: bool = False
    """`True` when the layer carries blend-options tagged blocks
    (`iOpa`/`infx`/`brst`). AE enables the container + Blend Options chain
    (`tdsb` 0x01) for these layers even when no style is enabled."""


# ---------------------------------------------------------------------------
# ActionDescriptor reader
# ---------------------------------------------------------------------------


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def raw(self, n: int) -> bytes:
        value = self.data[self.pos : self.pos + n]
        if len(value) != n:
            raise ValueError("truncated descriptor")
        self.pos += n
        return value

    def u4(self) -> int:
        return cast("int", struct.unpack(">I", self.raw(4))[0])

    def key(self) -> str:
        n = self.u4()
        return self.raw(4 if n == 0 else n).decode("latin-1")

    def ustr(self) -> str:
        n = self.u4()
        return self.raw(2 * n).decode("utf-16-be").rstrip("\x00")


def _parse_item(reader: _Reader, os_type: str) -> Any:
    if os_type in ("Objc", "GlbO"):
        reader.ustr()  # name from classID (unused)
        cls = reader.key()
        out: dict[str, Any] = {"_class": cls}
        for _ in range(reader.u4()):
            key = reader.key()
            out[key] = _parse_item(reader, reader.raw(4).decode("latin-1"))
        return out
    if os_type == "VlLs":
        return [
            _parse_item(reader, reader.raw(4).decode("latin-1"))
            for _ in range(reader.u4())
        ]
    if os_type == "doub":
        return struct.unpack(">d", reader.raw(8))[0]
    if os_type == "UntF":
        reader.raw(4)  # unit (imported verbatim; the unit tag is redundant)
        return struct.unpack(">d", reader.raw(8))[0]
    if os_type == "TEXT":
        return reader.ustr()
    if os_type == "enum":
        reader.key()  # enum type
        return reader.key()
    if os_type == "long":
        return struct.unpack(">i", reader.raw(4))[0]
    if os_type == "comp":
        return struct.unpack(">q", reader.raw(8))[0]
    if os_type == "bool":
        return reader.raw(1) != b"\x00"
    if os_type in ("type", "GlbC"):
        reader.ustr()
        return reader.key()
    if os_type in ("tdta", "alis"):
        reader.raw(reader.u4())
        return None
    raise ValueError(f"unhandled descriptor OSType {os_type!r}")


def _parse_effects_descriptor(body: bytes) -> dict[str, Any]:
    """Parse an `lmfx`/`lfx2` block body: version u4s (ending 16) + root Objc."""
    reader = _Reader(body)
    for _ in range(4):
        if reader.u4() == 16:
            break
    else:
        raise ValueError("no descriptor version marker")
    root = _parse_item(reader, "Objc")
    if not isinstance(root, dict):
        raise ValueError("effects descriptor root is not an object")
    return root


# ---------------------------------------------------------------------------
# PS -> AE value tables (AE 2026; see the plan's probe results)
# ---------------------------------------------------------------------------

# Blend-mode enum -> the styles' mode2 integer space (complete for every
# Photoshop-expressible mode; ints 3/9/15/23/26/31 are AE-only slots).
# Legacy writers store the classic modes as zero-length 4-char typeIDs;
# the aliases below are exactly the set AE 2026 resolves (spliced 27-mode
# probe, psd_blend_4cc_all.aep). AE does NOT resolve the post-CS modes'
# 4CCs (lbrn/dkCl/lddg/lgCl/vLit/lLit/pLit/hMix/fsub/fdiv - no legacy
# writer ever produced them): it silently keeps the default mode, so those
# stay unmapped here and py_aep warns where AE is silent.
_BLEND_MODE2 = {
    "Nrml": 1.0,
    "Dslv": 2.0,
    "Drkn": 4.0,
    "Mltp": 5.0,
    "CBrn": 6.0,
    "Lghn": 10.0,
    "Scrn": 11.0,
    "CDdg": 12.0,
    "Ovrl": 16.0,
    "SftL": 17.0,
    "HrdL": 18.0,
    "Dfrn": 24.0,
    "Xclu": 25.0,
    "H   ": 27.0,
    "Strt": 28.0,
    "Clr ": 29.0,
    "Lmns": 30.0,
    "normal": 1.0,
    "dissolve": 2.0,
    "darken": 4.0,
    "multiply": 5.0,
    "colorBurn": 6.0,
    "linearBurn": 7.0,
    "darkerColor": 8.0,
    "lighten": 10.0,
    "screen": 11.0,
    "colorDodge": 12.0,
    "linearDodge": 13.0,
    "lighterColor": 14.0,
    "overlay": 16.0,
    "softLight": 17.0,
    "hardLight": 18.0,
    "vividLight": 19.0,
    "linearLight": 20.0,
    "pinLight": 21.0,
    "hardMix": 22.0,
    "difference": 24.0,
    "exclusion": 25.0,
    "hue": 27.0,
    "saturation": 28.0,
    "color": 29.0,
    "luminosity": 30.0,
    "blendSubtraction": 32.0,
    "blendDivide": 33.0,
}

_GLOW_TECHNIQUE = {"SfBL": 1.0, "PrBL": 2.0}
_INNER_GLOW_SOURCE = {"SrcE": 1.0, "SrcC": 2.0}
# Bevel style/technique/direction: InrB(2)/Embs(3), PrBL(2) and Out(2) are
# fixture-pinned; the rest follow AE's dropdown order.
_BEVEL_STYLE = {"OtrB": 1.0, "InrB": 2.0, "Embs": 3.0, "PlEb": 4.0}
_BEVEL_TECHNIQUE = {"SfBL": 1.0, "PrBL": 2.0, "Slmt": 3.0}
_BEVEL_DIRECTION = {"In  ": 1.0, "Out ": 2.0}
_GRADIENT_TYPE = {"Lnr ": 1.0, "Rdl ": 2.0, "Angl": 3.0, "Rflc": 4.0, "Dmnd": 5.0}
# Stroke position: OutF=1 (default), InsF=2, CtrF=3 (probe-pinned).
_STROKE_POSITION = {"OutF": 1.0, "InsF": 2.0, "CtrF": 3.0}


def _enum(table: dict[str, float]) -> Callable[[Any], float]:
    def convert(value: Any) -> float:
        try:
            return table[value]
        except (KeyError, TypeError):
            raise UnsupportedStyleError(f"unmapped enum value {value!r}") from None

    return convert


def _number(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise UnsupportedStyleError(f"expected a number, got {value!r}")
    return float(value)


def _bool01(value: Any) -> float:
    return 1.0 if value else 0.0


def _color(value: Any) -> list[float]:
    if not isinstance(value, dict) or value.get("_class") != "RGBC":
        raise UnsupportedStyleError(f"unsupported color model {value!r}")
    return [
        value["Rd  "] / 255.0,
        value["Grn "] / 255.0,
        value["Bl  "] / 255.0,
        1.0,
    ]


def _point(value: Any) -> list[float]:
    if not isinstance(value, dict):
        raise UnsupportedStyleError(f"expected a point, got {value!r}")
    return [_number(value["Hrzn"]), _number(value["Vrtc"])]


def _gradient(value: Any) -> Gradient:
    if not isinstance(value, dict) or value.get("_class") != "Grdn":
        raise UnsupportedStyleError(f"expected a gradient, got {value!r}")
    if value.get("GrdF") != "CstS":
        # Noise gradients ("ClNs") have no AE representation.
        raise UnsupportedStyleError(f"unsupported gradient form {value.get('GrdF')!r}")
    # `Lctn` stop locations are always on Photoshop's fixed 0..4096 scale.
    # The sibling `Intr` field is the gradient editor's Smoothness slider
    # (0..4096 = 0..100%), NOT the location scale - every repo sample has
    # Intr=4096, so it must not be used as the divisor (smoothness 50%
    # would double every offset, and 0% would divide by zero). Smoothness
    # is left unmapped (AE's gradientSmoothness handling is unprobed).
    color_stops = []
    for stop in value["Clrs"]:
        red, green, blue, _ = _color(stop["Clr "])
        color_stops.append(
            GradientColorStop(
                offset=stop["Lctn"] / 4096.0,
                midpoint=stop["Mdpn"] / 100.0,
                color=(red, green, blue),
            )
        )
    alpha_stops = [
        GradientAlphaStop(
            offset=stop["Lctn"] / 4096.0,
            midpoint=stop["Mdpn"] / 100.0,
            alpha=_number(stop["Opct"]) / 100.0,
        )
        for stop in value["Trns"]
    ]
    return Gradient(color_stops, alpha_stops)


class _Param(NamedTuple):
    descriptor_key: str
    suffix: str
    convert: Callable[[Any], StyleValue]


_SHADOW_PARAMS = (
    _Param("Md  ", "mode2", _enum(_BLEND_MODE2)),
    _Param("Clr ", "color", _color),
    _Param("Opct", "opacity", _number),
    _Param("uglg", "useGlobalAngle", _bool01),
    _Param("lagl", "localLightingAngle", _number),
    _Param("Dstn", "distance", _number),
    _Param("Ckmt", "chokeMatte", _number),
    _Param("blur", "blur", _number),
    _Param("Nose", "noise", _number),
)
_GLOW_PARAMS = (
    _Param("Md  ", "mode2", _enum(_BLEND_MODE2)),
    _Param("Opct", "opacity", _number),
    _Param("Nose", "noise", _number),
    _Param("Clr ", "color", _color),
    _Param("Grad", "gradient", _gradient),
    _Param("GlwT", "glowTechnique", _enum(_GLOW_TECHNIQUE)),
    _Param("Ckmt", "chokeMatte", _number),
    _Param("blur", "blur", _number),
    _Param("Inpr", "inputRange", _number),
    _Param("ShdN", "shadingNoise", _number),
)

# Style key in the effects descriptor -> (AE match-name prefix, params).
_STYLES: dict[str, tuple[str, tuple[_Param, ...]]] = {
    "DrSh": (
        "dropShadow",
        _SHADOW_PARAMS + (_Param("layerConceals", "layerConceals", _bool01),),
    ),
    "IrSh": ("innerShadow", _SHADOW_PARAMS),
    "OrGl": ("outerGlow", _GLOW_PARAMS),
    "IrGl": (
        "innerGlow",
        _GLOW_PARAMS + (_Param("glwS", "innerGlowSource", _enum(_INNER_GLOW_SOURCE)),),
    ),
    "ebbl": (
        "bevelEmboss",
        (
            _Param("bvlS", "bevelStyle", _enum(_BEVEL_STYLE)),
            _Param("bvlT", "bevelTechnique", _enum(_BEVEL_TECHNIQUE)),
            _Param("srgR", "strengthRatio", _number),
            _Param("bvlD", "bevelDirection", _enum(_BEVEL_DIRECTION)),
            _Param("blur", "blur", _number),
            _Param("Sftn", "softness", _number),
            _Param("uglg", "useGlobalAngle", _bool01),
            _Param("lagl", "localLightingAngle", _number),
            _Param("Lald", "localLightingAltitude", _number),
            _Param("hglM", "highlightMode", _enum(_BLEND_MODE2)),
            _Param("hglC", "highlightColor", _color),
            _Param("hglO", "highlightOpacity", _number),
            _Param("sdwM", "shadowMode", _enum(_BLEND_MODE2)),
            _Param("sdwC", "shadowColor", _color),
            _Param("sdwO", "shadowOpacity", _number),
        ),
    ),
    "ChFX": (
        "chromeFX",
        (
            _Param("Md  ", "mode2", _enum(_BLEND_MODE2)),
            _Param("Clr ", "color", _color),
            _Param("Opct", "opacity", _number),
            _Param("lagl", "localLightingAngle", _number),
            _Param("Dstn", "distance", _number),
            _Param("blur", "blur", _number),
            _Param("Invr", "invert", _bool01),
        ),
    ),
    "SoFi": (
        "solidFill",
        (
            _Param("Md  ", "mode2", _enum(_BLEND_MODE2)),
            _Param("Clr ", "color", _color),
            _Param("Opct", "opacity", _number),
        ),
    ),
    "GrFl": (
        "gradientFill",
        (
            _Param("Md  ", "mode2", _enum(_BLEND_MODE2)),
            _Param("Opct", "opacity", _number),
            _Param("Grad", "gradient", _gradient),
            _Param("Angl", "angle", _number),
            _Param("Type", "type", _enum(_GRADIENT_TYPE)),
            _Param("Rvrs", "reverse", _bool01),
            _Param("Algn", "align", _bool01),
            _Param("Scl ", "scale", _number),
            _Param("Ofst", "offset", _point),
        ),
    ),
    "patternFill": (
        "patternFill",
        (
            _Param("Md  ", "mode2", _enum(_BLEND_MODE2)),
            _Param("Opct", "opacity", _number),
            _Param("Algn", "align", _bool01),
            _Param("Scl ", "scale", _number),
            _Param("phase", "phase", _point),
        ),
    ),
    "FrFX": (
        "frameFX",
        (
            _Param("Md  ", "mode2", _enum(_BLEND_MODE2)),
            _Param("Clr ", "color", _color),
            _Param("Sz  ", "size", _number),
            _Param("Opct", "opacity", _number),
            _Param("Styl", "style", _enum(_STROKE_POSITION)),
        ),
    ),
}

# `<style>Multi` list keys (the lmfx multi-instance containers).
_MULTI_KEYS = {f"{prefix}Multi": key for key, (prefix, _) in _STYLES.items()}


def _style_instances(descriptor: dict[str, Any]) -> dict[str, list[Any]]:
    """Collect style instances per descriptor style key.

    Single-instance styles appear as a plain object under the style key,
    multi-instance ones as a list under the `<style>Multi` key.
    """
    instances: dict[str, list[Any]] = {}
    for key, value in descriptor.items():
        if key in _STYLES:
            instances.setdefault(key, []).append(value)
        elif key in _MULTI_KEYS and isinstance(value, list):
            instances.setdefault(_MULTI_KEYS[key], []).extend(value)
    return instances


# Styles Photoshop stores as a plain key whenever they exist (single-instance
# only: the two glows, Bevel/Emboss, Satin). AE imports their parameters
# whenever the key exists, even with `present=False` (psd_noise_gradient
# fixtures). Every other style imports its parameters iff the instance has
# `present=True` - see `parse_layer_styles`.
_ALWAYS_WHEN_PRESENT = frozenset({"outerGlow", "innerGlow", "bevelEmboss", "chromeFX"})

# Styles whose gradient carries the editor's Smoothness slider as `Intr`
# (0..4096 = 0..100%); AE maps it onto the `gradientSmoothness` leaf
# (psd_styles_smoothness fixture: 2048 -> 50, 1024 -> 25).
_GRADIENT_SMOOTHNESS_PREFIXES = frozenset({"outerGlow", "innerGlow", "gradientFill"})


def _convert_style(
    prefix: str, params: tuple[_Param, ...], instance: dict[str, Any]
) -> dict[str, StyleValue]:
    values: dict[str, StyleValue] = {}
    for param in params:
        if param.descriptor_key not in instance:
            continue
        try:
            values[f"{prefix}/{param.suffix}"] = param.convert(
                instance[param.descriptor_key]
            )
        except UnsupportedStyleError as exc:
            # A single unrepresentable parameter (e.g. a noise-type gradient)
            # is skipped, not fatal - AE imports the style without that leaf.
            # Warn so an unmapped value (e.g. a legacy 4-char blend-mode
            # enum) does not silently leave the leaf at its default.
            warnings.warn(
                f"style parameter {prefix}/{param.suffix} was skipped "
                f"({exc}); the imported style keeps the AE default",
                stacklevel=2,
            )
            continue
    # The glows choose between a solid color and a gradient fill; AE records
    # the choice explicitly (1 = color, the default; 2 = gradient).
    if prefix in ("outerGlow", "innerGlow"):
        values[f"{prefix}/AEColorChoice"] = 2.0 if "Grad" in instance else 1.0
    if prefix in _GRADIENT_SMOOTHNESS_PREFIXES:
        grad = instance.get("Grad")
        if (
            isinstance(grad, dict)
            and grad.get("GrdF") == "CstS"
            and isinstance(grad.get("Intr"), (int, float))
        ):
            values[f"{prefix}/gradientSmoothness"] = grad["Intr"] / 4096.0 * 100.0
    return values


# ---------------------------------------------------------------------------
# Blend options
# ---------------------------------------------------------------------------


def read_global_light(file: str | os.PathLike[str]) -> tuple[float, float]:
    """The document's global light `(angle, altitude)` in degrees.

    Read from image resources 1037/1049; AE's Layer Styles defaults
    (120, 30) apply when a resource is absent or the section is malformed.
    """
    angle, altitude = 120.0, 30.0
    with open(file, "rb") as fp:
        if fp.read(4) != b"8BPS":
            return angle, altitude
        fp.seek(26)
        for resource_id, body in iter_image_resources(fp):
            if resource_id == 1037 and len(body) >= 4:
                angle = float(struct.unpack(">i", body[:4])[0])
            elif resource_id == 1049 and len(body) >= 4:
                altitude = float(struct.unpack(">i", body[:4])[0])
    return angle, altitude


def _blend_options_values(
    blocks: PsdStyleBlocks, global_light: tuple[float, float]
) -> dict[str, StyleValue]:
    angle, altitude = global_light
    values: dict[str, StyleValue] = {
        "ADBE Global Angle2": angle,
        "ADBE Global Altitude2": altitude,
    }
    if blocks.fill_opacity is not None:
        values["ADBE Layer Fill Opacity2"] = float(
            round(blocks.fill_opacity * 100 / 255)
        )
    if blocks.blend_interior is not None:
        values["ADBE Blend Interior"] = _bool01(blocks.blend_interior)
    # `brst` lists the channels EXCLUDED from blending as big-endian u4
    # indices (0=R, 1=G, 2=B); an absent/empty block keeps all channels on.
    restricted = {
        struct.unpack(">I", blocks.channel_restrictions[off : off + 4])[0]
        for off in range(0, len(blocks.channel_restrictions) - 3, 4)
    }
    for index, name in enumerate(("R", "G", "B")):
        values[f"ADBE {name} Channel Blend"] = 0.0 if index in restricted else 1.0
    return values


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_layer_styles(
    leaf: PsdLayer, global_light: tuple[float, float]
) -> PsdLayerStyles | None:
    """Resolve a layer's styles to AE Layer Styles values.

    Args:
        leaf: A `PsdLayer` from `read_psd_layers` (carries the raw blocks).
        global_light: The document global light from `read_global_light`.

    Returns:
        The resolved styles, or `None` when the layer has no style-related
        blocks at all or its descriptor cannot be decoded (the layer then
        keeps the plain disabled skeleton; a warning is emitted so the
        style loss is visible).
    """
    blocks = leaf.style_blocks
    if blocks is None:
        return None
    # Photoshop writes an `infx` block (value 0) on every ordinary layer;
    # only a USER deviation activates AE's blend-options chain: a Fill
    # slider away from 100% (`iOpa`), Blend Interior checked (`infx` true)
    # or a channel restriction (`brst`).
    blend_data = (
        blocks.fill_opacity is not None
        or bool(blocks.blend_interior)
        or bool(blocks.channel_restrictions)
    )
    descriptor: dict[str, Any] = {}
    if blocks.effects is not None:
        try:
            descriptor = _parse_effects_descriptor(blocks.effects)
        except ValueError:
            warnings.warn(
                f"layer {leaf.name!r}: the layer-styles descriptor could not "
                "be decoded; the styles are imported as disabled",
                stacklevel=2,
            )
            return None
    values: dict[str, StyleValue] = {}
    enabled: list[str] = []
    dropped: list[str] = []
    disabled: list[str] = []
    imported_any = False
    for key, instances in _style_instances(descriptor).items():
        prefix, params = _STYLES[key]
        present_instances = [inst for inst in instances if isinstance(inst, dict)]
        if len(present_instances) > 1:
            # AE drops a multi-instance style entirely, even when every
            # instance is representable.
            dropped.append(prefix)
            continue
        if not present_instances:
            continue
        instance = present_instances[0]
        is_enabled = bool(instance.get("enab", False))
        # `present` distinguishes an unchecked-but-kept style (imported,
        # tdsb 0x00) from a removed one Photoshop left in the descriptor
        # (skeleton, 0x02). Old writers without the key follow `enab`.
        is_present = bool(instance.get("present", is_enabled))
        if not is_present and prefix not in _ALWAYS_WHEN_PRESENT:
            continue
        try:
            values.update(_convert_style(prefix, params, instance))
        except (KeyError, TypeError):
            dropped.append(prefix)
            continue
        imported_any = True
        if is_enabled:
            enabled.append(prefix)
        elif is_present:
            disabled.append(prefix)
    if imported_any or blend_data:
        values.update(_blend_options_values(blocks, global_light))
    return PsdLayerStyles(
        values, tuple(enabled), tuple(dropped), tuple(disabled), blend_data
    )


def has_enabled_styles(node: PsdLayer | PsdGroup) -> bool:
    """Whether any style instance is enabled on the layer or group.

    Used to gate merge-mode geometry: enabled styles (including multi-instance
    ones) expand the rasterized content box in ways py_aep cannot compute. An
    undecodable descriptor counts as styled (the conservative answer).
    """
    blocks = node.style_blocks
    if blocks is None or blocks.effects is None:
        return False
    try:
        descriptor = _parse_effects_descriptor(blocks.effects)
    except ValueError:
        return True
    return any(
        isinstance(inst, dict) and inst.get("enab", False)
        for instances in _style_instances(descriptor).values()
        for inst in instances
    )
