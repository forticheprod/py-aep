"""Codec/context-conditional validation of output-module settings.

Fixtures are the AE-saved per-codec samples: each test parses the sample
whose stored codec/bitrate provides the rule context, then asserts the
narrowed sets accept/reject as AE's dialog does.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep.enums import (
    AudioBitDepth,
    AudioChannels,
    OutputChannels,
    OutputColorDepth,
)

FORMAT_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "format_options"
)
AVI_NONE_SAMPLE = FORMAT_DIR / "avi" / "video_codec_none.aep"


def _om(project):
    return project.render_queue.items[0].output_modules[0]


REJECTS = [
    # WAV: per-codec narrowing of the format-level union.
    ("wav/audio_codec_gsm_6.10", "Audio Sample Rate", 48000),
    ("wav/audio_codec_gsm_6.10", "Audio Channels", AudioChannels.STEREO),
    ("wav/audio_codec_gsm_6.10", "Audio Bit Depth", AudioBitDepth.THIRTY_TWO_BIT),
    ("wav/audio_codec_ima_adpcm", "Audio Sample Rate", 16000),
    ("wav/audio_codec_ccitt_a-law", "Audio Sample Rate", 32000),
    ("wav/audio_codec_ccitt_u-law", "Audio Bit Depth", AudioBitDepth.EIGHT_BIT),
    # AVI: per-video-codec channels/depth.
    ("avi/video_codec_dv_ntsc", "Channels", OutputChannels.RGBA),
    ("avi/video_codec_dv_ntsc", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("avi/video_codec_v210_10-bit_yuv", "Depth", OutputColorDepth.MILLIONS_OF_COLORS),
    ("avi/video_codec_v210_10-bit_yuv", "Channels", OutputChannels.RGBA),
    # H264: audio-format-conditional sample rates.
    ("h.264/audio_format_pcm", "Audio Sample Rate", 16000),
    ("h.264/audio_format_mpeg", "Audio Sample Rate", 22050),
    ("h.264/base", "Audio Sample Rate", 96000),  # AAC has no 96 kHz
    # MP3: (bitrate, stereo) resolves a single rate.
    ("mp3/base", "Audio Sample Rate", 22050),  # stored bitrate is 128
]


@pytest.mark.parametrize(
    ("sample", "key", "value"),
    REJECTS,
    ids=[f"{s}-{k}-{v}" for s, k, v in REJECTS],
)
def test_disallowed_under_codec_context(sample: str, key: str, value: object) -> None:
    project = parse_project_fresh(FORMAT_DIR / f"{sample}.aep")
    with pytest.raises(ValueError):
        _om(project).settings[key] = value


ACCEPTS = [
    ("wav/audio_codec_gsm_6.10", "Audio Sample Rate", 22050),
    ("wav/base", "Audio Sample Rate", 96000),  # Uncompressed keeps the union
    ("wav/base", "Audio Bit Depth", AudioBitDepth.EIGHT_BIT),
    ("avi/video_codec_v210_10-bit_yuv", "Depth", OutputColorDepth.TRILLIONS_OF_COLORS),
    ("h.264/audio_format_pcm", "Audio Sample Rate", 96000),
    ("h.264/audio_format_mpeg", "Audio Sample Rate", 32000),
    ("mp3/base", "Audio Sample Rate", 44100),
]


@pytest.mark.parametrize(
    ("sample", "key", "value"),
    ACCEPTS,
    ids=[f"{s}-{k}-{v}" for s, k, v in ACCEPTS],
)
def test_allowed_under_codec_context(
    sample: str, key: str, value: object, tmp_path: Path
) -> None:
    project = parse_project_fresh(FORMAT_DIR / f"{sample}.aep")
    om = _om(project)
    om.settings[key] = value
    project.save(tmp_path / "out.aep")
    assert _om(parse_project_fresh(tmp_path / "out.aep")).settings[key] == value


def test_avi_none_codec_allows_rgba(tmp_path: Path) -> None:
    project = parse_project_fresh(AVI_NONE_SAMPLE)
    om = _om(project)
    om.settings["Channels"] = OutputChannels.RGBA
    assert om.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.settings["Channels"] == OutputChannels.RGBA
    assert om2.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS


def test_mp3_bitrate_change_revalidates_rate() -> None:
    """Changing the FO bitrate narrows the rate to the new singleton."""
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    om = _om(project)
    om.format_options.bitrate = 320
    with pytest.raises(ValueError):
        om.settings["Audio Sample Rate"] = 44100
    om.settings["Audio Sample Rate"] = 48000
    assert int(om.settings["Audio Sample Rate"]) == 48000


def test_mp3_mono_rows_from_binary_evidence() -> None:
    """Mono resolves different single rates than stereo - incl. 12000 Hz,
    which only MP3 mono at 18/20 kbps can store (AE-saved evidence)."""
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "mp3_mono_18.aep")
    om = _om(project)
    assert int(om.settings["Audio Sample Rate"]) == 12000  # RATE_12000 decode
    with pytest.raises(ValueError):
        om.settings["Audio Sample Rate"] = 44100
    om.settings["Audio Sample Rate"] = 12000

    project = parse_project_fresh(FORMAT_DIR / "mp3" / "mp3_mono_320.aep")
    om = _om(project)
    with pytest.raises(ValueError):
        om.settings["Audio Sample Rate"] = 48000  # stereo@320, not mono@320
    om.settings["Audio Sample Rate"] = 44100


def test_modern_ae_depth_low_byte_decodes() -> None:
    """AE 2026 writes noise in the depth field's upper bytes; the low
    byte carries the real value (0xF8529Axx across the whole sweep)."""
    from py_aep.enums import OutputColorDepth

    for subdir, name, expected in (
        ("png", "png_rgba", OutputColorDepth.MILLIONS_OF_COLORS_PLUS),
        ("cineon", "dpx_rgba", OutputColorDepth.TRILLIONS_OF_COLORS_PLUS),
        ("openexr", "exr_rgba", OutputColorDepth.FLOATING_POINT_PLUS),
        ("cineon", "dpx_fido", OutputColorDepth.TRILLIONS_OF_COLORS),
    ):
        project = parse_project_fresh(FORMAT_DIR / subdir / f"{name}.aep")
        om = _om(project)
        assert om.settings["Depth"] == expected, name
        assert om.validate_state() == [], name


def test_dnx_alpha_type_decodes() -> None:
    qt = FORMAT_DIR / "quicktime"
    compressed = parse_project_fresh(
        qt / "Quicktime_720p-DNxHD-HQ-10-bit_Compressed.aep"
    )
    assert _om(compressed).format_options.dnx_alpha_type == 1
    none = parse_project_fresh(qt / "Quicktime_720p-DNxHD-HQ-10-bit_None.aep")
    assert _om(none).format_options.dnx_alpha_type is None
