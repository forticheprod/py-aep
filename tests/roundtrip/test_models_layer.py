"""Tests for Layer model parsing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from helpers import (
    get_comp,
    get_first_layer,
    get_layer,
    parse_project_fresh,
)

import py_aep
from py_aep import parse as parse_aep
from py_aep.enums import (
    AutoOrientType,
    BlendingMode,
    FrameBlendingType,
    Label,
    LayerQuality,
    LayerSamplingQuality,
    LightType,
    TrackMatteType,
)
from py_aep.models.layers import (
    AVLayer,
    Layer,
    LightLayer,
    ShapeLayer,
    TextLayer,
)
from py_aep.models.layers.three_d_model_layer import ThreeDModelLayer

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"


def _tdpi_by_param_suffix(layer: Layer) -> dict[str, list[int]]:
    """Collect tdpi values in a layer block, keyed by the owning param's
    tdmn suffix (`-0000` internal vs `-0001` value param)."""
    from py_aep.binary.chunk import ListChunk

    result: dict[str, list[int]] = {}

    def walk(lst: ListChunk) -> None:
        chunks = lst.chunks
        for i, c in enumerate(chunks):
            if c.chunk_type == "tdmn" and i + 1 < len(chunks):
                body = chunks[i + 1]
                if isinstance(body, ListChunk):
                    for inner in body.chunks:
                        if inner.chunk_type == "tdpi":
                            result.setdefault(c.value[-5:], []).append(inner.value)
            if isinstance(c, ListChunk):
                walk(c)

    walk(layer._layer_list)
    return result


class TestLightSource:
    """Tests for LightLayer.light_source."""

    def test_light_source_default_is_none(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "light_source_default.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, LightLayer)
        assert layer.light_source is None

    def test_light_source_mov(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "light_source_mov_23_976.mov.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, LightLayer)
        assert layer.light_source is not None
        assert isinstance(layer.light_source, AVLayer)
        assert layer.light_source.name == "mov_23_976.mov"

    def test_light_source_set_none(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "light_source_mov_23_976.mov.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, LightLayer)
        assert layer.light_source is not None

        layer.light_source = None
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_first_layer(parse_aep(out).project)
        assert isinstance(layer2, LightLayer)
        assert layer2.light_source is None

    def test_light_source_rejects_3d_layer(self) -> None:
        project = parse_aep(SAMPLES_DIR / "light_source_mov_23_976.mov.aep").project
        light = project.compositions[0].light_layers[0]
        assert isinstance(light, LightLayer)
        source = light.light_source
        assert isinstance(source, AVLayer)

        source.three_d_layer = True
        with pytest.raises(ValueError, match="Invalid light source specified"):
            light.light_source = source


class TestRoundtripLightType:
    """Roundtrip tests for LightLayer.light_type."""

    def test_modify_light_type_to_spot(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_AMBIENT")
        assert isinstance(layer, LightLayer)
        assert layer.light_type == LightType.AMBIENT

        layer.light_type = LightType.SPOT
        out = tmp_path / "modified_light_type.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "lightType_AMBIENT")
        assert isinstance(layer2, LightLayer)
        assert layer2.light_type == LightType.SPOT

    def test_modify_light_type_to_point(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_SPOT")
        assert isinstance(layer, LightLayer)
        assert layer.light_type == LightType.SPOT

        layer.light_type = LightType.POINT
        out = tmp_path / "modified_light_type_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "lightType_SPOT")
        assert isinstance(layer2, LightLayer)
        assert layer2.light_type == LightType.POINT

    def test_modify_light_type_to_parallel(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_POINT")
        assert isinstance(layer, LightLayer)
        assert layer.light_type == LightType.POINT

        layer.light_type = LightType.PARALLEL
        out = tmp_path / "modified_light_type_parallel.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "lightType_POINT")
        assert isinstance(layer2, LightLayer)
        assert layer2.light_type == LightType.PARALLEL

    def test_light_type_validation_rejects_invalid(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_AMBIENT")
        assert isinstance(layer, LightLayer)
        with pytest.raises(ValueError, match="Invalid value"):
            layer.light_type = 9999  # type: ignore[assignment]


class TestRoundtripLayerFlags:
    """Roundtrip tests for Layer chunk-backed boolean flags."""

    def test_modify_locked(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "locked_true")
        assert layer.locked is True

        layer.locked = False
        out = tmp_path / "modified_locked.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "locked_true")
        assert layer2.locked is False

    def test_modify_shy(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "shy_true")
        assert layer.shy is True

        layer.shy = False
        out = tmp_path / "modified_shy.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "shy_true")
        assert layer2.shy is False

    def test_modify_solo(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "solo_true")
        assert layer.solo is True

        layer.solo = False
        out = tmp_path / "modified_solo.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "solo_true")
        assert layer2.solo is False


class TestRoundtripAVLayerFlags:
    """Roundtrip tests for AVLayer chunk-backed flags."""

    def test_modify_blending_mode(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "blendingMode.aep")
        layer = get_layer(project, "blendingMode_ADD")
        assert isinstance(layer, AVLayer)
        assert layer.blending_mode == BlendingMode.ADD

        layer.blending_mode = BlendingMode.MULTIPLY
        out = tmp_path / "modified_blending.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "blendingMode_ADD")
        assert isinstance(layer2, AVLayer)
        assert layer2.blending_mode == BlendingMode.MULTIPLY

    def test_dancing_dissolve_roundtrip(self, tmp_path: Path) -> None:
        # Dancing Dissolve has no transfer-mode value of its own - AE stores it
        # as Dissolve plus a flag bit in the ldta. Round-tripping exercises both
        # the write (set the bit) and read (recover DANCING_DISSOLVE) paths.
        project = parse_project_fresh(SAMPLES_DIR / "blendingMode.aep")
        layer = get_layer(project, "blendingMode_ADD")
        assert isinstance(layer, AVLayer)

        layer.blending_mode = BlendingMode.DANCING_DISSOLVE
        out = tmp_path / "dancing.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "blendingMode_ADD")
        assert isinstance(layer2, AVLayer)
        assert layer2.blending_mode == BlendingMode.DANCING_DISSOLVE

    def test_dancing_dissolve_independent_of_preserve_transparency(
        self, tmp_path: Path
    ) -> None:
        # The dancing flag and preserve-underlying-transparency share one ldta
        # byte (bits 1 and 0). Setting one must not disturb the other.
        project = parse_project_fresh(SAMPLES_DIR / "blendingMode.aep")
        layer = get_layer(project, "blendingMode_ADD")
        assert isinstance(layer, AVLayer)
        layer.blending_mode = BlendingMode.DANCING_DISSOLVE
        layer.preserve_transparency = True
        out = tmp_path / "dancing_pt.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "blendingMode_ADD")
        assert layer2.blending_mode == BlendingMode.DANCING_DISSOLVE
        assert layer2.preserve_transparency is True
        # Switching to a non-Dissolve mode clears only the dancing flag.
        layer2.blending_mode = BlendingMode.NORMAL
        assert layer2.preserve_transparency is True

    def test_modify_three_d_layer(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "threeDLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.three_d_layer is True

        layer.three_d_layer = False
        out = tmp_path / "modified_3d.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "threeDLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.three_d_layer is False

    def test_environment_layer_sets_three_d_layer(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "threeDLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.environment_layer is False

        layer.environment_layer = True
        assert layer.three_d_layer is True

        out = tmp_path / "modified_env.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "threeDLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.environment_layer is True
        assert layer2.three_d_layer is True

    def test_three_d_layer_clears_environment_layer(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "threeDLayer_true")
        assert isinstance(layer, AVLayer)

        layer.environment_layer = True
        assert layer.environment_layer is True

        layer.three_d_layer = True
        assert layer.environment_layer is False

        out = tmp_path / "modified_3d_env.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "threeDLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.three_d_layer is True
        assert layer2.environment_layer is False


class TestRoundtripAutoOrient:
    """Roundtrip tests for Layer.auto_orient."""

    def test_modify_along_path_to_no_auto_orient(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "autoOrient.aep")
        layer = get_layer(project, "autoOrient_ALONG_PATH")
        assert layer.auto_orient == AutoOrientType.ALONG_PATH

        layer.auto_orient = AutoOrientType.NO_AUTO_ORIENT
        out = tmp_path / "modified_auto_orient.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "autoOrient_ALONG_PATH")
        assert layer2.auto_orient == AutoOrientType.NO_AUTO_ORIENT

    def test_modify_no_auto_orient_to_along_path(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        assert layer.auto_orient == AutoOrientType.NO_AUTO_ORIENT

        layer.auto_orient = AutoOrientType.ALONG_PATH
        out = tmp_path / "modified_auto_orient.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.auto_orient == AutoOrientType.ALONG_PATH


class TestRoundtripComment:
    """Roundtrip tests for Layer.comment."""

    def test_modify_comment(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "comment")
        assert layer.comment != ""

        layer.comment = "modified comment"
        out = tmp_path / "modified_comment.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "comment")
        assert layer2.comment == "modified comment"


class TestRoundtripInOutPoint:
    """Roundtrip tests for Layer.in_point and Layer.out_point."""

    def test_modify_in_point(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        original_in = layer.in_point

        new_in = original_in + 1.0
        layer.in_point = new_in
        out = tmp_path / "modified_in_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert abs(layer2.in_point - new_in) < 0.001

    def test_modify_out_point(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        original_out = layer.out_point

        new_out = original_out - 1.0
        layer.out_point = new_out
        out = tmp_path / "modified_out_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert abs(layer2.out_point - new_out) < 0.001


class TestRoundtripCommentCreate:
    """Roundtrip tests for Layer.comment when cmta chunk is absent."""

    def test_create_comment_from_empty(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        assert layer.comment == ""

        layer.comment = "new comment"
        out = tmp_path / "created_comment.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.comment == "new comment"


class TestRoundtripFramePoints:
    """Roundtrip tests for frame_in_point, frame_out_point, frame_start_time."""

    def test_modify_frame_in_point(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")

        layer.frame_in_point = 10
        out = tmp_path / "modified_frame_in_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.frame_in_point == 10

    def test_modify_frame_out_point(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")

        layer.frame_out_point = 20
        out = tmp_path / "modified_frame_out_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.frame_out_point == 20

    def test_modify_frame_start_time(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")

        layer.frame_start_time = 5
        out = tmp_path / "modified_frame_start_time.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.frame_start_time == 5


class TestRoundtripFrameBlendingType:
    """Roundtrip tests for AVLayer.frame_blending_type."""

    def test_no_blend_to_frame_mix(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "frameBlendingType.aep")
        layer = get_layer(project, "frameBlendingType_NO_FRAME_BLEND")
        assert layer.frame_blending_type == FrameBlendingType.NO_FRAME_BLEND
        assert layer.frame_blending is False

        layer.frame_blending_type = FrameBlendingType.FRAME_MIX
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "frameBlendingType_NO_FRAME_BLEND")
        assert layer2.frame_blending_type == FrameBlendingType.FRAME_MIX
        assert layer2.frame_blending is True

    def test_frame_mix_to_pixel_motion(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "frameBlendingType.aep")
        layer = get_layer(project, "frameBlendingType_FRAME_MIX")
        assert layer.frame_blending_type == FrameBlendingType.FRAME_MIX

        layer.frame_blending_type = FrameBlendingType.PIXEL_MOTION
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "frameBlendingType_FRAME_MIX")
        assert layer2.frame_blending_type == FrameBlendingType.PIXEL_MOTION

    def test_pixel_motion_to_no_blend(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "frameBlendingType.aep")
        layer = get_layer(project, "frameBlendingType_PIXEL_MOTION")
        assert layer.frame_blending_type == FrameBlendingType.PIXEL_MOTION

        layer.frame_blending_type = FrameBlendingType.NO_FRAME_BLEND
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "frameBlendingType_PIXEL_MOTION")
        assert layer2.frame_blending_type == FrameBlendingType.NO_FRAME_BLEND
        assert layer2.frame_blending is False


class TestRoundtripTimeRemapEnabled:
    """Roundtrip tests for AVLayer.time_remap_enabled."""

    def test_disable_time_remap(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "outPoint_no_clamp.aep")
        layer = get_layer(project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer, AVLayer)
        assert layer.time_remap_enabled is True

        layer.time_remap_enabled = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer2, AVLayer)
        assert layer2.time_remap_enabled is False

    def test_enable_time_remap(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "outPoint_no_clamp.aep")
        layer = get_layer(project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer, AVLayer)

        layer.time_remap_enabled = False
        out = tmp_path / "disabled.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = get_layer(project2, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer2, AVLayer)
        assert layer2.time_remap_enabled is False

        layer2.time_remap_enabled = True
        out2 = tmp_path / "re_enabled.aep"
        project2.save(out2)
        layer3 = get_layer(parse_aep(out2).project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer3, AVLayer)
        assert layer3.time_remap_enabled is True


class TestRoundtripLayerEnabled:
    """Roundtrip tests for Layer.enabled."""

    def test_modify_enabled(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "enabled_false")
        assert layer.enabled is False

        layer.enabled = True
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "enabled_false")
        assert layer2.enabled is True


class TestRoundtripLayerLabel:
    """Roundtrip tests for Layer.label."""

    def test_modify_label(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "label_3")
        assert layer.label == Label.AQUA

        layer.label = Label.RED
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "label_3")
        assert layer2.label == Label.RED


class TestRoundtripLayerStretch:
    """Roundtrip tests for Layer.stretch."""

    def test_modify_stretch(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_timing.aep")
        layer = get_layer(project, "stretch_200")
        assert math.isclose(layer.stretch, 200.0)

        layer.stretch = 150.0
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "stretch_200")
        assert math.isclose(layer2.stretch, 150.0)


class TestRoundtripAVLayerBoolFlags:
    """Roundtrip tests for remaining AVLayer boolean flags."""

    def test_modify_adjustment_layer(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "adjustmentLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.adjustment_layer is True

        layer.adjustment_layer = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "adjustmentLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.adjustment_layer is False

    def test_modify_audio_enabled(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_false")
        assert isinstance(layer, AVLayer)
        assert layer.audio_enabled is False

        layer.audio_enabled = True
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "audioEnabled_false")
        assert isinstance(layer2, AVLayer)
        assert layer2.audio_enabled is True

    def test_modify_collapse_transformation(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "collapseTransformation_true")
        assert isinstance(layer, AVLayer)
        assert layer.collapse_transformation is True

        layer.collapse_transformation = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "collapseTransformation_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.collapse_transformation is False

    def test_modify_effects_active(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "effectsActive_false")
        assert isinstance(layer, AVLayer)
        assert layer.effects_active is False

        layer.effects_active = True
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "effectsActive_false")
        assert isinstance(layer2, AVLayer)
        assert layer2.effects_active is True

    def test_modify_guide_layer(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "guideLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.guide_layer is True

        layer.guide_layer = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "guideLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.guide_layer is False

    def test_modify_motion_blur(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "motionBlur_true")
        assert isinstance(layer, AVLayer)
        assert layer.motion_blur is True

        layer.motion_blur = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "motionBlur_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.motion_blur is False

    def test_modify_preserve_transparency(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "preserveTransparency_true")
        assert isinstance(layer, AVLayer)
        assert layer.preserve_transparency is True

        layer.preserve_transparency = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "preserveTransparency_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.preserve_transparency is False


class TestRoundtripAVLayerQuality:
    """Roundtrip tests for AVLayer.quality and sampling_quality."""

    def test_modify_quality(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "quality.aep")
        layer = get_layer(project, "quality_BEST")
        assert isinstance(layer, AVLayer)
        assert layer.quality == LayerQuality.BEST

        layer.quality = LayerQuality.DRAFT
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "quality_BEST")
        assert isinstance(layer2, AVLayer)
        assert layer2.quality == LayerQuality.DRAFT

    def test_modify_sampling_quality(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "samplingQuality_BICUBIC")
        assert isinstance(layer, AVLayer)
        assert layer.sampling_quality == LayerSamplingQuality.BICUBIC

        layer.sampling_quality = LayerSamplingQuality.BILINEAR
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "samplingQuality_BICUBIC")
        assert isinstance(layer2, AVLayer)
        assert layer2.sampling_quality == LayerSamplingQuality.BILINEAR


class TestRoundtripThreeDPerChar:
    """Roundtrip tests for AVLayer.three_d_per_char."""

    def test_modify_three_d_per_char(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "threeDPerChar_on.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, AVLayer)
        assert layer.three_d_per_char is True

        layer.three_d_per_char = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_first_layer(parse_aep(out).project)
        assert isinstance(layer2, AVLayer)
        assert layer2.three_d_per_char is False


class TestRoundtripTrackMatteType:
    """Roundtrip tests for AVLayer.track_matte_type."""

    def test_modify_track_matte_type(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "trackMatteType.aep")
        comp = get_comp(project, "trackMatteType_ALPHA")
        # Track matte layer is the one with ALPHA matte
        matte_layer = None
        for layer in comp.layers:
            if (
                isinstance(layer, AVLayer)
                and layer.track_matte_type == TrackMatteType.ALPHA
            ):
                matte_layer = layer
                break
        assert matte_layer is not None

        matte_layer.track_matte_type = TrackMatteType.LUMA
        out = tmp_path / "modified.aep"
        project.save(out)

        comp2 = get_comp(parse_aep(out).project, "trackMatteType_ALPHA")
        matte_layer2 = None
        for layer in comp2.layers:
            if (
                isinstance(layer, AVLayer)
                and layer.track_matte_type == TrackMatteType.LUMA
            ):
                matte_layer2 = layer
                break
        assert matte_layer2 is not None


class TestRoundtripLayerName:
    """Roundtrip: modify Layer.name and verify save/reload."""

    def test_modify_layer_name(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "name_renamed")
        assert layer.name == "RenamedLayer"

        layer.name = "NewName"
        out = tmp_path / "modified_name.aep"
        project.save(out)

        layer2 = get_layer(parse_project_fresh(out), "name_renamed")
        assert layer2.name == "NewName"

    def test_set_name_on_source_layer(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "comment")
        assert not layer.is_name_set

        layer.name = "CustomName"
        out = tmp_path / "set_name.aep"
        project.save(out)

        layer2 = get_layer(parse_project_fresh(out), "comment")
        assert layer2.name == "CustomName"
        assert layer2.is_name_set


class TestSetTrackMatte:
    """Tests for AVLayer.set_track_matte()."""

    def test_basic(self) -> None:
        """Assign ALPHA track matte on a file that has none."""
        app = parse_aep(SAMPLES_DIR / "track_matte_no.aep")
        comp = app.project.compositions[0]
        matted, matte = comp.layers[0], comp.layers[1]

        matted.set_track_matte(matte, TrackMatteType.ALPHA)

        assert matted.track_matte_type == TrackMatteType.ALPHA
        assert matted._matte_layer_id == matte.id
        assert matted.track_matte_layer is matte
        assert not matte.enabled

    def test_roundtrip(self, tmp_path: Path) -> None:
        """Set matte, save, reparse, verify persisted."""
        app = parse_aep(SAMPLES_DIR / "track_matte_no.aep")
        comp = app.project.compositions[0]
        matted, matte = comp.layers[0], comp.layers[1]

        matted.set_track_matte(matte, TrackMatteType.LUMA)
        app.project.save(tmp_path / "out.aep")

        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]
        matted2 = comp2.layers[0]
        matte2 = comp2.layers[1]

        assert matted2.track_matte_type == TrackMatteType.LUMA
        assert matted2._matte_layer_id == matte2.id
        assert not matte2.enabled

    def test_replaces_existing(self) -> None:
        """Switching matte re-enables the old matte layer."""
        app = parse_aep(SAMPLES_DIR / "trackMatteType.aep")
        comp = get_comp(app.project, "trackMatteType_ALPHA")
        matted = comp.layers[0]
        old_matte = comp.layers[1]
        assert not old_matte.enabled

        # Switch to LUMA with the same matte layer (type changes only)
        matted.set_track_matte(old_matte, TrackMatteType.LUMA)
        assert matted.track_matte_type == TrackMatteType.LUMA
        # Matte stays disabled since it's still the matte
        assert not old_matte.enabled

    def test_none_clears_ref(self) -> None:
        """Passing None clears matte_layer_id but preserves the type."""
        app = parse_aep(SAMPLES_DIR / "track_matte_yes.aep")
        comp = app.project.compositions[0]
        matted = comp.layers[0]
        matte = comp.layers[1]
        assert not matte.enabled

        matted.set_track_matte(None, TrackMatteType.ALPHA)

        assert matted.track_matte_type == TrackMatteType.ALPHA
        assert matted._matte_layer_id == 0
        assert matted.track_matte_layer is None
        # Old matte re-enabled
        assert matte.enabled

    def test_noop_with_no_track_matte(self) -> None:
        """NO_TRACK_MATTE + non-None layer is a no-op."""
        app = parse_aep(SAMPLES_DIR / "track_matte_no.aep")
        comp = app.project.compositions[0]
        matted, matte = comp.layers[0], comp.layers[1]
        original_type = matted.track_matte_type

        matted.set_track_matte(matte, TrackMatteType.NO_TRACK_MATTE)

        assert matted.track_matte_type == original_type
        assert matted._matte_layer_id == 0
        assert matte.enabled

    def test_pre_ae23_raises(self) -> None:
        """Files older than AE 23 don't have matte_layer_id."""
        app = parse_aep(VERSIONS_DIR / "ae2022" / "complete.aep")
        comp = app.project.compositions[0]
        layer = comp.layers[0]

        with pytest.raises(AttributeError, match="AE 23"):
            layer.set_track_matte(layer, TrackMatteType.ALPHA)

    def test_wrong_comp_raises(self) -> None:
        """Matte layer from a different comp raises ValueError."""
        app = parse_aep(SAMPLES_DIR / "trackMatteType.aep")
        comp_a = get_comp(app.project, "trackMatteType_ALPHA")
        comp_l = get_comp(app.project, "trackMatteType_LUMA")
        matted = comp_a.layers[0]
        foreign = comp_l.layers[1]

        with pytest.raises(ValueError, match="same composition"):
            matted.set_track_matte(foreign, TrackMatteType.ALPHA)


