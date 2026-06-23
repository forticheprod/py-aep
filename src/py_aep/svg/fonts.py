"""Resolve an SVG `font-family` to an installed font file.

SVG text is rendered by outlining glyphs (see `svg.text`), which needs the
actual font file. This module discovers installed fonts from the standard OS
font directories (lazily, cached) and matches a CSS `font-family` plus
weight/style to a file, mirroring the discover-at-use pattern in `color.icc`.
Fonts are not bundled.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fontTools.ttLib import TTCollection, TTFont

if TYPE_CHECKING:
    from typing import Any

_FONT_SUFFIXES = (".ttf", ".otf", ".ttc")

#: family (lowercased) -> {subfamily (lowercased): (font file path, face index)}
#: The face index addresses a face within a TrueType Collection (.ttc); it is
#: 0 for a single-face .ttf/.otf.
_index: dict[str, dict[str, tuple[Path, int]]] | None = None

#: CSS generic families mapped to concrete fonts to try, in order. Used when a
#: requested family is not installed (an unknown family falls back to the
#: sans-serif chain, as a user agent would).
_GENERIC_FALLBACKS = {
    "sans-serif": (
        "arial",
        "helvetica",
        "helvetica neue",
        "liberation sans",
        "dejavu sans",
        "segoe ui",
        "noto sans",
        "verdana",
        "tahoma",
    ),
    "serif": (
        "times new roman",
        "georgia",
        "liberation serif",
        "dejavu serif",
        "noto serif",
        "cambria",
    ),
    "monospace": (
        "consolas",
        "courier new",
        "liberation mono",
        "dejavu sans mono",
        "noto sans mono",
        "menlo",
    ),
    "cursive": ("comic sans ms", "segoe script"),
    "fantasy": ("impact",),
    "system-ui": ("segoe ui", "arial", "helvetica", "dejavu sans"),
    "ui-sans-serif": ("segoe ui", "arial", "helvetica", "dejavu sans"),
}


def _font_dirs() -> list[Path]:
    """The standard OS font directories that exist on this machine."""
    dirs: list[Path] = []
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs.append(Path(windir) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        dirs += [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
        ]
    else:
        dirs += [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts",
            Path.home() / ".local" / "share" / "fonts",
        ]
    return [d for d in dirs if d.is_dir()]


def _name(font: Any, *ids: int) -> str | None:
    table = font.get("name")
    if table is None:
        return None
    for nid in ids:
        value = table.getDebugName(nid)
        if value:
            return str(value)
    return None


def _index_file(path: Path, idx: dict[str, dict[str, tuple[Path, int]]]) -> None:
    try:
        if path.suffix.lower() == ".ttc":
            fonts = list(TTCollection(str(path), lazy=True).fonts)
        else:
            fonts = [TTFont(str(path), fontNumber=0, lazy=True)]
    except Exception:
        # Corrupt/unsupported font file - skip it rather than fail discovery.
        return
    try:
        # A .ttc bundles several faces (e.g. cambria.ttc -> Cambria + Cambria
        # Math); index each by its own face number so a family that ships only
        # as a secondary face is still resolvable and loads the right face.
        for face, font in enumerate(fonts):
            # Typographic family (16) preferred over the legacy family (1); same
            # for the subfamily (17 over 2).
            family = _name(font, 16, 1)
            subfamily = _name(font, 17, 2) or "Regular"
            if family:
                idx.setdefault(family.lower(), {}).setdefault(
                    subfamily.lower(), (path, face)
                )
    finally:
        for font in fonts:
            font.close()


def _build_index() -> dict[str, dict[str, tuple[Path, int]]]:
    idx: dict[str, dict[str, tuple[Path, int]]] = {}
    for directory in _font_dirs():
        for path in directory.rglob("*"):
            if path.suffix.lower() in _FONT_SUFFIXES:
                _index_file(path, idx)
    return idx


def _pick(
    styles: dict[str, tuple[Path, int]], bold: bool, italic: bool
) -> tuple[Path, int]:
    """Choose the closest available face for the requested weight/style."""
    if bold and italic:
        order = ["bold italic", "bolditalic", "bold oblique", "bold", "italic"]
    elif bold:
        order = ["bold", "bold italic"]
    elif italic:
        order = ["italic", "oblique"]
    else:
        order = ["regular", "book", "roman"]
    for key in order:
        if key in styles:
            return styles[key]
    return next(iter(styles.values()))


def resolve_font(
    family: str, *, bold: bool = False, italic: bool = False
) -> tuple[Path, int] | None:
    """Resolve a CSS `font-family` value to an installed font face.

    `family` may be a comma-separated list (quotes stripped); the first
    installed family wins. Returns `(font file path, face index)` - the index
    selects a face within a `.ttc` collection (0 for a single-face file) - or
    `None` when no listed family is found.
    """
    global _index
    if _index is None:
        _index = _build_index()
    generic = None
    for raw in family.split(","):
        name = raw.strip().strip("'\"").lower()
        if not name:
            continue
        styles = _index.get(name)
        if styles:
            return _pick(styles, bold, italic)
        if generic is None and name in _GENERIC_FALLBACKS:
            generic = name
    # No requested family is installed: fall back to the generic chain (the
    # requested generic, or sans-serif for an unknown family).
    for candidate in _GENERIC_FALLBACKS.get(generic or "sans-serif", ()):
        styles = _index.get(candidate)
        if styles:
            return _pick(styles, bold, italic)
    return None
