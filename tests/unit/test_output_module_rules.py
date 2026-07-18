"""Integrity checks for the output-module rules tables.

These tests make the clamp/sync bypass writes safe: values written
outside the descriptors (depth pairing, singleton clamps) are proven to
stay inside the tables, so re-validation on the bypass path is never
needed.
"""

from __future__ import annotations

import pytest

from py_aep.data.output_module_rules import (
    _CONDITIONAL_RULES,
    _FORMAT_RULES,
    _KIND_RULES,
    allowed_values,
)
from py_aep.enums import (
    AudioChannels,
    AudioCodec,
    FormatKind,
    OutputAudio,
    OutputChannels,
    OutputColorMode,
    OutputFormat,
)
from py_aep.models.renderqueue.output_module import (
    _DEPTH_MINUS,
    _DEPTH_PLUS,
    OM_SETTINGS,
)

# Context keys the OutputModule._rules_context builder can provide.
_CONDITION_KEYS = {
    "Channels",
    "Audio Channels",
    "Audio Sample Rate",
    "Audio Codec",
    "Video Codec",
    "Audio Format",
    "Audio Layer",
    "Multiplexer",
    "BitRate",
}

# Keys a rule may constrain: OM settings plus format-option fields.
_FO_CONSTRAINT_KEYS = {
    "Audio Bitrate",
    "Audio Codec",
    "Audio Format",
    "BitRate",
    "Multiplexer",
    "Video Codec",
}

_ALL_CHANNELS = frozenset(OutputChannels)


def _iter_all_constraint_dicts():
    for rules in _KIND_RULES.values():
        yield rules
    for rules in _FORMAT_RULES.values():
        yield rules
    for entries in _CONDITIONAL_RULES.values():
        for _, constraints in entries:
            yield constraints


def test_every_format_has_a_kind() -> None:
    # A new OutputFormat member must be classified before it ships.
    for fmt in OutputFormat:
        assert isinstance(fmt.kind, FormatKind)


def test_constraint_keys_are_known_settings() -> None:
    valid = set(OM_SETTINGS) | _FO_CONSTRAINT_KEYS
    for constraints in _iter_all_constraint_dicts():
        for key in constraints:
            assert key in valid, f"unknown constraint key {key!r}"


def test_condition_keys_are_buildable_context() -> None:
    for entries in _CONDITIONAL_RULES.values():
        for conditions, _ in entries:
            for key in conditions:
                assert key in _CONDITION_KEYS, f"unknown condition key {key!r}"


def test_no_empty_allowed_sets() -> None:
    # An empty set would make a setting unwritable for the format.
    for constraints in _iter_all_constraint_dicts():
        for key, values in constraints.items():
            assert values, f"empty allowed set for {key!r}"


def _depth_closure_ok(channels: frozenset, depths: frozenset) -> tuple[bool, str]:
    """Check the channels<->depth pairing closure for one rule branch."""
    if OutputChannels.RGBA in channels:
        for depth in depths:
            base = int(depth)
            if base in _DEPTH_PLUS and _DEPTH_PLUS[base] not in depths:
                return False, f"{base} has no +alpha pair in {sorted(depths)}"
    if channels & {OutputChannels.RGB, OutputChannels.ALPHA}:
        for depth in depths:
            plus = int(depth)
            if plus in _DEPTH_MINUS and _DEPTH_MINUS[plus] not in depths:
                return False, f"{plus} has no base pair in {sorted(depths)}"
    return True, ""


@pytest.mark.parametrize("fmt", list(OutputFormat), ids=lambda f: f.name)
def test_depth_pairing_closed_under_channel_sync(fmt: OutputFormat) -> None:
    """`_sync_after_channels` can never write an out-of-table depth.

    For every rule branch (format level and each conditional entry), any
    depth reachable through the RGBA pairing maps (`_DEPTH_PLUS/_MINUS`)
    from an allowed depth under allowed channels must itself be allowed.
    """
    fmt_rules = _FORMAT_RULES.get(fmt, {})
    branches = [(fmt_rules, None)]
    for conditions, constraints in _CONDITIONAL_RULES.get(fmt, []):
        merged = dict(fmt_rules)
        merged.update(constraints)
        branches.append((merged, conditions))
    for branch, conditions in branches:
        depths = branch.get("Depth")
        if depths is None:
            continue
        channels = branch.get("Channels", _ALL_CHANNELS)
        # A branch conditioned on specific channels only ever applies
        # there (e.g. the generated parity rows): narrow accordingly.
        cond_channels = (conditions or {}).get("Channels")
        if cond_channels is not None:
            if not isinstance(cond_channels, tuple):
                cond_channels = (cond_channels,)
            channels = channels & frozenset(cond_channels)
        ok, why = _depth_closure_ok(channels, depths)
        assert ok, f"{fmt.name}: {why}"


def test_forced_color_values_are_color_modes() -> None:
    # Singleton "Color" sets drive the clamp; their value must be a real
    # OutputColorMode so the raw byte write is well-formed.
    for entries in _CONDITIONAL_RULES.values():
        for _, constraints in entries:
            for value in constraints.get("Color", ()):
                assert isinstance(value, OutputColorMode)


def test_allowed_values_kind_and_format_merge() -> None:
    assert allowed_values(OutputFormat.MP3, "Video Output") == frozenset({False})
    assert allowed_values(OutputFormat.MP3, "Output Audio") == frozenset(
        {OutputAudio.ON}
    )
    assert allowed_values(OutputFormat.TIFF_SEQUENCE, "Output Audio") == frozenset(
        {OutputAudio.OFF}
    )
    # Movies leave both toggles free.
    assert allowed_values(OutputFormat.AVI, "Video Output") is None
    assert allowed_values(OutputFormat.AVI, "Output Audio") is None
    # Unconstrained key -> None (NOT an empty set).
    assert allowed_values(OutputFormat.TIFF_SEQUENCE, "Channels") is None


def test_allowed_values_conditional_replaces_format_row() -> None:
    # Without context the WAV union applies; with the GSM codec the
    # conditional row replaces it.
    union = allowed_values(OutputFormat.WAV, "Audio Sample Rate")
    assert union is not None and 96000 in union
    gsm = allowed_values(
        OutputFormat.WAV,
        "Audio Sample Rate",
        {"Audio Codec": AudioCodec.GSM_6_10},
    )
    assert gsm == frozenset({8000, 11025, 22050, 44100})
    channels = allowed_values(
        OutputFormat.WAV,
        "Audio Channels",
        {"Audio Codec": AudioCodec.GSM_6_10},
    )
    assert channels == frozenset({AudioChannels.MONO})


def test_allowed_values_missing_context_is_permissive() -> None:
    # No codec in context -> the conditional rows do not narrow.
    assert allowed_values(OutputFormat.WAV, "Audio Channels") is None
    assert allowed_values(OutputFormat.WAV, "Audio Channels", {}) is None
