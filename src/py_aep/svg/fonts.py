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
    from typing import Any, Iterator

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


def _adobe_font_dirs() -> list[Path]:
    """Adobe CoreSync (Creative Cloud) font caches, when present.

    Activated Adobe fonts live here as suffix-less OpenType files; AE
    resolves text-layer fonts against them.
    """
    dirs: list[Path] = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            dirs.append(
                Path(appdata) / "Adobe" / "CoreSync" / "plugins" / "livetype" / "r"
            )
    elif sys.platform == "darwin":
        dirs.append(
            Path.home()
            / "Library"
            / "Application Support"
            / "Adobe"
            / "CoreSync"
            / "plugins"
            / "livetype"
            / ".r"
        )
    return [d for d in dirs if d.is_dir()]


#: PostScript name (name ID 6, lowercased) ->
#: (font file path, face index, version string from name ID 5 or None).
_ps_index: dict[str, tuple[Path, int, str | None]] | None = None


def _iter_faces(path: Path) -> Iterator[tuple[int, TTFont]]:
    """Yield `(face index, opened font)` for each face in a font file,
    closing every face afterwards.

    Corrupt/unsupported files yield nothing rather than fail discovery.
    """
    try:
        if path.suffix.lower() == ".ttc":
            fonts = list(TTCollection(str(path), lazy=True).fonts)
        else:
            fonts = [TTFont(str(path), fontNumber=0, lazy=True)]
    except Exception:
        return
    try:
        yield from enumerate(fonts)
    finally:
        for font in fonts:
            font.close()


def _index_postscript(path: Path, idx: dict[str, tuple[Path, int, str | None]]) -> None:
    for face, font in _iter_faces(path):
        ps_name = _name(font, 6)
        if not ps_name:
            continue
        key = ps_name.lower()
        existing = idx.get(key)
        if existing is None:
            idx[key] = (path, face, _name(font, 5))
        elif existing[2] is None:
            # The first-seen face resolves the name, but a later
            # duplicate can still supply the version string it lacked
            # (the pre-index code only ever stored truthy versions).
            version = _name(font, 5)
            if version:
                idx[key] = (existing[0], existing[1], version)


def _walk_font_files() -> Iterator[Path]:
    """Yield every font file under the OS font directories. Both index
    builders (`_build_index`, `_postscript_index`) walk the same tree."""
    for directory in _font_dirs():
        for path in directory.rglob("*"):
            if path.suffix.lower() in _FONT_SUFFIXES:
                yield path


def _postscript_index() -> dict[str, tuple[Path, int, str | None]]:
    """The lazily built, cached PostScript-name index (one walk over the
    OS and Adobe CoreSync font directories)."""
    global _ps_index
    if _ps_index is None:
        idx: dict[str, tuple[Path, int, str | None]] = {}
        for path in _walk_font_files():
            _index_postscript(path, idx)
        for directory in _adobe_font_dirs():
            for path in directory.rglob("*"):
                if path.is_file():
                    _index_postscript(path, idx)
        _ps_index = idx
    return _ps_index


def resolve_postscript(post_script_name: str) -> tuple[Path, int] | None:
    """Resolve a PostScript name (name ID 6) to an installed font face.

    Returns `(font file path, face index)` - the index selects a face
    within a `.ttc` collection - or `None` when no matching font is
    installed. This mirrors how AE's text engine identifies fonts, so
    the composed-line resolver uses it for measurement.
    """
    entry = _postscript_index().get(post_script_name.strip().lower())
    if entry is None:
        return None
    return entry[0], entry[1]


def font_version_string(post_script_name: str) -> str | None:
    """The installed font's version string (name ID 5) for a PostScript
    name, or `None` when no matching font is installed.

    AE stamps this host-resolved string on font entries it registers in
    a text document and on the used-font records (probed via the
    `W_FONT` write fixture); matching it keeps py-written files
    byte-identical to AE's output on the same machine.
    """
    entry = _postscript_index().get(post_script_name.strip().lower())
    if entry is None:
        return None
    return entry[2]


def _index_file(path: Path, idx: dict[str, dict[str, tuple[Path, int]]]) -> None:
    # A .ttc bundles several faces (e.g. cambria.ttc -> Cambria + Cambria
    # Math); index each by its own face number so a family that ships only
    # as a secondary face is still resolvable and loads the right face.
    for face, font in _iter_faces(path):
        # Typographic family (16) preferred over the legacy family (1); same
        # for the subfamily (17 over 2).
        family = _name(font, 16, 1)
        subfamily = _name(font, 17, 2) or "Regular"
        if family:
            idx.setdefault(family.lower(), {}).setdefault(
                subfamily.lower(), (path, face)
            )


def _build_index() -> dict[str, dict[str, tuple[Path, int]]]:
    idx: dict[str, dict[str, tuple[Path, int]]] = {}
    for path in _walk_font_files():
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


def resolve_font_exact(family: str) -> tuple[Path, int] | None:
    """Resolve a single family name to an installed font face, with NO
    generic fallback.

    Unlike `resolve_font`, an uninstalled family returns `None` instead
    of degrading to the sans-serif chain; used where substituting a
    different font would be wrong (e.g. reading variable-font axes).
    Returns `(font file path, face index)`.
    """
    global _index
    if _index is None:
        _index = _build_index()
    styles = _index.get(family.strip().strip("'\"").lower())
    if not styles:
        return None
    return _pick(styles, False, False)


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
