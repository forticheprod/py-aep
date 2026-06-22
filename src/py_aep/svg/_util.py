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
