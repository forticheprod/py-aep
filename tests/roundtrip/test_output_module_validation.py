"""Format-dependent validation of output-module settings writes.

Reject cases assert `ValueError` on values AE's dialog never offers for
the format; accept cases write an allowed value and verify it survives a
save + fresh reparse (including the clamp side effects).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep.enums import (
    OutputAudio,
    OutputChannels,
    OutputColorDepth,
    OutputColorMode,
)

RQ_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "renderqueue"


def _om(project):
    return project.render_queue.items[0].output_modules[0]


REJECTS = [
    # (sample, key, value) - corruption-preventing rows first: turning
    # video on for an audio format writes comp dimensions into the Rouu.
    ("format_mp3", "Video Output", True),
    ("format_wav", "Video Output", True),
    ("format_aiff", "Output Audio", OutputAudio.OFF),
    ("format_mp3", "Output Audio", OutputAudio.AUTO),
    ("format_tiff_sequence", "Video Output", False),
    ("format_png_sequence", "Output Audio", OutputAudio.ON),
    ("format_png_sequence", "Depth", OutputColorDepth.FLOATING_POINT),
    ("format_openexr_sequence", "Depth", OutputColorDepth.MILLIONS_OF_COLORS),
    ("format_jpeg_sequence", "Channels", OutputChannels.RGBA),
    ("format_jpeg_sequence", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("format_radiance_sequence", "Channels", OutputChannels.RGBA),
    ("format_radiance_sequence", "Depth", OutputColorDepth.MILLIONS_OF_COLORS),
    ("format_targa_sequence", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("format_dpx_cineon_sequence", "Depth", OutputColorDepth.MILLIONS_OF_COLORS),
    ("format_sgi_sequence", "Depth", OutputColorDepth.FLOATING_POINT),
    ("format_h264", "Channels", OutputChannels.RGBA),
    ("format_h264", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("format_h264", "Audio Sample Rate", 8000),
    ("format_quicktime", "Depth", OutputColorDepth.FLOATING_POINT),
    ("format_aiff", "Audio Sample Rate", 24000),
    ("format_mp3", "Audio Sample Rate", 88200),
    ("format_mp3", "Audio Bit Depth", 4),  # 32-bit; MP3 is locked to 16
]


@pytest.mark.parametrize(
    ("sample", "key", "value"),
    REJECTS,
    ids=[f"{s}-{k}-{v}" for s, k, v in REJECTS],
)
def test_disallowed_write_raises(sample: str, key: str, value: object) -> None:
    project = parse_project_fresh(RQ_DIR / f"{sample}.aep")
    om = _om(project)
    before = om.get_settings()
    with pytest.raises(ValueError):
        om.settings[key] = value
    assert om.get_settings() == before, "rejected write must not mutate"


# NOTE: the samples store RGB channels, so only base (non-`+`) depths
# are writable - the channels<->depth parity rows mirror AE's dialog,
# which offers `+` depths only under RGB+Alpha.
ACCEPTS = [
    ("format_tiff_sequence", "Depth", OutputColorDepth.FLOATING_POINT),
    ("format_sgi_sequence", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("format_iff_sequence", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("format_aiff", "Audio Sample Rate", 96000),
    ("format_wav", "Audio Sample Rate", 8000),
    ("format_avi", "Audio Sample Rate", 96000),
    ("format_h264", "Audio Sample Rate", 44100),
    # The sample stores bitrate 128 + stereo, which resolves 44100.
    ("format_mp3", "Audio Sample Rate", 44100),
    ("format_quicktime", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("format_photoshop_sequence", "Depth", OutputColorDepth.FLOATING_POINT),
]


def test_quicktime_supports_alpha(tmp_path: Path) -> None:
    """QT alpha is AE-legal: the factory template "High Quality with
    Alpha" writes a QT Rouu with depth 32 (millions+)."""
    project = parse_project_fresh(
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "format_options"
        / "quicktime"
        / "apple_prores_4444.aep"
    )
    om = project.render_queue.items[0].output_modules[0]
    om.settings["Channels"] = OutputChannels.RGBA
    assert om.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.settings["Channels"] == OutputChannels.RGBA
    assert om2.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS
    assert om2.validate_state() == []


