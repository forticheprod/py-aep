"""Footage source models."""

from __future__ import annotations

from .file import FileSource
from .footage import FootageSource
from .placeholder import PlaceholderSource
from .solid import SolidSource

__all__ = [
    "FileSource",
    "FootageSource",
    "PlaceholderSource",
    "SolidSource",
]