class TestRemoveTrackMatte:
    """Tests for AVLayer.remove_track_matte()."""

    def test_basic(self) -> None:
        """Remove matte reference and re-enable the matte layer."""
        app = parse_aep(SAMPLES_DIR / "track_matte_yes.aep")
        comp = app.project.compositions[0]
        matted = comp.layers[0]
        matte = comp.layers[1]
        assert not matte.enabled

        matted.remove_track_matte()

        assert matted._matte_layer_id == 0
        assert matted.track_matte_layer is None
        assert matte.enabled

    def test_preserves_type(self) -> None:
        """track_matte_type stays after removing the matte."""
        app = parse_aep(SAMPLES_DIR / "track_matte_yes.aep")
        comp = app.project.compositions[0]
        matted = comp.layers[0]
        assert matted.track_matte_type == TrackMatteType.ALPHA

        matted.remove_track_matte()

        assert matted.track_matte_type == TrackMatteType.ALPHA

    def test_roundtrip(self, tmp_path: Path) -> None:
        """Remove matte, save, reparse."""
        app = parse_aep(SAMPLES_DIR / "track_matte_yes.aep")
        comp = app.project.compositions[0]
        comp.layers[0].remove_track_matte()
        app.project.save(tmp_path / "out.aep")

        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]
        assert comp2.layers[0]._matte_layer_id == 0
        assert comp2.layers[1].enabled

    def test_pre_ae23_raises(self) -> None:
        """Files older than AE 23 raise AttributeError."""
        app = parse_aep(VERSIONS_DIR / "ae2022" / "complete.aep")
        comp = app.project.compositions[0]
        with pytest.raises(AttributeError, match="AE 23"):
            comp.layers[0].remove_track_matte()


