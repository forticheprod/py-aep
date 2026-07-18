"""Typed XML-param accessors on XmlFormatOptions (context accessors).

Decode is checked against AE-saved samples; writes are verified through
a save + fresh reparse.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep.enums import AudioInterleave, MPEGAudioFormat, MPEGAudioLayer

FORMAT_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "format_options"
)


def _fo(project):
    return project.render_queue.items[0].output_modules[0].format_options


DECODES = [
    ("mp3/base", "bitrate", 128),
    ("mp3/base", "audio_interleave", None),  # MP3 stores no interleave
    ("avi/audio_interleave_1_frame", "audio_interleave", AudioInterleave.ONE_FRAME),
    (
        "avi/audio_interleave_half_second",
        "audio_interleave",
        AudioInterleave.HALF_SECOND,
    ),
    ("avi/audio_interleave_1_second", "audio_interleave", AudioInterleave.ONE_SECOND),
    ("avi/audio_interleave2_seconds", "audio_interleave", AudioInterleave.TWO_SECONDS),
    ("avi/audio_interleave_none", "audio_interleave", None),  # None = param absent
    ("h.264/base", "mpeg_audio_format", MPEGAudioFormat.AAC),
    ("h.264/audio_format_mpeg", "mpeg_audio_format", MPEGAudioFormat.MPEG),
    ("h.264/audio_format_pcm", "mpeg_audio_format", MPEGAudioFormat.PCM),
    ("h.264/audio_format_mpeg_layer_II", "mpeg_audio_layer", MPEGAudioLayer.LAYER_II),
    ("h.264/base", "audio_bitrate", 128),
    ("h.264/audio_codec_aac+_version_2", "audio_bitrate", 64),
    ("h.264/base", "profile", 1),
    ("h.264/base", "level", 41),
    ("quicktime/dnxhr_dnxhd", "resolution", 1017),
    ("quicktime/base", "resolution", None),
]


@pytest.mark.parametrize(
    ("sample", "attr", "expected"),
    DECODES,
    ids=[f"{s}-{a}" for s, a, _ in DECODES],
)
def test_decode(sample: str, attr: str, expected: object) -> None:
    project = parse_project_fresh(FORMAT_DIR / f"{sample}.aep")
    assert getattr(_fo(project), attr) == expected


WRITES = [
    ("mp3/base", "bitrate", 320),
    ("avi/base", "audio_interleave", AudioInterleave.ONE_SECOND),
    ("h.264/base", "audio_bitrate", 192),
    ("h.264/base", "level", 32),
]


@pytest.mark.parametrize(
    ("sample", "attr", "value"),
    WRITES,
    ids=[f"{s}-{a}" for s, a, _ in WRITES],
)
def test_write_survives_roundtrip(
    sample: str, attr: str, value: object, tmp_path: Path
) -> None:
    project = parse_project_fresh(FORMAT_DIR / f"{sample}.aep")
    setattr(_fo(project), attr, value)
    assert getattr(_fo(project), attr) == value
    project.save(tmp_path / "out.aep")
    reparsed = parse_project_fresh(tmp_path / "out.aep")
    assert getattr(_fo(reparsed), attr) == value


def test_scalar_write_rejects_non_int() -> None:
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    with pytest.raises(TypeError):
        _fo(project).bitrate = "320"


def test_scalar_write_rejects_bool() -> None:
    # bool is an int subclass; str(True) would corrupt the XML param.
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    with pytest.raises(TypeError):
        _fo(project).bitrate = True


def test_enum_param_write_rejects_bad_member() -> None:
    project = parse_project_fresh(FORMAT_DIR / "avi" / "base.aep")
    with pytest.raises(ValueError):
        _fo(project).audio_interleave = 99
