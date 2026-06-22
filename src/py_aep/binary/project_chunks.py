"""Root-level project chunk types used when building a new project.

These chunks appear once at the top of the `RIFX` of every `.aep` and
are otherwise opaque to py_aep. They are modelled here with best-guess
`fmt_field`s and fresh-project defaults (captured from an AE 2026 empty
project) so `Project._new()` can build a valid skeleton by instantiating
them with no arguments. See `scripts/dev/dump_new_project.py`.
"""

from __future__ import annotations

from attrs import define

from .chunk import Chunk
from .fmt_field import bytes_field, u1_field, u2_field, u4_field
from .registry import register

# ---------------------------------------------------------------------------
# svap - save-app marker (4 bytes); byte 3 tracks the AE build number
# ---------------------------------------------------------------------------


@register("svap")
@define
class SvapChunk(Chunk):
    """Top-of-file marker (4 bytes).

    The last byte is the AE build number; the leading 3 bytes are stable
    for AE 2024+ (AE's open gate keys off `head.file_format_version`, not
    svap).
    """

    chunk_type: str = "svap"

    _prefix: bytes = bytes_field(3, default=b"\x0f\x10\x06", repr=False)
    build_number: int = u1_field(default=0x43)


# ---------------------------------------------------------------------------
# cpid - project id (16 bytes, all 0xFF in a new project)
# ---------------------------------------------------------------------------


@register("cpid")
@define
class CpidChunk(Chunk):
    """Project id chunk (16 bytes). AE writes all-`0xFF` for a new project."""

    chunk_type: str = "cpid"
    data: bytes = b"\xff" * 16


# ---------------------------------------------------------------------------
# fdta - root folder data (14 bytes)
# ---------------------------------------------------------------------------


@register("fdta")
@define
class FdtaChunk(Chunk):
    """Root folder descriptor (14 bytes).

    The leading 10 bytes are zero; the 4-byte tail is an opaque
    folder-state value that varies per file (AE rewrites it on save).
    """

    chunk_type: str = "fdta"

    _reserved_00: bytes = bytes_field(10, repr=False)
    _tail: bytes = bytes_field(4, default=b"\x1f\x44\x84\x00", repr=False)


# ---------------------------------------------------------------------------
# Rhed - render queue header (20 bytes)
# ---------------------------------------------------------------------------


@register("Rhed")
@define
class RhedChunk(Chunk):
    """Render queue header (`LRdr/Rhed`, 20 bytes)."""

    chunk_type: str = "Rhed"

    _a: int = u2_field(default=1, repr=False)
    _b: int = u2_field(default=2, repr=False)
    _c: int = u4_field(repr=False)
    _d: int = u4_field(repr=False)
    # Render-queue identity captured from one empty project. The fixed default
    # is intentional: it keeps py_aep.new() output deterministic, and AE
    # rewrites render-queue state on save - so every generated file sharing
    # this value is inert (it is not a cross-file item/project id).
    _uid: int = u4_field(default=0x03E2076C, repr=False)
    _e: int = u4_field(default=1, repr=False)


# ---------------------------------------------------------------------------
# wsns - workspace-name byte length (U2); wsnm - workspace name (UTF-16-LE)
# ---------------------------------------------------------------------------


@register("wsns")
@define
class WsnsChunk(Chunk):
    """Workspace-name byte length (2 bytes).

    Holds the byte length of the following `wsnm` chunk. A fresh project's
    `"Default"` workspace name is 14 bytes in UTF-16-LE.
    """

    chunk_type: str = "wsns"
    value: int = u2_field(default=14)


@register("wsnm")
@define
class WsnmChunk(Chunk):
    """Workspace name (variable length, UTF-16-LE). Fresh projects use
    `"Default"`."""

    chunk_type: str = "wsnm"
    data: bytes = "Default".encode("utf-16-le")