def test_plus_depth_requires_rgba_channels() -> None:
    """AE offers `+` depths only under RGB+Alpha (parity rows)."""
    project = parse_project_fresh(RQ_DIR / "format_photoshop_sequence.aep")
    om = _om(project)
    with pytest.raises(ValueError):
        om.settings["Depth"] = OutputColorDepth.FLOATING_POINT_PLUS  # RGB module
    om.settings["Channels"] = OutputChannels.RGBA
    om.settings["Depth"] = OutputColorDepth.FLOATING_POINT_PLUS
    with pytest.raises(ValueError):
        om.settings["Depth"] = OutputColorDepth.FLOATING_POINT  # base under RGBA


@pytest.mark.parametrize(
    ("sample", "key", "value"),
    ACCEPTS,
    ids=[f"{s}-{k}-{v}" for s, k, v in ACCEPTS],
)
def test_allowed_write_survives_roundtrip(
    sample: str, key: str, value: object, tmp_path: Path
) -> None:
    project = parse_project_fresh(RQ_DIR / f"{sample}.aep")
    om = _om(project)
    om.settings[key] = value
    assert om.settings[key] == value
    project.save(tmp_path / "out.aep")
    reparsed = parse_project_fresh(tmp_path / "out.aep")
    assert _om(reparsed).settings[key] == value


def test_png_rgba_clamps_color_straight(tmp_path: Path) -> None:
    """Switching PNG to RGB+Alpha forces Straight and the +alpha depth."""
    project = parse_project_fresh(RQ_DIR / "format_png_sequence.aep")
    om = _om(project)
    om.settings["Color"] = OutputColorMode.PREMULTIPLIED  # inert while RGB
    om.settings["Channels"] = OutputChannels.RGBA
    assert om.settings["Color"] == OutputColorMode.STRAIGHT_UNMATTED
    assert om.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.settings["Channels"] == OutputChannels.RGBA
    assert om2.settings["Color"] == OutputColorMode.STRAIGHT_UNMATTED
    assert om2.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS


def test_exr_rgba_clamps_color_premultiplied(tmp_path: Path) -> None:
    project = parse_project_fresh(RQ_DIR / "format_openexr_sequence.aep")
    om = _om(project)
    om.settings["Color"] = OutputColorMode.STRAIGHT_UNMATTED  # inert while RGB
    om.settings["Channels"] = OutputChannels.RGBA
    assert om.settings["Color"] == OutputColorMode.PREMULTIPLIED
    assert om.settings["Depth"] == OutputColorDepth.FLOATING_POINT_PLUS
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.settings["Color"] == OutputColorMode.PREMULTIPLIED
    assert om2.settings["Depth"] == OutputColorDepth.FLOATING_POINT_PLUS


def test_rgba_color_write_rejected_after_clamp() -> None:
    project = parse_project_fresh(RQ_DIR / "format_png_sequence.aep")
    om = _om(project)
    om.settings["Channels"] = OutputChannels.RGBA
    with pytest.raises(ValueError):
        om.settings["Color"] = OutputColorMode.PREMULTIPLIED


def test_crop_resize_roi_writes_keep_audio_module_audio_only() -> None:
    """Video-section side effects must not write dims into an audio Rouu.

    The Video Output gate blocks the direct write; the crop/resize/ROI
    post_set hooks used to bypass it by writing comp dimensions (which
    ARE the video-output flag) into the audio-only Rouu.
    """
    project = parse_project_fresh(RQ_DIR / "format_mp3.aep")
    om = _om(project)
    om.settings["Crop"] = True
    om.settings["Crop Left"] = 10
    om.settings["Use Region of Interest"] = True
    om.settings["Resize"] = False
    assert om.settings["Video Output"] is False
    assert (om._roou.width, om._roou.height) == (0, 0)
    assert om.validate_state() == []
    with pytest.raises(ValueError):
        om.settings["Resize to"] = [1280, 720]


def test_garbage_channels_byte_stays_permissive() -> None:
    """An out-of-enum stored byte degrades permissively, never raises.

    OutputChannels has no from_binary fallback, so a garbage channels
    byte makes the descriptor read raise; the context builder, clamps
    and validate_state must treat that as "unclean -> skip" instead of
    propagating (permissive-degradation contract).
    """
    project = parse_project_fresh(RQ_DIR / "format_png_sequence.aep")
    om = _om(project)
    om._om_ldat.channels = 7  # not a valid OutputChannels member
    om.settings["Depth"] = OutputColorDepth.TRILLIONS_OF_COLORS  # no raise
    om.settings["Audio Channels"] = om.settings["Audio Channels"]  # clamp path
    assert om.validate_state() == []
