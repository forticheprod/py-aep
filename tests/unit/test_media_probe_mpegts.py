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
    assert info.frames == 5
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


def test_hevc_size_rate_and_square_pixels() -> None:
    info = probe_media(ASSETS / "ts_hevc_320x180p25.ts")
    assert (info.width, info.height) == (320, 180)
    assert info.frame_rate == 25.0
    assert info.frames == 5
    assert info.duration == pytest.approx(5 / 25)
    assert info.pixel_aspect_terms == (1, 1)
    assert (info.field_order, info.field_label) == (0, False)
    assert info.depth == 24
    assert not info.has_audio
    assert probe_media(ASSETS / "ts_hevc_320x180p2997.ts").frame_rate == 29.97
    assert probe_media(ASSETS / "ts_hevc_320x180p23976.ts").frame_rate == 23.976


def test_hevc_vui_aspect_is_ignored() -> None:
    # AE gives every H.265 stream square pixels: a 40:33 VUI aspect, a 4:3
    # D1 PAL frame and a 16:9 HDV frame all store 1/1.
    for name in (
        "ts_hevc_320x180p25_sar40x33.ts",
        "ts_hevc_720x576p25_4x3.ts",
        "ts_hevc_1440x1080p25_16x9.ts",
    ):
        assert probe_media(ASSETS / name).pixel_aspect_terms == (1, 1), name


def test_hevc_progressive_size_rules() -> None:
    info = probe_media(ASSETS / "ts_hevc_720x576p25_4x3.ts")
    assert (info.field_order, info.field_label) == (2, True)
    info = probe_media(ASSETS / "ts_hevc_720x480p2997_16x9.ts")
    assert (info.width, info.height, info.frame_rate) == (720, 480, 29.97)
    assert (info.field_order, info.field_label) == (2, True)
    info = probe_media(ASSETS / "ts_hevc_1440x1080p25_16x9.ts")
    assert (info.field_order, info.field_label) == (1, True)


def test_hevc_conformance_window_and_bit_depth() -> None:
    info = probe_media(ASSETS / "ts_hevc_322x182p25.ts")
    assert (info.width, info.height) == (322, 182)
    info = probe_media(ASSETS / "ts_hevc_320x180p25_10bit.ts")
    assert info.bit_depth == 10
    assert info.depth == 48


def test_hevc_field_coded_streams_read_as_frames_at_half_the_rate() -> None:
    # Field pictures at 50 per second: AE reads the 12 pictures as 12 frames
    # at 25 fps and applies its 720x576 at 25 fps lower-field rule.
    info = probe_media(ASSETS / "ts_hevc_720x576i50_tff.ts")
    assert info.frame_rate == 25.0
    assert info.frames == 12
    assert info.duration == pytest.approx(12 / 25)
    assert (info.field_order, info.field_label) == (2, True)
    # The same coding fed 25 pictures per second: 12.5 fps, no fields.
    info = probe_media(ASSETS / "ts_hevc_720x576i25_tff.ts")
    assert info.frame_rate == 12.5
    assert info.duration == pytest.approx(6 / 12.5)
    assert (info.field_order, info.field_label) == (0, False)


def test_hevc_frames_count_from_the_first_irap_picture() -> None:
    # A stream opening on a CRA keeps its RASL picture: 9 of 9.
    assert probe_media(ASSETS / "ts_hevc_320x180p25_cut.ts").frames == 9
    # Four trailing pictures before the first CRA are dropped: 17 of 21.
    assert probe_media(ASSETS / "ts_hevc_320x180p25_trail_first.ts").frames == 17


def test_hevc_with_aac_audio() -> None:
    info = probe_media(ASSETS / "ts_hevc_320x180p25_aac.ts")
    assert info.has_audio
    assert (info.audio_sample_rate, info.audio_channels) == (48000.0, 2)
    info = probe_media(ASSETS / "ts_hevc_320x180p25_aac44k.ts")
    assert (info.audio_sample_rate, info.audio_channels) == (44100.0, 2)


def test_hevc_vui_timing_wins_over_the_timestamps() -> None:
    # VUI timing says 50 while the timestamps step at 25 per second.
    info = probe_media(ASSETS / "ts_hevc_320x180p25_vuifps50.ts")
    assert (info.frame_rate, info.frames) == (50.0, 10)
    # Without VUI timing the timestamps give the rate...
    info = probe_media(ASSETS / "ts_hevc_320x180p25_novuitiming.ts")
    assert (info.frame_rate, info.frames) == (25.0, 10)
    # ...and a field-coded stream's timestamp rate is not halved, so the
    # 720x576 at 25 fps lower-field rule applies.
    info = probe_media(ASSETS / "ts_hevc_720x576i25_tff_novuitiming.ts")
    assert (info.frame_rate, info.frames) == (25.0, 6)
    assert (info.field_order, info.field_label) == (2, True)


def test_hevc_non_standard_rate_is_kept() -> None:
    assert probe_media(ASSETS / "ts_hevc_320x180p12345.ts").frame_rate == 12.345


def test_hevc_leading_pictures_and_slices_count_once() -> None:
    # A BLA picture and its RADL leading picture count like a CRA and RASL.
    assert probe_media(ASSETS / "ts_hevc_320x180p25_cut_bla_radl.ts").frames == 9
    # Two slice segments per picture: still 5 pictures.
    assert probe_media(ASSETS / "ts_hevc_320x180p25_slices2.ts").frames == 5


def test_hevc_without_parameter_sets_is_refused() -> None:
    with pytest.raises(ValueError, match="sequence parameter set"):
        probe_media(ASSETS / "ts_hevc_320x180p25_nosps.ts")


def test_hevc_192_byte_packets() -> None:
    assert probe_media(ASSETS / "ts_hevc_320x180p25.m2ts").duration == pytest.approx(
        0.2
    )


def test_hevc_monochrome_window_is_scaled_like_420() -> None:
    # 322x182 coded as 336x192 with a 14 x 10 conformance window: AE takes
    # twice the offsets off a monochrome frame, as it would for 4:2:0.
    info = probe_media(ASSETS / "ts_hevc_322x182p25_gray.ts")
    assert (info.width, info.height) == (308, 172)
    assert probe_media(ASSETS / "ts_hevc_322x182p25_gray10.ts").width == 308


def test_hevc_depth_is_16_bpc_for_10_bit_420_and_422_only() -> None:
    assert probe_media(ASSETS / "ts_hevc_320x180p25_10bit.ts").depth == 48
    for name in (
        "ts_hevc_320x180p25_12bit.ts",
        "ts_hevc_320x180p25_444_10bit.ts",
        "ts_hevc_322x182p25_gray10.ts",
    ):
        info = probe_media(ASSETS / name)
        assert (info.bit_depth, info.depth) == (8, 24), name


def test_not_a_transport_stream_raises(tmp_path: Path) -> None:
    path = tmp_path / "not.ts"
    path.write_bytes(b"\x00" * 1000)
    with pytest.raises(ValueError, match="no packet sync"):
        probe_media(path)
