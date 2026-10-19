"""MPEG transport-stream probing against what After Effects 2026 reports for
the same files (samples/assets/ts_*, ffmpeg-written)."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.resolvers.media_probe import probe_media

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"


def test_h264_with_ac3_audio() -> None:
    info = probe_media(ASSETS / "ts_h264_320x180p25_ac3.ts")
    assert (info.width, info.height) == (320, 180)
    assert info.frame_rate == 25.0
    assert info.duration == pytest.approx(5 / 25)
    assert info.pixel_aspect_terms == (1, 1)
    assert info.field_order == 0
    assert not info.field_label
    assert info.depth == 24
    assert info.has_audio
    # AE records a stereo block at 48 kHz for every audio stream.
    assert info.audio_channels == 2
    assert info.audio_sample_rate == 48000.0
    assert info.timecode_drop_frame


def test_192_byte_packets_read_alike() -> None:
    info = probe_media(ASSETS / "ts_h264_320x180p25_ac3.m2ts")
    assert (info.width, info.height, info.duration) == (320, 180, pytest.approx(5 / 25))
    assert info.has_audio


def test_mpeg2_pal_interlaced_upper_first_d1_aspect() -> None:
    info = probe_media(ASSETS / "ts_mpeg2_720x576i25_4x3.ts")
    assert (info.width, info.height) == (720, 576)
    assert info.field_order == 1
    assert info.field_label
    # The D1/DV PAL preset, stored unreduced as AE writes it.
    assert info.pixel_aspect_terms == (768, 702)
    assert not info.has_audio


def test_h264_ntsc_keeps_vui_aspect_and_follows_the_lower_field_rule() -> None:
    info = probe_media(ASSETS / "ts_h264_720x480p2997_16x9.ts")
    assert (info.width, info.height) == (720, 480)
    assert info.frame_rate == 29.97
    assert info.duration == pytest.approx(5 / 29.97)
    assert info.pixel_aspect_terms == (32, 27)
    # Progressive coding, but AE's 720x480 at 29.97 rule sets lower first.
    assert info.field_order == 2
    assert info.field_label


def test_h264_vui_aspect_table() -> None:
    info = probe_media(ASSETS / "ts_h264_320x180p2997_sar40x33.ts")
    assert info.pixel_aspect_terms == (40, 33)
    assert info.pixel_aspect == pytest.approx(40 / 33)
    assert info.field_order == 0
    assert not info.field_label


def test_hdv_size_rule_upper_first_anamorphic() -> None:
    info = probe_media(ASSETS / "ts_h264_1440x1080p25_16x9.ts")
    assert (info.width, info.height) == (1440, 1080)
    assert info.duration == pytest.approx(3 / 25)
    assert info.pixel_aspect_terms == (4, 3)
    assert info.field_order == 1
    assert info.field_label


def test_frames_count_from_the_first_i_picture() -> None:
    # Streams cut mid-GOP: AE drops the pictures before the first I picture
    # in coded order and, once its media index is complete, an open GOP's
    # leading B pictures: 8 of 14 frames are left after a 3-unit H.264 cut
    # and after a 2-unit MPEG-2 cut alike.
    assert probe_media(ASSETS / "ts_h264_320x180p25_cut.ts").duration == pytest.approx(
        8 / 25
    )
    assert probe_media(ASSETS / "ts_mpeg2_320x180p25_cut.ts").duration == pytest.approx(
        8 / 25
    )


def test_audio_only() -> None:
    info = probe_media(ASSETS / "ts_aac_only.ts")
    assert (info.width, info.height) == (0, 0)
    assert info.frame_rate == 0.0
    # 25 AAC frames of 1024 samples over AE's 48 kHz.
    assert info.duration == pytest.approx(25600 / 48000)
    assert info.has_audio
    assert info.audio_channels == 2
    assert info.depth == 0


def test_hevc_raises() -> None:
    with pytest.raises(ValueError, match="HEVC"):
        probe_media(ASSETS / "ts_hevc_320x180p25.ts")


def test_not_a_transport_stream_raises(tmp_path: Path) -> None:
    path = tmp_path / "not.ts"
    path.write_bytes(b"\x00" * 1000)
    with pytest.raises(ValueError, match="no packet sync"):
        probe_media(path)