class TestReplaceSource:
    """Tests for AVLayer.replace_source()."""

    def test_basic(self) -> None:
        """Swap source and verify the new source is returned."""
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comp = get_comp(app.project, "Main_Comp")
        layer = comp.layers[0]  # first AVLayer
        old_source = layer.source
        # Pick any other footage item as new source
        new_source = next(
            item for item in app.project.footages if item is not old_source
        )

        layer.replace_source(new_source)

        assert layer.source is new_source
        assert layer._source_id == new_source.id

    def test_roundtrip(self, tmp_path: Path) -> None:
        """Replace source, save, reparse, verify."""
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comp = get_comp(app.project, "Main_Comp")
        layer = comp.layers[0]
        new_source = next(
            item for item in app.project.footages if item is not layer.source
        )
        new_id = new_source.id

        layer.replace_source(new_source)
        app.project.save(tmp_path / "out.aep")

        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = get_comp(app2.project, "Main_Comp")
        assert comp2.layers[0]._source_id == new_id

    def test_updates_used_in(self) -> None:
        """_used_in back-references are updated."""
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comp = get_comp(app.project, "Main_Comp")
        layer = comp.layers[0]
        old_source = layer.source
        new_source = next(
            item
            for item in app.project.footages
            if item is not old_source and hasattr(item, "_used_in")
        )

        layer.replace_source(new_source)

        assert comp in new_source._used_in
        # old_source removed if no other layer in comp uses it
        still_used = any(
            ly._source_id == old_source.id
            for ly in comp.layers
            if hasattr(ly, "_source_id") and ly is not layer
        )
        if not still_used:
            assert comp not in old_source._used_in

    def test_fix_expressions_raises(self) -> None:
        """fix_expressions=True raises NotImplementedError."""
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comp = get_comp(app.project, "Main_Comp")
        layer = comp.layers[0]
        source = next(iter(app.project.footages))

        with pytest.raises(NotImplementedError, match="fix_expressions"):
            layer.replace_source(source, fix_expressions=True)

    def test_not_in_project_raises(self) -> None:
        """Source not in project.items raises ValueError."""
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comp = get_comp(app.project, "Main_Comp")
        layer = comp.layers[0]

        class _FakeItem:
            id = 999999
            name = "ghost"

        with pytest.raises(ValueError, match="must be an AVItem"):
            layer.replace_source(_FakeItem())  # type: ignore[arg-type]

    def test_sourceless_layer_raises(self) -> None:
        """Shape/text layers (source=None) cannot have their source replaced."""
        project = parse_project_fresh(SAMPLES_DIR / "type.aep")
        layer = get_layer(project, "type_shape")
        assert isinstance(layer, ShapeLayer)
        assert layer.source is None

        with pytest.raises(ValueError, match="does not have a source"):
            layer.replace_source(project.footages[0])

    def test_3d_model_layer_raises(self) -> None:
        """ThreeDModelLayer cannot have its source replaced."""
        project = parse_project_fresh(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, ThreeDModelLayer)

        with pytest.raises(ValueError, match="3D model layers"):
            layer.replace_source(layer.source)

    def test_direct_cycle_raises(self) -> None:
        """Replacing a layer's source with its own comp raises ValueError."""
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comp = get_comp(app.project, "Main_Comp")
        layer = comp.layers[0]

        with pytest.raises(ValueError, match="composition cycle"):
            layer.replace_source(comp)

    def test_deep_cycle_raises(self) -> None:
        """Cycle detection catches indirect chains (A > B > A)."""
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comp = get_comp(app.project, "Main_Comp")
        # Find a sub-comp used as a source by a layer in Main_Comp
        sub_comp = None
        for layer in comp.av_layers:
            src = layer.source
            if src is not None and hasattr(src, "layers") and src is not comp:
                sub_comp = src
                break
        if sub_comp is None:
            pytest.skip("No nested comp layer in Main_Comp")
        # Find a layer in sub_comp that has a source (not text/shape)
        sub_layer = None
        for ly in sub_comp.av_layers:
            if ly.source is not None:
                sub_layer = ly
                break
        if sub_layer is None:
            pytest.skip("No sourced layer in sub-comp")
        # sub_comp is used inside Main_Comp, so setting a layer
        # in sub_comp to point at Main_Comp would create A > B > A.
        with pytest.raises(ValueError, match="composition cycle"):
            sub_layer.replace_source(comp)


