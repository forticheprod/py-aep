"""Tests for the Photoshop layer-style descriptor resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.models.properties.gradient import Gradient
from py_aep.resolvers.psd_layers import read_psd_layers
from py_aep.resolvers.psd_styles import (
    _instance_box,
    has_enabled_styles,
    merged_styles_bounds,
    parse_layer_styles,
    read_global_light,
)

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"

STYLED = ASSETS / "psd_layer_styles.psd"
VARIANT = ASSETS / "psd_layer_styles_variant.psd"
SINGLE = ASSETS / "psd_layer_styles_8bits_single.psd"
NOISE = ASSETS / "psd_noise_gradient.psd"
NOISE_32 = ASSETS / "psd_noise_gradient_32bpc.psd"


def _leaves(psd: Path) -> dict:
    return {leaf.name: leaf for leaf in read_psd_layers(psd)}


class TestReadGlobalLight:
    def test_document_resources(self) -> None:
        # Resources 1037/1049 of the sample document (AE wrote 49/11 into
        # every layer's Blend Options in the editable fixtures).
        assert read_global_light(STYLED) == (49.0, 11.0)

    def test_defaults_when_absent(self) -> None:
        # choose_layer.psd carries no global-light resources; AE's Layer
        # Styles defaults apply.
        assert read_global_light(ASSETS / "choose_layer.psd") == (120.0, 30.0)


class TestParseLayerStyles:
    def test_values_match_editable_fixture(self) -> None:
        # Spot-check the AE-unit conversion against values AE wrote into
        # psd_layer_styles_single.aep (fixture-decoded ground truth).
        leaf = _leaves(SINGLE)["Layer 1"]
        styles = parse_layer_styles(leaf, read_global_light(SINGLE))
        assert styles is not None
        values = styles.values
        assert values["dropShadow/mode2"] == 17.0  # softLight
        assert values["innerShadow/mode2"] == 4.0  # darken
        assert values["outerGlow/mode2"] == 24.0  # difference
        assert values["innerGlow/mode2"] == 13.0  # linearDodge
        assert values["frameFX/mode2"] == 10.0  # lighten
        assert values["frameFX/style"] == 2.0  # InsF = inside
        assert values["frameFX/size"] == 6.0
        assert values["frameFX/opacity"] == 91.0
        # The gradient-paint stroke imports its color verbatim (black).
        assert values["frameFX/color"] == [0.0, 0.0, 0.0, 1.0]
        assert values["dropShadow/opacity"] == 44.0
        assert values["dropShadow/localLightingAngle"] == 90.0
        assert values["outerGlow/AEColorChoice"] == 2.0  # gradient fill
        assert values["innerGlow/innerGlowSource"] == 2.0  # SrcC
        assert values["bevelEmboss/bevelStyle"] == 3.0  # Embs
        assert values["bevelEmboss/highlightMode"] == 12.0  # colorDodge
        # Blend options: global light + iOpa/brst/infx tagged blocks.
        assert values["ADBE Global Angle2"] == 49.0
        assert values["ADBE Global Altitude2"] == 11.0
        assert values["ADBE Layer Fill Opacity2"] == 89.0
        assert values["ADBE G Channel Blend"] == 0.0
        assert values["ADBE R Channel Blend"] == 1.0
        assert values["ADBE Blend Interior"] == 1.0
        assert len(styles.enabled) == 10
        assert styles.dropped == ()

    def test_gradient_stops(self) -> None:
        leaf = _leaves(SINGLE)["Layer 1"]
        styles = parse_layer_styles(leaf, read_global_light(SINGLE))
        assert styles is not None
        gradient = styles.values["outerGlow/gradient"]
        assert isinstance(gradient, Gradient)
        assert len(gradient.color_stops) == 5
        assert len(gradient.alpha_stops) == 2
        # Stop positions are Lctn/4096; colors Rd/255 (write path quantizes
        # to the f4 AE stores).
        offsets = [stop.offset for stop in gradient.color_stops]
        assert offsets == [0.0, 0.25, 0.5, 0.75, 1.0]
        first = gradient.color_stops[0].color
        assert abs(first[0] - 0.9137255) < 1e-6

    def test_multi_instance_styles_drop(self) -> None:
        # The main PSD has TWO stroke instances per layer; AE drops the
        # whole style (even though one instance is a plain solid stroke).
        leaf = _leaves(STYLED)["Layer 1"]
        styles = parse_layer_styles(leaf, read_global_light(STYLED))
        assert styles is not None
        assert styles.dropped == ("frameFX",)
        assert "frameFX" not in styles.enabled
        assert "frameFX/mode2" not in styles.values

    def test_two_representable_instances_still_drop(self) -> None:
        # The variant's top layer has two identical inner shadows: the
        # instance COUNT is the trigger, not unrepresentable content.
        leaf = _leaves(VARIANT)["Layer 1 copy"]
        styles = parse_layer_styles(leaf, read_global_light(VARIANT))
        assert styles is not None
        assert styles.dropped == ("innerShadow",)
        # Its single gradient-paint stroke imports fine.
        assert "frameFX" in styles.enabled

    def test_no_styles_returns_none(self) -> None:
        leaf = _leaves(ASSETS / "choose_layer.psd")["solo"]
        assert leaf.style_blocks is None
        assert parse_layer_styles(leaf, (120.0, 30.0)) is None

    @pytest.mark.parametrize("psd", [NOISE, NOISE_32])
    def test_noise_gradient_keeps_style_omits_gradient(self, psd: Path) -> None:
        # AE imports a style whose gradient is a Noise gradient, dropping only
        # the (unrepresentable) gradient leaf. On 'Layer 1' the gradient fill
        # carries the noise gradient.
        leaf = _leaves(psd)["Layer 1"]
        styles = parse_layer_styles(leaf, read_global_light(psd))
        assert styles is not None
        assert "gradientFill" in styles.enabled
        assert "gradientFill/opacity" in styles.values
        assert "gradientFill/gradient" not in styles.values
        assert styles.dropped == ()

    def test_present_but_disabled_glows_still_import(self) -> None:
        # AE keeps the single-instance glow/bevel/satin parameters even when
        # the style is fully unchecked (present=False); other styles with
        # present=False stay plain skeletons.
        leaf = _leaves(NOISE)["Layer 1"]
        styles = parse_layer_styles(leaf, read_global_light(NOISE))
        assert styles is not None
        # outerGlow is present=False here: imported, neither enabled nor
        # in `disabled` (its tdsb stays the absent-style 0x02).
        assert "outerGlow/opacity" in styles.values
        assert "outerGlow" not in styles.enabled
        assert "outerGlow" not in styles.disabled
        # A present=False pattern overlay is a plain skeleton (no params).
        assert not any(mn.startswith("patternFill/") for mn in styles.values)

    def test_present_true_disabled_shadow_imports(self) -> None:
        # present=True + enab=False: parameters import and the prefix lands
        # in `disabled` (AE writes tdsb 0x00 - psd_fill_opacity fixture).
        leaf = _leaves(ASSETS / "psd_fill_opacity.psd")["fill plus disabled shadow"]
        styles = parse_layer_styles(leaf, (120.0, 30.0))
        assert styles is not None
        assert "dropShadow" in styles.disabled
        assert "dropShadow" not in styles.enabled
        assert styles.values["dropShadow/distance"] == 7.0
        assert styles.values["ADBE Layer Fill Opacity2"] == 60.0
        assert styles.blend_options is True

    def test_fill_opacity_without_styles(self) -> None:
        # A Fill slider away from 100% imports alone: no lfx2 block at all,
        # yet AE enables the blend-options chain and writes the leaf.
        leaf = _leaves(ASSETS / "psd_fill_opacity.psd")["fill only"]
        assert leaf.style_blocks is not None
        assert leaf.style_blocks.effects is None
        styles = parse_layer_styles(leaf, (120.0, 30.0))
        assert styles is not None
        assert styles.blend_options is True
        assert styles.enabled == ()
        assert styles.values["ADBE Layer Fill Opacity2"] == 40.0

    def test_gradient_smoothness_maps_from_intr(self) -> None:
        # Grdn `Intr` is the Smoothness slider; AE maps it onto the
        # gradientSmoothness leaf as Intr/4096*100.
        leaf = _leaves(ASSETS / "psd_styles_smoothness.psd")["Layer 1"]
        styles = parse_layer_styles(leaf, (120.0, 30.0))
        assert styles is not None
        assert styles.values["gradientFill/gradientSmoothness"] == 50.0
        assert styles.values["outerGlow/gradientSmoothness"] == 25.0

    def test_legacy_4cc_blend_modes(self) -> None:
        # Zero-length 4-char typeID enum spellings resolve like AE does
        # (spliced psd_blend_4cc fixture: Mltp=multiply, SftL=softLight).
        leaf = _leaves(ASSETS / "psd_blend_4cc.psd")["legacy modes"]
        styles = parse_layer_styles(leaf, (120.0, 30.0))
        assert styles is not None
        assert styles.values["dropShadow/mode2"] == 5.0
        assert styles.values["innerShadow/mode2"] == 17.0

    def test_4cc_alias_set_matches_ae(self) -> None:
        # The 27-mode probe (psd_blend_4cc_all.aep): the 16 true-legacy
        # 4CCs resolve; the post-CS ones (lbrn, vLit, fsub, ...) do NOT -
        # AE keeps the default mode, so py skips the leaf (with a warning).
        leaves = _leaves(ASSETS / "psd_blend_4cc_all.psd")
        resolved = {
            "normal": 1.0,
            "dissolve": 2.0,
            "darken": 4.0,
            "colorBurn": 6.0,
            "lighten": 10.0,
            "screen": 11.0,
            "colorDodge": 12.0,
            "overlay": 16.0,
            "hardLight": 18.0,
            "difference": 24.0,
            "exclusion": 25.0,
            "hue": 27.0,
            "saturation": 28.0,
            "color": 29.0,
            "luminosity": 30.0,
        }
        unresolved = (
            "linearBurn",
            "darkerColor",
            "linearDodge",
            "lighterColor",
            "vividLight",
            "linearLight",
            "pinLight",
            "hardMix",
            "blendSubtraction",
            "blendDivide",
        )
        for name, mode2 in resolved.items():
            styles = parse_layer_styles(leaves[name], (120.0, 30.0))
            assert styles is not None
            assert styles.values["dropShadow/mode2"] == mode2, name
        for name in unresolved:
            with pytest.warns(UserWarning, match="mode2"):
                styles = parse_layer_styles(leaves[name], (120.0, 30.0))
            assert styles is not None
            assert "dropShadow/mode2" not in styles.values, name


class TestHasEnabledStyles:
    def test_styled_and_multi_instance_layers(self) -> None:
        # Multi-instance styles rasterize in merge mode too, so they count.
        assert has_enabled_styles(_leaves(STYLED)["Layer 1"]) is True
        assert has_enabled_styles(_leaves(VARIANT)["Layer 1 copy"]) is True

    def test_style_less_layer(self) -> None:
        assert has_enabled_styles(_leaves(ASSETS / "choose_layer.psd")["solo"]) is False


# Pads (left, top, right, bottom) After Effects 2026 gave a 24x25 layer carrying
# one merged style, measured by importing byte-patched copies of
# psd_layer_styles.psd as COMP_CROPPED_LAYERS.
_DS = {
    "enab": True,
    "Dstn": 0.0,
    "Ckmt": 5.0,
    "uglg": False,
    "lagl": 90.0,
    "AntA": True,
}
_OG = {"enab": True, "Ckmt": 0.0, "GlwT": "SfBL", "AntA": True}
_BV = {"enab": True, "Sftn": 0.0, "useShape": True, "AntA": True}


class TestMergedStylesBounds:
    @pytest.mark.parametrize(
        ("key", "instance", "pads"),
        [
            ("DrSh", {**_DS, "blur": 10.0}, (12, 12, 12, 12)),
            ("DrSh", {**_DS, "blur": 0.0}, (5, 5, 4, 4)),
            ("DrSh", {**_DS, "blur": 1.0, "Ckmt": 50.0}, (8, 8, 7, 7)),
            ("DrSh", {**_DS, "blur": 10.0, "Ckmt": 0.0, "AntA": False}, (9, 9, 10, 10)),
            # Distance 11 along a 30 degree light: offsets (-9.53, 5.5) round
            # half away from zero to (-10, 6).
            (
                "DrSh",
                {**_DS, "blur": 35.0, "Dstn": 11.0, "lagl": 30.0},
                (47, 31, 27, 43),
            ),
            (
                "OrGl",
                {**_OG, "blur": 7.0, "Ckmt": 8.0, "GlwT": "PrBL"},
                (12, 12, 11, 11),
            ),
            ("OrGl", {**_OG, "blur": 43.0, "Ckmt": 50.0}, (45, 45, 45, 45)),
            ("FrFX", {"enab": True, "Styl": "CtrF", "Sz  ": 5.0}, (5, 5, 5, 5)),
            ("FrFX", {"enab": True, "Styl": "OutF", "Sz  ": 12.0}, (14, 14, 14, 14)),
            (
                "ebbl",
                {**_BV, "bvlS": "Embs", "bvlT": "PrBL", "blur": 27.0},
                (19, 19, 17, 17),
            ),
            (
                "ebbl",
                {**_BV, "bvlS": "OtrB", "bvlT": "SfBL", "blur": 0.0},
                (3, 3, 1, 1),
            ),
            (
                "ebbl",
                {**_BV, "bvlS": "OtrB", "bvlT": "SfBL", "blur": 9.0, "Sftn": 5.0},
                (15, 15, 15, 15),
            ),
            (
                "ebbl",
                {**_BV, "bvlS": "Embs", "bvlT": "SfBL", "blur": 9.0, "useShape": False},
                (6, 6, 6, 6),
            ),
        ],
    )
    def test_style_pads_match_ae(self, key: str, instance: dict, pads: tuple) -> None:
        left, top, right, bottom = pads
        box = _instance_box(key, instance, (0, 0, 24, 25), 120.0, "Layer 1")
        assert box == (-left, -top, 24 + right, 25 + bottom)

    @pytest.mark.parametrize(
        ("key", "instance"),
        [
            ("FrFX", {"enab": True, "Styl": "InsF", "Sz  ": 6.0}),
            ("ebbl", {**_BV, "bvlS": "InrB", "bvlT": "SfBL", "blur": 9.0, "Sftn": 5.0}),
            ("IrSh", {"enab": True, "blur": 21.0, "Dstn": 10.0}),
            ("ChFX", {"enab": True, "blur": 101.0, "Dstn": 69.0}),
        ],
    )
    def test_styles_inside_the_layer_do_not_grow_it(
        self, key: str, instance: dict
    ) -> None:
        assert _instance_box(key, instance, (0, 0, 24, 25), 120.0, "Layer 1") is None

    def test_global_light_moves_the_shadow(self) -> None:
        instance = {**_DS, "blur": 10.0, "Dstn": 11.0, "uglg": True, "lagl": 0.0}
        box = _instance_box("DrSh", instance, (0, 0, 24, 25), 90.0, "Layer 1")
        assert box == (-12, -1, 36, 48)  # straight down, as the 90 degree global light

    def test_stroke_emboss_is_refused(self) -> None:
        instance = {**_BV, "bvlS": "strokeEmboss", "bvlT": "SfBL", "blur": 9.0}
        with pytest.raises(NotImplementedError, match="strokeEmboss"):
            _instance_box("ebbl", instance, (0, 0, 24, 25), 120.0, "Layer 1")

    def test_sample_document_matches_ae(self) -> None:
        # Every style of the sample at once: AE's merged box (-45, -45, 69, 70)
        # (samples/models/import/psd_layer_styles.aep).
        angle = read_global_light(STYLED)[0]
        for name in ("Layer 1", "Layer 1 copy"):
            assert merged_styles_bounds(_leaves(STYLED)[name], angle) == (
                -45,
                -45,
                69,
                70,
            )

    def test_style_less_layer_keeps_its_bounds(self) -> None:
        leaf = _leaves(ASSETS / "choose_layer.psd")["solo"]
        assert merged_styles_bounds(leaf, 120.0) == leaf.bounds
