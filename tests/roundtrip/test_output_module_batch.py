"""batch_edit(): deferred whole-state validation with rollback."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep.enums import (
    AudioChannels,
    AudioCodec,
    OutputChannels,
    OutputColorDepth,
    OutputColorMode,
)

FORMAT_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "format_options"
)
RQ_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "renderqueue"


def _om(project):
    return project.render_queue.items[0].output_modules[0]


def test_coupled_writes_succeed_in_any_order(tmp_path: Path) -> None:
    """The write order that raises outside a batch passes inside one."""
    # Outside: rate-under-old-codec then codec works, codec-then-rate
    # raises. In a batch both orders converge on the same valid state.
    project = parse_project_fresh(FORMAT_DIR / "wav" / "base.aep")
    om = _om(project)
    with om.batch_edit():
        om.settings["Audio Sample Rate"] = 22050
        om.format_options.audio_codec = AudioCodec.GSM_6_10
        om.settings["Audio Channels"] = AudioChannels.MONO
    project.save(tmp_path / "a.aep")

    project2 = parse_project_fresh(FORMAT_DIR / "wav" / "base.aep")
    om2 = _om(project2)
    with om2.batch_edit():
        om2.format_options.audio_codec = AudioCodec.GSM_6_10
        om2.settings["Audio Channels"] = AudioChannels.MONO
        om2.settings["Audio Sample Rate"] = 22050
    project2.save(tmp_path / "b.aep")

    for name in ("a.aep", "b.aep"):
        om3 = _om(parse_project_fresh(tmp_path / name))
        assert om3.format_options.audio_codec == AudioCodec.GSM_6_10
        assert om3.settings["Audio Channels"] == AudioChannels.MONO
        assert int(om3.settings["Audio Sample Rate"]) == 22050


def test_invalid_final_state_rolls_back_everything() -> None:
    project = parse_project_fresh(FORMAT_DIR / "wav" / "base.aep")
    om = _om(project)
    before = om.get_settings()
    before_codec = om.format_options.audio_codec
    with pytest.raises(ValueError) as excinfo:
        with om.batch_edit():
            om.format_options.audio_codec = AudioCodec.GSM_6_10
            om.settings["Audio Sample Rate"] = 96000  # invalid under GSM
            om.settings["Audio Channels"] = AudioChannels.STEREO  # invalid
    # One error, every violation listed.
    assert "Audio Sample Rate" in str(excinfo.value)
    assert "Audio Channels" in str(excinfo.value)
    assert om.get_settings() == before
    assert om.format_options.audio_codec == before_codec


def test_body_exception_rolls_back_and_propagates() -> None:
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    om = _om(project)
    with pytest.raises(RuntimeError):
        with om.batch_edit():
            om.format_options.bitrate = 320
            raise RuntimeError("boom")
    assert om.format_options.bitrate == 128


def test_rollback_restores_byte_identical_save(tmp_path: Path) -> None:
    """A rolled-back batch leaves no trace in the saved bytes."""
    sample = FORMAT_DIR / "wav" / "base.aep"
    project = parse_project_fresh(sample)
    project.save(tmp_path / "untouched.aep")

    project2 = parse_project_fresh(sample)
    om = _om(project2)
    with pytest.raises(ValueError):
        with om.batch_edit():
            om.format_options.audio_codec = AudioCodec.GSM_6_10
            om.settings["Audio Sample Rate"] = 96000
    project2.save(tmp_path / "rolled_back.aep")

    untouched = (tmp_path / "untouched.aep").read_bytes()
    rolled_back = (tmp_path / "rolled_back.aep").read_bytes()
    assert rolled_back == untouched


def test_stale_untouched_dependent_is_flagged() -> None:
    # v1 has no exit-clamping: the user must set coupled fields
    # explicitly; the aggregated error tells them which one is missing.
    project = parse_project_fresh(FORMAT_DIR / "mp3" / "base.aep")
    om = _om(project)
    with pytest.raises(ValueError) as excinfo:
        with om.batch_edit():
            om.format_options.bitrate = 320  # stored rate stays 44100
    assert "Audio Sample Rate" in str(excinfo.value)
    assert om.format_options.bitrate == 128  # rolled back


def test_depth_and_channels_converge_in_any_order() -> None:
    """A channels change re-pairs depth once, at exit - both orders
    converge on the same final state (no in-batch pairing flips)."""
    results = []
    for first, second in (("depth", "channels"), ("channels", "depth")):
        project = parse_project_fresh(RQ_DIR / "format_photoshop_sequence.aep")
        om = _om(project)
        with om.batch_edit():
            for step in (first, second):
                if step == "depth":
                    om.settings["Depth"] = OutputColorDepth.TRILLIONS_OF_COLORS
                else:
                    om.settings["Channels"] = OutputChannels.RGBA
        results.append(om.settings["Depth"])
    # The channels change re-pairs 48 -> 64 at exit in both orders.
    assert results == [
        OutputColorDepth.TRILLIONS_OF_COLORS_PLUS,
        OutputColorDepth.TRILLIONS_OF_COLORS_PLUS,
    ]


def test_unpaired_depth_without_channels_change_raises() -> None:
    """No channels change -> no silent re-pair; the parity rules flag
    the impossible pair and the batch rolls back."""
    project = parse_project_fresh(RQ_DIR / "format_photoshop_sequence.aep")
    om = _om(project)
    om.settings["Channels"] = OutputChannels.RGBA  # depth pairs to 32
    with pytest.raises(ValueError) as excinfo:
        with om.batch_edit():
            om.settings["Depth"] = OutputColorDepth.TRILLIONS_OF_COLORS  # base
    assert "Depth" in str(excinfo.value)
    assert om.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS


def test_nested_batches_validate_at_outermost() -> None:
    project = parse_project_fresh(RQ_DIR / "format_png_sequence.aep")
    om = _om(project)
    with om.batch_edit():
        with om.batch_edit():
            om.settings["Channels"] = OutputChannels.RGBA
        # Inner exit must not validate: Color is still premultiplied-free
        # only after we fix it here, in the outer batch.
        om.settings["Color"] = OutputColorMode.STRAIGHT_UNMATTED
    assert om.settings["Color"] == OutputColorMode.STRAIGHT_UNMATTED
    assert om.settings["Depth"] == OutputColorDepth.MILLIONS_OF_COLORS_PLUS


def test_batch_on_removed_module_raises_clearly() -> None:
    project = parse_project_fresh(FORMAT_DIR / "wav" / "base.aep")
    om = _om(project)
    lom_chunks = om._parent_rqi._lom.chunks
    start, end = om._block_span(lom_chunks)
    del lom_chunks[start:end]  # what remove() does to the chunk block
    with pytest.raises(RuntimeError, match="removed"):
        with om.batch_edit():
            pass


def test_validate_state_clean_on_parsed_sample() -> None:
    project = parse_project_fresh(FORMAT_DIR / "wav" / "audio_codec_gsm_6.10.aep")
    assert _om(project).validate_state() == []
