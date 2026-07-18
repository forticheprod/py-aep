"""Format-option write rules: member sets, conditionals, clamps, sync.

Covers the FO -> OM direction: codec/bitrate/container writes validate
against the module's format rules and re-clamp dependent settings, the
video codec syncs its Rouu 4cc mirror, and the back-reference that powers
it all is wired on every parsed module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, parse_app, parse_project_fresh

from py_aep.enums import (
    AudioChannels,
    AudioCodec,
    MPEGAudioFormat,
    MPEGMultiplexer,
    OutputChannels,
    OutputColorDepth,
    VideoCodec,
)

FORMAT_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "format_options"
)


def _om(project):
    return project.render_queue.items[0].output_modules[0]


# -- back-reference wiring ---------------------------------------------------

_CORPUS = sorted((SAMPLES_DIR / "models").rglob("*.aep"))


@pytest.mark.parametrize(
    "aep_path",
    _CORPUS,
    ids=[str(p.relative_to(SAMPLES_DIR)) for p in _CORPUS],
)
def test_parent_om_backref_is_wired(aep_path) -> None:
    app = parse_app(aep_path)
    for rqi in app.project.render_queue.items:
        for om in rqi.output_modules:
            if om.format_options is not None:
                assert om.format_options._parent_om is om


def test_parent_om_backref_survives_apply_template(tmp_path: Path) -> None:
    # apply_template swaps the Ropt and re-derives format_options; the
    # fresh object must be re-wired. Template parsing needs a prefs dir,
    # so emulate the re-derive path directly (the real one also detaches
    # the outgoing wrapper - see the batch_edit rollback tests below).
    project = parse_project_fresh(FORMAT_DIR / "targa" / "base.aep")
    om = _om(project)
    fo_before = om.format_options
    rqi = project.render_queue.items[0]
    from py_aep.parsers.format_options import parse_format_options

    om._format_options = parse_format_options(rqi._lom.chunks)
    om._format_options._parent_om = om  # what _apply_output_template does
    assert om.format_options is not fo_before
    assert om.format_options._parent_om is om


# -- detachment on rebind ----------------------------------------------------


def _stale_options(project):
    """Force a batch_edit rollback, returning the now-replaced wrapper."""
    om = _om(project)
    fo = om.format_options
    with pytest.raises(RuntimeError, match="force rollback"):
        with om.batch_edit():
            raise RuntimeError("force rollback")
    assert om.format_options is not fo
    return om, fo


def test_rollback_detaches_outgoing_options() -> None:
    project = parse_project_fresh(FORMAT_DIR / "targa" / "base.aep")
    om, fo = _stale_options(project)
    assert fo._detached
    assert not om.format_options._detached


def test_stale_options_reject_field_write() -> None:
    # A stale wrapper holds an Ropt no longer in the tree: the write would
    # land in an orphaned body, be dropped from the saved file, and still
    # read back as if it had succeeded.
    project = parse_project_fresh(FORMAT_DIR / "openexr" / "exr_rgba.aep")
    _, fo = _stale_options(project)
    with pytest.raises(RuntimeError, match="detached"):
        fo.compression = 3


def test_stale_xml_options_reject_typed_and_raw_writes() -> None:
    # Both surfaces, not just the rules-gated params: `frame_rate` writes
    # through `_set_param` and `params` is the raw escape hatch, so neither
    # passes through the format-rule check.
    project = parse_project_fresh(FORMAT_DIR / "h.264" / "base.aep")
    _, fo = _stale_options(project)
    with pytest.raises(RuntimeError, match="detached"):
        fo.audio_codec = AudioCodec.AAC
    with pytest.raises(RuntimeError, match="detached"):
        fo.frame_rate = 30.0
    with pytest.raises(RuntimeError, match="detached"):
        fo.params["ADBEVideoCodec"] = "5"
    with pytest.raises(RuntimeError, match="detached"):
        fo.params.pop("ADBEVideoCodec")


def test_live_options_still_writable_after_rollback() -> None:
    # The guard must not leak onto the replacement wrapper.
    project = parse_project_fresh(FORMAT_DIR / "openexr" / "exr_rgba.aep")
    om, _ = _stale_options(project)
    om.format_options.compression = 3
    assert om.format_options.compression == 3


# -- member sets --------------------------------------------------------------


def test_wav_rejects_non_wav_codec() -> None:
    project = parse_project_fresh(FORMAT_DIR / "wav" / "base.aep")
    with pytest.raises(ValueError):
        _om(project).format_options.audio_codec = AudioCodec.AAC


def test_avi_rejects_quicktime_codec() -> None:
    project = parse_project_fresh(FORMAT_DIR / "avi" / "base.aep")
    with pytest.raises(ValueError):
        _om(project).format_options.video_codec = VideoCodec.APPLE_PRORES_422


def test_mp3_rejects_unknown_bitrate() -> None:
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    with pytest.raises(ValueError):
        _om(project).format_options.bitrate = 999


# -- conditionals -------------------------------------------------------------


def test_pcm_rejected_under_mp4_multiplexer() -> None:
    project = parse_project_fresh(FORMAT_DIR / "h.264" / "base.aep")
    with pytest.raises(ValueError):
        _om(project).format_options.mpeg_audio_format = MPEGAudioFormat.PCM


def test_aac_bitrate_matrix_narrows_by_codec() -> None:
    project = parse_project_fresh(FORMAT_DIR / "h.264" / "base.aep")
    fo = _om(project).format_options
    fo.audio_bitrate = 512  # AAC @ 48 kHz stereo allows it
    fo.audio_codec = AudioCodec.AAC_PLUS_V1
    with pytest.raises(ValueError):
        fo.audio_bitrate = 512  # AAC+ v1 tops out at 96


# -- clamps and sync ----------------------------------------------------------


def test_gsm_codec_clamps_mono(tmp_path: Path) -> None:
    project = parse_project_fresh(FORMAT_DIR / "wav" / "base.aep")
    om = _om(project)
    assert om.settings["Audio Channels"] == AudioChannels.STEREO
    om.format_options.audio_codec = AudioCodec.GSM_6_10
    assert om.settings["Audio Channels"] == AudioChannels.MONO
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.format_options.audio_codec == AudioCodec.GSM_6_10
    assert om2.settings["Audio Channels"] == AudioChannels.MONO


def test_mp3_bitrate_clamps_rate(tmp_path: Path) -> None:
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    om = _om(project)
    om.format_options.bitrate = 320
    assert int(om.settings["Audio Sample Rate"]) == 48000
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.format_options.bitrate == 320
    assert int(om2.settings["Audio Sample Rate"]) == 48000


def test_v210_codec_clamps_depth(tmp_path: Path) -> None:
    project = parse_project_fresh(FORMAT_DIR / "avi" / "base.aep")
    om = _om(project)
    om.format_options.video_codec = VideoCodec.V210
    assert om.settings["Depth"] == OutputColorDepth.TRILLIONS_OF_COLORS
    # Rouu.video_codec stays the constant AVI plugin tag: AE never
    # varies it with the selected codec (corpus-verified).
    assert om._roou.video_codec == "CTXF"
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.format_options.video_codec == VideoCodec.V210
    assert om2._roou.video_codec == "CTXF"
    assert om2.settings["Depth"] == OutputColorDepth.TRILLIONS_OF_COLORS


def test_3gpp_multiplexer_clamps_audio_format() -> None:
    project = parse_project_fresh(FORMAT_DIR / "h.264" / "audio_format_mpeg.aep")
    fo = _om(project).format_options
    assert fo.mpeg_audio_format == MPEGAudioFormat.MPEG
    fo.mpeg_multiplexer = MPEGMultiplexer.THREEGPP
    assert fo.mpeg_audio_format == MPEGAudioFormat.AAC


def test_targa_bits_not_coupled_to_channels(tmp_path: Path) -> None:
    """bits_per_pixel is a dialog-local byte AE leaves stale: RGB+Alpha
    with 24 bpp exists in AE-saved files (tga_rgba.aep), so channel
    writes neither clamp nor gate it."""
    project = parse_project_fresh(FORMAT_DIR / "targa" / "24_bits_per_pixel.aep")
    om = _om(project)
    om.settings["Channels"] = OutputChannels.RGBA
    assert om.format_options.bits_per_pixel == 24  # untouched, like AE
    assert om.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS
    om.format_options.bits_per_pixel = 32  # both values stay writable
    project.save(tmp_path / "out.aep")
    om2 = _om(parse_project_fresh(tmp_path / "out.aep"))
    assert om2.format_options.bits_per_pixel == 32
    assert om2.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS


def test_raw_params_escape_hatch_bypasses_rules() -> None:
    # Documented: the params dict is the low-level escape hatch.
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    fo = _om(project).format_options
    fo.params["BitRate"] = "999"
    assert fo.bitrate == 999