class TestLayerRemove:
    """Tests for Layer.remove()."""

    def test_remove_decreases_count(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        assert len(comp.layers) == 3
        comp.layers[2].remove()
        assert len(comp.layers) == 2

    def test_remove_cleans_parent_refs(self) -> None:
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]  # ChildLayer, parent_id=57
        assert child._parent_id == 57
        comp.layers[1].remove()  # Remove ParentNull (id=57)
        assert child._parent_id == 0

    def test_remove_cleans_matte_refs(self) -> None:
        app = parse_aep(SAMPLES_DIR / "track_matte_yes.aep")
        comp = app.project.compositions[0]
        matted = comp.layers[0]  # Gray Solid 2, matte_layer_id=15
        assert matted._ldta.matte_layer_id == 15
        comp.layers[1].remove()  # Remove matte source (id=15)
        assert matted._ldta.matte_layer_id == 0

    def test_remove_invalidates_cache(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        last_id = comp.layers[-1].id
        _ = comp.layers_by_id  # Build cache
        assert last_id in comp.layers_by_id
        comp.layers[-1].remove()
        assert last_id not in comp.layers_by_id

    def test_remove_all_layers(self) -> None:
        app = parse_aep(SAMPLES_DIR / "track_matte_no.aep")
        comp = app.project.compositions[0]
        n = len(comp.layers)
        for _ in range(n):
            comp.layers[0].remove()
        assert len(comp.layers) == 0

    def test_remove_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        removed_id = comp.layers[-1].id
        comp.layers[-1].remove()
        app.project.save(tmp_path / "out.aep")

        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = get_comp(app2.project, "crystal")
        assert len(comp2.layers) == 2
        assert removed_id not in [ly.id for ly in comp2.layers]

    def test_remove_parent_roundtrip(self, tmp_path: Path) -> None:
        """Remove a parent layer, save, reparse: child is unparented."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        comp.layers[1].remove()  # Remove ParentNull (id=57)
        app.project.save(tmp_path / "out.aep")

        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = get_comp(app2.project, "parent")
        child = comp2.layers[0]
        assert child._parent_id == 0

    def test_remove_parent_preserves_world_position(self) -> None:
        """Removing parent recalculates child Position to world coords."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]  # ChildLayer
        parent = comp.layers[1]  # ParentNull
        assert child.parent is parent
        assert child.transform["ADBE Position"].value == [0.0, 0.0, 0.0]
        parent_pos = parent.transform["ADBE Position"].value

        parent.remove()

        # Child position should now be the parent's former position
        pos = child.transform["ADBE Position"].value
        assert abs(pos[0] - parent_pos[0]) < 0.01
        assert abs(pos[1] - parent_pos[1]) < 0.01
        assert abs(pos[2] - parent_pos[2]) < 0.01


class TestParentSetter:
    """Tests for Layer.parent setter with transform preservation."""

    def test_unparent_preserves_world_position(self) -> None:
        """Setting parent=None recalculates child transforms."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]  # ChildLayer
        parent = comp.layers[1]  # ParentNull
        assert child.parent is parent

        parent_pos = parent.transform["ADBE Position"].value
        child.parent = None

        pos = child.transform["ADBE Position"].value
        assert abs(pos[0] - parent_pos[0]) < 0.01
        assert abs(pos[1] - parent_pos[1]) < 0.01
        assert abs(pos[2] - parent_pos[2]) < 0.01

    def test_unparent_preserves_scale(self) -> None:
        """Scale stays [100,100,100] when parent has identity scale."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]
        child.parent = None
        assert child.transform["ADBE Scale"].value == [100.0, 100.0, 100.0]

    def test_unparent_preserves_rotation(self) -> None:
        """Rotation stays 0 when parent has identity rotation."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]
        child.parent = None
        assert abs(child.transform["ADBE Rotate Z"].value) < 0.01

    def test_same_parent_noop(self) -> None:
        """Setting same parent is a no-op."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]
        parent = comp.layers[1]
        child.parent = parent  # Same parent, no-op
        assert child.transform["ADBE Position"].value == [0.0, 0.0, 0.0]

    def test_reparent_to_new_parent(self) -> None:
        """Reparenting from one parent to another preserves world pos."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]  # ChildLayer parented to ParentNull
        parent = comp.layers[1]  # ParentNull at [50, 50, 0]

        # World position of child is parent pos + child local pos
        # = [50, 50, 0] + [0, 0, 0] = [50, 50, 0]

        # Unparent first, then parent to the same layer (round-trip)
        child.parent = None

        # Re-parent back: child local should become [0,0,0] again
        child.parent = parent
        pos_local = child.transform["ADBE Position"].value
        assert abs(pos_local[0]) < 0.01
        assert abs(pos_local[1]) < 0.01
        assert abs(pos_local[2]) < 0.01

    def test_unparent_roundtrip(self, tmp_path: Path) -> None:
        """Unparent, save, reparse: transforms survive round-trip."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]
        parent = comp.layers[1]
        parent_pos = parent.transform["ADBE Position"].value[:]

        child.parent = None
        app.project.save(tmp_path / "out.aep")

        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = get_comp(app2.project, "parent")
        child2 = comp2.layers[0]
        assert child2._parent_id == 0
        pos = child2.transform["ADBE Position"].value
        assert abs(pos[0] - parent_pos[0]) < 0.01
        assert abs(pos[1] - parent_pos[1]) < 0.01


class TestLayerMove:
    """Tests for Layer.move_to_beginning/end/after/before."""

    def test_move_to_end(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        first = comp.layers[0]
        first_id = first.id
        first.move_to_end()
        assert comp.layers[-1] is first
        assert comp.layers[-1].id == first_id

    def test_move_to_beginning(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        last = comp.layers[-1]
        last_id = last.id
        last.move_to_beginning()
        assert comp.layers[0] is last
        assert comp.layers[0].id == last_id

    def test_move_after(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        ids_before = [ly.id for ly in comp.layers]
        first = comp.layers[0]
        target = comp.layers[2]
        first.move_after(target)
        # [0] moved after [2]: new order is [1, 2, 0]
        assert comp.layers[0].id == ids_before[1]
        assert comp.layers[1].id == ids_before[2]
        assert comp.layers[2].id == ids_before[0]

    def test_move_before(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        ids_before = [ly.id for ly in comp.layers]
        last = comp.layers[2]
        target = comp.layers[0]
        last.move_before(target)
        # [2] moved before [0]: new order is [2, 0, 1]
        assert comp.layers[0].id == ids_before[2]
        assert comp.layers[1].id == ids_before[0]
        assert comp.layers[2].id == ids_before[1]

    def test_move_preserves_parent(self) -> None:
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]  # ChildLayer, parent_id=57
        parent = comp.layers[1]  # ParentNull, id=57
        parent.move_to_beginning()
        assert child._parent_id == 57

    def test_move_preserves_matte(self) -> None:
        app = parse_aep(SAMPLES_DIR / "track_matte_yes.aep")
        comp = app.project.compositions[0]
        matted = comp.layers[0]  # Gray Solid 2, matte_layer_id=15
        comp.layers[1].move_to_beginning()  # Move matte source
        assert matted._ldta.matte_layer_id == 15

    def test_move_same_position(self) -> None:
        """Moving to current position is a no-op."""
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        ids_before = [ly.id for ly in comp.layers]
        comp.layers[1].move_before(comp.layers[1])
        assert [ly.id for ly in comp.layers] == ids_before

    def test_move_wrong_comp_raises(self) -> None:
        app = parse_aep(VERSIONS_DIR / "ae2025" / "complete.aep")
        comps = app.project.compositions
        if len(comps) < 2:
            pytest.skip("Need at least 2 comps")
        layer_a = comps[0].layers[0]
        layer_b = comps[1].layers[0]
        with pytest.raises(ValueError, match="same composition"):
            layer_a.move_after(layer_b)

    def test_move_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        names_before = [ly.name for ly in comp.layers]
        comp.layers[0].move_to_end()
        expected = names_before[1:] + [names_before[0]]
        assert [ly.name for ly in comp.layers] == expected

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = get_comp(app2.project, "crystal")
        assert [ly.name for ly in comp2.layers] == expected

    def test_move_updates_index(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        layer = comp.layers[0]
        assert layer.index == 0
        layer.move_to_end()
        assert layer.index == 2


class TestSetParentWithJump:
    """Tests for Layer.set_parent_with_jump()."""

    def test_set_parent(self) -> None:
        """Setting parent via set_parent_with_jump writes the ID."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]  # ChildLayer

        # Unparent without transform compensation
        child.set_parent_with_jump(None)
        assert child._parent_id == 0
        assert child.parent is None
        # Local position should NOT change (no compensation)
        assert child.transform["ADBE Position"].value == [0.0, 0.0, 0.0]

    def test_set_parent_assigns_id(self) -> None:
        """set_parent_with_jump sets the parent ID directly."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]
        parent = comp.layers[1]
        child.set_parent_with_jump(None)
        child.set_parent_with_jump(parent)
        assert child._parent_id == parent.id
        assert child.parent is parent

    def test_roundtrip(self, tmp_path: Path) -> None:
        """set_parent_with_jump survives save/reparse."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]
        child.set_parent_with_jump(None)

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = get_comp(app2.project, "parent")
        assert comp2.layers[0]._parent_id == 0


class TestLayerDuplicate:
    """Tests for Layer.duplicate()."""

    def test_duplicate_increases_count(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        assert len(comp.layers) == 3
        comp.layers[0].duplicate()
        assert len(comp.layers) == 4

    def test_duplicate_returns_new_layer(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        original = comp.layers[0]
        dup = original.duplicate()
        assert dup is not original
        assert dup.id != original.id

    def test_duplicate_placed_before_original(self) -> None:
        """Duplicate appears above (before) the original."""
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        original = comp.layers[1]
        original_idx = original.index
        dup = original.duplicate()
        assert dup.index == original_idx
        assert original.index == original_idx + 1

    def test_duplicate_rewrites_owner_tdpi(self) -> None:
        """Effect internal (-0000) tdpi values point at the duplicate's
        new id, while layer-reference (-0001) values keep pointing at
        the originally referenced layer, as AE does."""
        app = parse_aep(
            Path(__file__).parent.parent.parent
            / "samples"
            / "models"
            / "property"
            / "2_gaussian.aep"
        )
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        # Layer Control references the containing layer by default.
        layer.effects.add_property("ADBE Layer Control")
        original_id = layer.id

        dup = layer.duplicate()
        orig_tdpi = _tdpi_by_param_suffix(layer)
        dup_tdpi = _tdpi_by_param_suffix(dup)
        assert set(orig_tdpi["-0000"]) == {original_id}
        assert orig_tdpi["-0001"] == [original_id]
        assert set(dup_tdpi["-0000"]) == {dup.id}
        assert dup_tdpi["-0001"] == [original_id]

    def test_duplicate_owner_tdpi_roundtrip(self, tmp_path: Path) -> None:
        """The rewritten tdpi values survive save/reload."""
        app = parse_aep(
            Path(__file__).parent.parent.parent
            / "samples"
            / "models"
            / "property"
            / "2_gaussian.aep"
        )
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        layer.effects.add_property("ADBE Layer Control")
        original_id = layer.id
        dup = layer.duplicate()
        dup_id = dup.id
        app.project.save(tmp_path / "out.aep")
        comp2 = parse_aep(tmp_path / "out.aep").project.compositions[0]
        dup2 = next(lyr for lyr in comp2.layers if lyr.id == dup_id)
        dup2_tdpi = _tdpi_by_param_suffix(dup2)
        assert set(dup2_tdpi["-0000"]) == {dup_id}
        assert dup2_tdpi["-0001"] == [original_id]

    def test_duplicate_preserves_name_from_source(self) -> None:
        """Source-derived names are not modified on duplicate."""
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        original = comp.layers[1]  # mov_23_976.mov - name from source
        assert not original.is_name_set
        dup = original.duplicate()
        assert dup.name == original.name

    def test_duplicate_increments_user_name(self) -> None:
        """User-defined names are incremented on duplicate."""
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        original = comp.layers[0]  # Environment Light 1 - user-defined
        assert original.is_name_set
        dup = original.duplicate()
        assert dup.name == "Environment Light 2"

    def test_duplicate_increments_name_no_number(self) -> None:
        """User-defined name without trailing number gets ' 2' appended."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        parent_null = comp.layers[1]  # ParentNull - user-defined
        assert parent_null.is_name_set
        dup = parent_null.duplicate()
        assert dup.name == "ParentNull 2"

    def test_duplicate_preserves_parent(self) -> None:
        """Duplicated layer keeps the same parent reference."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(app.project, "parent")
        child = comp.layers[0]  # ChildLayer, has parent
        assert child._parent_id != 0
        dup = child.duplicate()
        assert dup._parent_id == child._parent_id

    def test_duplicate_preserves_matte(self) -> None:
        """Duplicated layer keeps the track matte reference."""
        app = parse_aep(SAMPLES_DIR / "track_matte_yes.aep")
        comp = app.project.compositions[0]
        matted = comp.layers[0]  # has matte_layer_id
        assert matted._ldta.matte_layer_id != 0
        dup = matted.duplicate()
        assert dup._ldta.matte_layer_id == matted._ldta.matte_layer_id

    def test_duplicate_unique_id(self) -> None:
        """Each duplicate gets a unique layer ID."""
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        ids_before = {ly.id for ly in comp.layers}
        dup1 = comp.layers[0].duplicate()
        dup2 = comp.layers[0].duplicate()
        all_ids = {ly.id for ly in comp.layers}
        assert dup1.id not in ids_before
        assert dup2.id not in ids_before
        assert dup1.id != dup2.id
        assert len(all_ids) == len(comp.layers)

    def test_duplicate_invalidates_cache(self) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        _ = comp.layers_by_id  # Build cache
        dup = comp.layers[0].duplicate()
        assert dup.id in comp.layers_by_id

    def test_duplicate_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        dup = comp.layers[0].duplicate()
        dup_name = dup.name
        dup_id = dup.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = get_comp(app2.project, "crystal")
        assert len(comp2.layers) == 4
        assert comp2.layers[0].name == dup_name
        assert comp2.layers[0].id == dup_id


class TestDuplicateComplexValueLayers:
    """Regression: duplicate() re-parses cloned chunks; complex-value
    properties (text, masks, keyframed transforms) must cache during
    that re-parse instead of taking the user-write setter paths."""

    PROPERTY_DIR = (
        Path(__file__).parent.parent.parent / "samples" / "models" / "property"
    )
    EG_DIR = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "essential_graphics"
    )

    def test_duplicate_static_text_layer(self) -> None:
        app = parse_aep(self.EG_DIR / "text_source_text.aep")
        comp = get_comp(app.project, "primary")
        original = comp.layers[0]
        assert isinstance(original, TextLayer)
        dup = original.duplicate()
        src = original.text.property("ADBE Text Document").value
        dup_src = dup.text.property("ADBE Text Document").value
        assert dup_src.text == src.text

    def test_duplicate_masked_layer(self) -> None:
        app = parse_aep(self.PROPERTY_DIR / "shape_basic.aep")
        comp = get_comp(app.project, "shape_closed_oval")
        original = comp.layers[0]
        dup = original.duplicate()
        orig_shape = original.masks[0].property("ADBE Mask Shape").value
        dup_shape = dup.masks[0].property("ADBE Mask Shape").value
        assert dup_shape.vertices == orig_shape.vertices

    def test_duplicate_every_layer_kind(self) -> None:
        """All layers of the animated sample duplicate without error."""
        app = parse_aep(self.PROPERTY_DIR / "all_animated.aep")
        for comp in app.project.compositions:
            count = len(comp.layers)
            for layer in list(comp.layers):
                layer.duplicate()
            assert len(comp.layers) == 2 * count


class TestCopyToComp:
    """Tests for Layer.copy_to_comp()."""

    def test_copy_increases_count(self) -> None:
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        src_comp = get_comp(app.project, "parent")
        dst_comp = get_comp(app.project, "comment")
        assert len(dst_comp.layers) == 1
        src_comp.layers[0].copy_to_comp(dst_comp)
        assert len(dst_comp.layers) == 2

    def test_copy_does_not_remove_from_source(self) -> None:
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        src_comp = get_comp(app.project, "parent")
        dst_comp = get_comp(app.project, "comment")
        n_before = len(src_comp.layers)
        src_comp.layers[0].copy_to_comp(dst_comp)
        assert len(src_comp.layers) == n_before

    def test_copy_placed_at_top(self) -> None:
        """Copied layer is at the top (index 0) of target comp."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        src_comp = get_comp(app.project, "parent")
        dst_comp = get_comp(app.project, "comment")
        original_name = src_comp.layers[0].name
        src_comp.layers[0].copy_to_comp(dst_comp)
        assert dst_comp.layers[0].name == original_name

    def test_copy_clears_parent(self) -> None:
        """Copied layer has no parent in the target comp."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        src_comp = get_comp(app.project, "parent")
        dst_comp = get_comp(app.project, "comment")
        child = src_comp.layers[0]  # ChildLayer, has parent
        assert child._parent_id != 0
        child.copy_to_comp(dst_comp)
        assert dst_comp.layers[0]._parent_id == 0

    def test_same_comp_duplicates(self) -> None:
        """Copying to the same comp delegates to duplicate()."""
        app = parse_aep(SAMPLES_DIR / "light_source_default.aep")
        comp = get_comp(app.project, "crystal")
        assert len(comp.layers) == 3
        result = comp.layers[0].copy_to_comp(comp)
        assert len(comp.layers) == 4
        assert result is comp.layers[0]

    def test_copy_returns_layer(self) -> None:
        """copy_to_comp returns the newly created layer."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        src_comp = get_comp(app.project, "parent")
        dst_comp = get_comp(app.project, "comment")
        result = src_comp.layers[0].copy_to_comp(dst_comp)
        assert result is dst_comp.layers[0]

    def test_copy_unique_id(self) -> None:
        """Copied layer gets an ID unique within the target comp."""
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        src_comp = get_comp(app.project, "parent")
        dst_comp = get_comp(app.project, "comment")
        existing_ids = {ly.id for ly in dst_comp.layers}
        src_comp.layers[0].copy_to_comp(dst_comp)
        new_id = dst_comp.layers[0].id
        assert new_id not in existing_ids

    def test_copy_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer_misc.aep")
        src_comp = get_comp(app.project, "parent")
        dst_comp = get_comp(app.project, "comment")
        src_comp.layers[0].copy_to_comp(dst_comp)
        copied_name = dst_comp.layers[0].name
        copied_id = dst_comp.layers[0].id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        dst2 = get_comp(app2.project, "comment")
        assert len(dst2.layers) == 2
        assert dst2.layers[0].name == copied_name
        assert dst2.layers[0].id == copied_id


class TestLayerReservedBytes:
    """ldta _reserved_3b/_reserved_3c match AE across layer types.

    AE writes _reserved_3b=1 / _reserved_3c=0 for every non-camera/light
    layer (AV, shape, text), and 0/0 for cameras and lights.
    """

    def test_new_layer_reserved_bytes(self) -> None:
        comp = py_aep.new().project.root_folder.add_comp("t", 100, 100, 1.0, 1.0, 30.0)
        av = comp.add_solid([1.0, 0.0, 0.0])
        shape = comp.add_shape()
        camera = comp.add_camera()
        light = comp.add_light()
        for layer in (av, shape):
            assert layer._ldta._reserved_3b == 1
            assert layer._ldta._reserved_3c == 0
        for layer in (camera, light):
            assert layer._ldta._reserved_3b == 0
            assert layer._ldta._reserved_3c == 0
