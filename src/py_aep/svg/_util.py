"""Shared low-level helpers for the SVG reader package."""

from __future__ import annotations

import re

# An SVG/CSS number token: optional sign, decimal or integer, optional exponent.
NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
# The same token allowing a trailing `%` (CSS color / ratio values).
NUMBER_PCT_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?%?")


def local_name(tag: str) -> str:
    """Strip an XML namespace, e.g. `{http://...}rect` -> `rect`."""
    return tag.rsplit("}", 1)[-1]


def clamp01(value: float) -> float:
    """Clamp a float to the `[0.0, 1.0]` range."""
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def parse_number(text: str | None, default: float = 0.0) -> float:
    """Leading numeric value of `text`, ignoring a unit suffix (e.g.
    `"40px"` -> `40.0`); `default` when absent or non-numeric."""
    if not text:
        return default
    m = NUMBER_RE.match(text.strip())
    return float(m.group()) if m else default


def parse_ratio(text: str | None, default: float) -> float:
    """CSS ratio (`0.5` or `50%`) clamped to `[0, 1]`; `default` when the
    value is absent or non-numeric (e.g. the keyword `inherit`)."""
    if text is None:
        return default
    text = text.strip()
    m = NUMBER_RE.match(text)
    if m is None:
        return default
    val = float(m.group())
    return clamp01(val / 100.0 if text.endswith("%") else val)
