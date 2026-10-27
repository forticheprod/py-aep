"""MXF header probing against what After Effects 2026 reports for the same
files (samples/assets/mxf_*.mxf, ffmpeg-written OP1a and OP-Atom)."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.resolvers.media_probe import probe_media

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"


def test_op1a_dnxhr_stereo() -> None:
    info = probe_media(ASSETS / "mxf_dnxhr_320x180p25.mxf")
    assert (info.width, info.height) == (320, 180)
    assert info.frame_rate == 25.0
    assert info.duration == pytest.approx(8 / 25)
    assert info.frames == 8
    assert info.pixel_aspect == 1.0
    assert info.pixel_aspect_terms == (1, 1)
    assert info.field_order == 0
    assert info.field_label
    assert info.depth == 24
    assert not info.has_alpha
    assert info.has_audio
    assert info.audio_sample_rate == 48000.0
    assert info.audio_channels == 2
    assert (info.timecode_start, info.timecode_drop_frame) == (0, False)


def test_drop_frame_timecode_and_two_mono_tracks() -> None:
    info = probe_media(ASSETS / "mxf_dnxhr_2997_df_tc.mxf")
    # AE stores the 3-decimal rate, and the duration as 8 frames over it.
    assert info.frame_rate == 29.97
    assert info.duration == pytest.approx(8 / 29.97)
    assert info.timecode_start == 111582
    assert info.timecode_drop_frame
    assert info.audio_channels == 2


def test_mpeg2_pal_interlaced_upper_first_d1_aspect() -> None:
    info = probe_media(ASSETS / "mxf_mpeg2_pal_4x3_tff.mxf")
    assert (info.width, info.height) == (720, 576)
    assert info.field_order == 1
    # The D1/DV PAL preset, stored unreduced as AE writes it.
    assert info.pixel_aspect_terms == (768, 702)
    assert info.pixel_aspect == pytest.approx(1.0940, abs=1e-4)


def test_h264_ntsc_keeps_computed_aspect() -> None:
    info = probe_media(ASSETS / "mxf_h264_ntsc_16x9.mxf")
    assert (info.width, info.height) == (720, 480)
    assert info.frame_rate == 29.97
    assert info.duration == pytest.approx(2 / 29.97)
    assert info.pixel_aspect_terms == (32, 27)
    assert info.field_order == 0


def test_dv_pal_wide_preset_lower_field_first() -> None:
    info = probe_media(ASSETS / "mxf_dv_pal_16x9.mxf")
    assert (info.width, info.height) == (720, 576)
    assert info.pixel_aspect_terms == (512, 351)
    assert info.field_order == 2


def test_prores_10_bit_depth() -> None:
    info = probe_media(ASSETS / "mxf_prores422_320x180.mxf")
    assert info.bit_depth == 10
    assert info.depth == 48
    assert not info.has_alpha


def test_hd_anamorphic_aspect() -> None:
    info = probe_media(ASSETS / "mxf_mpeg2_1440x1080_16x9.mxf")
    assert (info.width, info.height) == (1440, 1080)
    assert info.pixel_aspect_terms == (4, 3)


def test_op_atom_audio_only() -> None:
    info = probe_media(ASSETS / "mxf_opatom_pcm_1ch.mxf")
    assert (info.width, info.height) == (0, 0)
    assert info.frame_rate == 0.0
    # The sound clip's length in samples over its sample rate.
    assert info.duration == pytest.approx(5760 / 48000)
    assert info.has_audio
    assert info.audio_channels == 1
    assert info.depth == 0


def test_op_atom_video_only() -> None:
    info = probe_media(ASSETS / "mxf_opatom_h264_320x180.mxf")
    assert (info.width, info.height) == (320, 180)
    assert info.duration == pytest.approx(4 / 25)
    assert not info.has_audio
    assert info.audio_channels == 0


def test_undecodable_picture_coding_raises() -> None:
    # AE 2026 refuses an FFV1 MXF outright, audio track included.
    with pytest.raises(ValueError, match="cannot decode the MXF picture coding"):
        probe_media(ASSETS / "mxf_ffv1_320x180.mxf")


def test_not_an_mxf_raises(tmp_path: Path) -> None:
    path = tmp_path / "not.mxf"
    path.write_bytes(b"\x00" * 100)
    with pytest.raises(ValueError, match="no header partition pack"):
        probe_media(path)


def test_truncated_header_raises(tmp_path: Path) -> None:
    path = tmp_path / "cut.mxf"
    path.write_bytes((ASSETS / "mxf_dnxhr_320x180p25.mxf").read_bytes()[:2000])
    with pytest.raises(ValueError):
        probe_media(path)
