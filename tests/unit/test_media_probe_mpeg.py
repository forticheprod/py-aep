"""MPEG-1 system stream and MPEG-2 program stream probing against what After
Effects 2026 reports for the same files (samples/assets/mpg_*.mpg,
ffmpeg-written: `mpg_ps2_*` are MPEG-2 program streams, the others MPEG-1
system streams carrying MPEG-2 video)."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.resolvers.media_probe import probe_media

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"


def test_mpeg1_system_d1_preset_and_lower_field_rule() -> None:
    info = probe_media(ASSETS / "mpg_720x576_4x3.mpg")
    assert (info.width, info.height) == (720, 576)
    assert info.frame_rate == 25.0
    assert info.frames == 6
    assert info.duration == pytest.approx(6 / 25)
    assert info.pixel_aspect_terms == (768, 702)
    # Progressive, but AE's 720x576 at 25 fps rule separates fields lower
    # first in an MPEG-1 system stream, and labels the footage then.
    assert info.field_order == 2
    assert info.field_label
    assert not info.has_audio


def test_mpeg1_system_non_preset_aspect_is_four_decimals() -> None:
    info = probe_media(ASSETS / "mpg_704x576_4x3.mpg")
    assert info.pixel_aspect_terms == (10909, 10000)
    assert info.pixel_aspect == pytest.approx(1.0909)
    assert info.field_order == 0
    assert not info.field_label


def test_mpeg1_system_hdv_aspect_and_upper_field_rule() -> None:
    info = probe_media(ASSETS / "mpg_1440x1080_16x9.mpg")
    assert info.pixel_aspect_terms == (4, 3)
    assert info.field_order == 1
    assert info.field_label


def test_mpeg2_program_stream_keeps_exact_aspect_and_no_field_order() -> None:
    assert probe_media(ASSETS / "mpg_ps2_704x576_4x3.mpg").pixel_aspect_terms == (
        12,
        11,
    )
    info = probe_media(ASSETS / "mpg_ps2_720x576_4x3.mpg")
    assert info.pixel_aspect_terms == (768, 702)
    assert info.field_order == 0
    # Progressive MPEG-2 pictures without audio carry the field label.
    assert info.field_label


def test_three_decimal_rate() -> None:
    info = probe_media(ASSETS / "mpg_320x180p23976.mpg")
    assert info.frame_rate == 23.976
    assert info.frames == 10
    assert info.duration == pytest.approx(10 / 23.976)


def test_frame_rate_extension_numerator_doubles_the_rate() -> None:
    info = probe_media(ASSETS / "mpg_320x180p2997_rateext_x2.mpg")
    assert info.frame_rate == 59.94
    assert info.frames == 30


def test_frame_rate_extension_denominator_is_refused() -> None:
    # AE 2026 cannot open an MPEG-1 system stream whose extension divides
    # the rate (a transport stream imports it at 29.97 / 4 = 7.492).
    with pytest.raises(ValueError, match="divides the rate"):
        probe_media(ASSETS / "mpg_320x180p2997_rateext_div4_post.mpg")


def test_cut_streams_keep_leading_b_pictures() -> None:
    # Both cut files open with a sequence header followed by an open GOP (an
    # I picture then two B pictures that display before it); unlike a
    # transport stream AE counts those B pictures: 10 frames of the 20.
    for name in ("mpg_320x180p25_cut.mpg", "mpg_ps2_320x180p25_cut.mpg"):
        info = probe_media(ASSETS / name)
        assert info.frames == 10, name
        assert info.duration == pytest.approx(10 / 25)


def test_mpeg1_system_gop_time_code_is_the_start_timecode() -> None:
    # The cut MPEG-1 system stream's first GOP header reads 00:00:00:10.
    info = probe_media(ASSETS / "mpg_320x180p25_cut.mpg")
    assert (info.timecode_start, info.timecode_drop_frame) == (10, False)
    # An MPEG-2 program stream ignores the GOP time code.
    info = probe_media(ASSETS / "mpg_ps2_320x180p25_cut.mpg")
    assert (info.timecode_start, info.timecode_drop_frame) == (0, True)


def test_stream_without_a_leading_sequence_header_is_refused() -> None:
    # The file starts with the previous GOP's last pictures: AE refuses it
    # ("Could not open source file"), a transport stream drops them.
    with pytest.raises(ValueError, match="sequence header"):
        probe_media(ASSETS / "mpg_320x180p25_cut_e.mpg")


def test_audio_sample_rate_and_channels() -> None:
    info = probe_media(ASSETS / "mpg_320x180p25_mp2_44k.mpg")
    assert info.has_audio
    assert info.audio_sample_rate == 44100.0
    assert info.audio_channels == 1
    assert not info.field_label  # fields off in an MPEG-1 system stream
    info = probe_media(ASSETS / "mpg_ps2_320x180p25_mp2stereo.mpg")
    assert (info.audio_sample_rate, info.audio_channels) == (48000.0, 2)
    # Stereo MPEG audio keeps the field label of a progressive MPEG-2
    # program stream; AC-3 (here mono) drops it.
    assert info.field_label
    info = probe_media(ASSETS / "mpg_ps2_320x180p25_ac3.mpg")
    assert (info.audio_sample_rate, info.audio_channels) == (48000.0, 1)
    assert not info.field_label


def test_existing_sample_counts_every_picture() -> None:
    info = probe_media(ASSETS / "mpeg.mpeg")
    assert (info.width, info.height) == (640, 360)
    assert info.frame_rate == 29.97
    assert info.frames == 400
    assert info.pixel_aspect_terms == (1, 1)


def test_not_an_mpeg_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "not.mpg"
    path.write_bytes(b"\x00" * 100)
    with pytest.raises(ValueError, match="sequence header"):
        probe_media(path)
