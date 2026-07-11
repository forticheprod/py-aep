"""Recompose box-text lines the way AE's single-line Latin composer does.

Every rule here is fixture-verified against AE 26.3's own persisted
layout caches (37/37 matrix layers reproduce AE's exact breaks; see
`.claude/plans/text-recomposition.md` and
`samples/models/text/box_matrix.aep`):

* Measurement: HarfBuzz shaping per maximal same-style stretch with
  `liga`/`clig` disabled (AE's ligature default), advances accumulated
  per source cluster at `size / unitsPerEm`; tracking adds
  `tracking / 1000 x size` per character; horizontal scale multiplies
  advances; faux bold adds `0.027 x size` per glyph; small caps are
  synthesized (uppercase shaped, originally-lowercase advances x 0.7).
* Breaks: greedy word-fit at space groups only - hyphens are not break
  opportunities; a token wider than the line wraps at the character
  level. Trailing spaces ride along, excluded from the fit.
* Geometry: usable width = box width - 2 x inset - start/end indents;
  each paragraph's first line additionally subtracts the first-line
  indent.
* Vertical clip: keep lines while `baseline <= box height`, with the
  first baseline at `inset + ascender x size` (ascender = the lowercase
  'd' glyph height, CoolType's notion of ascent) and subsequent
  baselines adding the line leading (auto leading = 1.2 x size).

Anything outside the verified envelope raises
[CompositionUnsupported][] - the resolver refuses rather than guesses.
Besides the module-header features, that covers non-default box
vertical alignment / auto-fit / first-baseline alignment, paragraph
space before/after, disabled auto kerning, and case maps that change
the text length (all dirty-marked by the write engine but not modeled
here). Requires `uharfbuzz` for OpenType shaping; it is unavailable on
Python 3.7 (no wheels), where the resolver reports unsupported.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from ..cos import cos_get, run_spans
from ..enums import (
    BoxAutoFitPolicy,
    BoxFirstBaselineAlignment,
    BoxVerticalAlignment,
)
from ..svg.fonts import resolve_postscript

try:
    import uharfbuzz as hb  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised on Python 3.7 (no uharfbuzz wheels)
    hb = None

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from ..models.text.text_document import TextDocument

_AUTO_LEADING_FACTOR = 1.2
_FAUX_BOLD_ADVANCE = 0.027
_SMALL_CAPS_SCALE = 0.7


class CompositionUnsupported(ValueError):
    """The document is outside the verified composition envelope."""


class ComposedLines:
    """Result of a recomposition: clipped line spans + overflow state."""

    def __init__(
        self,
        spans: list[tuple[int, int]],
        baselines: list[float],
        overflow: bool,
    ) -> None:
        self.spans = spans
        self.baselines = baselines
        self.overflow = overflow


_hb_cache: dict[tuple[str, int], tuple[Any, int]] = {}
_ascender_cache: dict[tuple[str, int], float] = {}

# The font index is process-lifetime, so an indexed file can vanish
# (CoreSync eviction, uninstall) before its first shaping; those opens
# must refuse, not leak OS/HarfBuzz errors into innocuous reads.
_FONT_OPEN_ERRORS: tuple[type[BaseException], ...] = (OSError,)
if hb is not None and hasattr(hb, "HarfBuzzError"):
    _FONT_OPEN_ERRORS = (OSError, hb.HarfBuzzError)


def _resolve_face(ps_name: str) -> tuple[Path, int]:
    resolved = resolve_postscript(ps_name)
    if resolved is None:
        raise CompositionUnsupported(f"font {ps_name!r} is not installed")
    return resolved


def _hb_font(ps_name: str) -> tuple[Any, int]:
    path, face_index = _resolve_face(ps_name)
    key = (str(path), face_index)
    if key not in _hb_cache:
        try:
            blob = hb.Blob.from_file_path(str(path))
            face = hb.Face(blob, face_index)
        except _FONT_OPEN_ERRORS as exc:
            raise CompositionUnsupported(
                f"font file for {ps_name!r} is unreadable: {path}"
            ) from exc
        _hb_cache[key] = (hb.Font(face), face.upem)
    return _hb_cache[key]


def _ascender_ratio(ps_name: str) -> float:
    """CoolType's ascent as a fraction of the em: the lowercase 'd'
    glyph height (fixture-matched: Myriad 710/1000 while every table
    ascent says 750), falling back to `hhea` when 'd' is missing."""
    path, face_index = _resolve_face(ps_name)
    key = (str(path), face_index)
    if key not in _ascender_cache:
        try:
            font = TTFont(str(path), fontNumber=face_index, lazy=True)
        except OSError as exc:
            raise CompositionUnsupported(
                f"font file for {ps_name!r} is unreadable: {path}"
            ) from exc
        try:
            upem = font["head"].unitsPerEm
            ratio = font["hhea"].ascent / upem
            cmap = font.getBestCmap() or {}
            glyph_name = cmap.get(ord("d"))
            if glyph_name:
                glyph_set = font.getGlyphSet()
                pen = BoundsPen(glyph_set)
                glyph_set[glyph_name].draw(pen)
                if pen.bounds is not None:
                    ratio = pen.bounds[3] / upem
        finally:
            font.close()
        _ascender_cache[key] = ratio
    return _ascender_cache[key]


class _CharStyle:
    """Per-character composition inputs decoded from one style run."""

    __slots__ = ("font", "size", "tracking", "hscale", "fauxbold", "caps", "leading")

    def __init__(self, ps_name: str, style: dict[str, Any]) -> None:
        self.font = ps_name
        self.size = float(style.get("1", 36.0))
        self.tracking = float(style.get("8", 0.0))
        self.hscale = float(style.get("6", 1.0))
        self.fauxbold = bool(style.get("2", False))
        self.caps = int(style.get("12", 0))  # 0 normal, 1 small, 2 all
        if style.get("4", True):
            self.leading = _AUTO_LEADING_FACTOR * self.size
        else:
            self.leading = float(style.get("5", _AUTO_LEADING_FACTOR * self.size))

    def stretch_key(self) -> tuple:
        return (
            self.font,
            self.size,
            self.tracking,
            self.hscale,
            self.fauxbold,
            self.caps,
        )


def _check_envelope(doc: TextDocument, raw: str) -> None:
    """Raise [CompositionUnsupported][] outside the verified envelope."""
    if hb is None:
        raise CompositionUnsupported(
            "composition requires uharfbuzz, which is unavailable on Python 3.7"
        )
    orientation = cos_get(doc._cos_data, "0", "8", "0", 0, "0", "2", "1")
    if orientation not in (None, 0):
        raise CompositionUnsupported("vertical text")
    if "8" in (cos_get(doc._doc, "0") or {}):
        raise CompositionUnsupported("manual kerning")
    # Box-frame inputs the composer does not model: the matrix fixture
    # never swept them, so non-default values must refuse rather than
    # silently compose with top-aligned, ascender-based geometry.
    if doc.box_vertical_alignment is not BoxVerticalAlignment.TOP:
        raise CompositionUnsupported("box vertical alignment")
    if doc.box_auto_fit_policy is not BoxAutoFitPolicy.NONE:
        raise CompositionUnsupported("box auto-fit policy")
    if doc.box_first_baseline_alignment is not BoxFirstBaselineAlignment.ASCENT:
        raise CompositionUnsupported("box first-baseline alignment")
    if doc.box_first_baseline_alignment_minimum != 0.0:
        raise CompositionUnsupported("box first-baseline minimum")
    for char in raw:
        code = ord(char)
        if char == "\t":
            raise CompositionUnsupported("tab characters")
        if char == "\u00a0":
            raise CompositionUnsupported("no-break spaces")
        if code > 0xFFFF:
            raise CompositionUnsupported("non-BMP characters")
        if char != "\r" and unicodedata.bidirectional(char) in ("R", "AL", "AN"):
            raise CompositionUnsupported("right-to-left text")
        if unicodedata.combining(char):
            raise CompositionUnsupported("combining marks")
    for _start, _end, style in run_spans(doc._doc, "6", "6"):
        if style.get("18"):
            raise CompositionUnsupported("ligatures enabled")
        if float(style.get("36", 0.0)) != 0.0:
            raise CompositionUnsupported("tsume")
        kern_type = int(style.get("11", 1))
        if kern_type == 2:
            raise CompositionUnsupported("optical kerning")
        if kern_type != 1:
            # HarfBuzz keeps pair kerning on (matching AE's metric
            # default); a no-auto-kern run would measure kerned widths
            # for text AE lays out unkerned.
            raise CompositionUnsupported("auto kerning disabled")
        if style.get("52"):
            raise CompositionUnsupported("no-break attribute")
        if float(style.get("9", 0.0)) != 0.0:
            raise CompositionUnsupported("baseline shift")
        if int(style.get("13", 0)) != 0:
            raise CompositionUnsupported("super/subscript")
    for _start, _end, style in run_spans(doc._doc, "5", "5"):
        if style.get("29"):
            raise CompositionUnsupported("every-line composer")
        # NOTE auto-hyphenate (para key "9") is AE's DEFAULT and is inert
        # for the single-line composer: the explicit M_HYPHENATE matrix
        # layer still breaks greedily (long words char-wrap rather than
        # hyphenate), so it is deliberately NOT refused.
        if int(style.get("33", 0)) != 0:
            raise CompositionUnsupported("right-to-left paragraphs")
        if int(style.get("8", 0)) != 0:
            raise CompositionUnsupported("non-Roman leading type")
        if float(style.get("4", 0.0)) != 0.0 or float(style.get("5", 0.0)) != 0.0:
            # space_before/space_after shift baselines; the matrix never
            # swept them, so the composer does not model them.
            raise CompositionUnsupported("paragraph spacing")


def _char_styles(doc: TextDocument, raw: str) -> list[_CharStyle]:
    fonts = [f.post_script_name for f in doc._fonts]
    out: list[_CharStyle] = []
    for start, end, style in run_spans(doc._doc, "6", "6"):
        index = style.get("0")
        if not isinstance(index, int) or not 0 <= index < len(fonts):
            raise CompositionUnsupported("unresolvable font reference")
        out.extend([_CharStyle(fonts[index], style)] * (end - start))
    if len(out) != len(raw):
        raise CompositionUnsupported("style runs do not cover the text")
    return out


def _shape_stretch(text: str, style: _CharStyle) -> list[float]:
    """Per-character advances for one same-style stretch."""
    font, upem = _hb_font(style.font)
    shaped_text = text.upper() if style.caps in (1, 2) else text
    if len(shaped_text) != len(text):
        # e.g. eszett -> "SS": clusters no longer map 1:1 onto the
        # source characters, so per-character advances are undefined.
        raise CompositionUnsupported("case mapping changes the text length")
    buf = hb.Buffer()
    buf.add_str(shaped_text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"liga": False, "clig": False})
    scale = style.size / upem
    per_cluster = [0.0] * len(shaped_text)
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        if info.codepoint == 0:
            raise CompositionUnsupported(
                f"glyph missing from {style.font!r} for a character in {text!r}"
            )
        per_cluster[info.cluster] += pos.x_advance * scale
    advances: list[float] = []
    for i, advance in enumerate(per_cluster):
        if style.fauxbold:
            advance += _FAUX_BOLD_ADVANCE * style.size
        if style.caps == 1 and text[i].islower():
            advance *= _SMALL_CAPS_SCALE
        advances.append(advance * style.hscale + style.tracking / 1000.0 * style.size)
    return advances


def _advances(text: str, styles: list[_CharStyle], offset: int) -> list[float]:
    """Per-character advances for `text` at `offset` in the document."""
    out: list[float] = []
    i = 0
    while i < len(text):
        key = styles[offset + i].stretch_key()
        j = i
        while j < len(text) and styles[offset + j].stretch_key() == key:
            j += 1
        out.extend(_shape_stretch(text[i:j], styles[offset + i]))
        i = j
    return out


def _width(text: str, styles: list[_CharStyle], offset: int) -> float:
    return sum(_advances(text, styles, offset))


def _break_paragraph(
    paragraph: str,
    styles: list[_CharStyle],
    offset: int,
    limit: float,
    first_limit: float,
) -> list[int]:
    """Greedy word-fit; returns the length of each produced line.

    Each candidate prefix is re-shaped from scratch (quadratic in line
    width). Deliberate: prefix sums over one full-paragraph shape
    diverge from shaped-substring widths by up to ~1 px at the cut
    boundary (cross-boundary kern/contextual positioning, measured on
    M_HYPHENS), and only per-candidate shaping is fixture-proven
    against AE's breaks. Do not swap in prefix sums without re-running
    the box_matrix parity suite on width-critical fixtures.
    """
    if not paragraph:
        # An empty paragraph still composes to one (empty) line; the
        # caller extends it over the paragraph's `\r`.
        return [0]
    lengths: list[int] = []
    rest = paragraph
    rest_offset = offset
    current_limit = first_limit
    while rest:
        take = 0
        while take < len(rest):
            next_space = rest.find(" ", take)
            candidate_end = len(rest) if next_space == -1 else next_space
            candidate = rest[:candidate_end].rstrip(" ")
            if _width(candidate, styles, rest_offset) > current_limit:
                break
            while candidate_end < len(rest) and rest[candidate_end] == " ":
                candidate_end += 1
            take = candidate_end
            if next_space == -1:
                break
        if take == 0:
            # Token wider than the line: wrap at the character level.
            take = 1
            while (
                take < len(rest)
                and rest[take] != " "
                and _width(rest[: take + 1], styles, rest_offset) <= current_limit
            ):
                take += 1
        lengths.append(take)
        rest = rest[take:]
        rest_offset += take
        current_limit = limit
    return lengths


def compose_lines(doc: TextDocument) -> ComposedLines:
    """Recompose a box-text document's lines exactly as AE would.

    Returns the clipped line spans (UTF-16 == code-point indices inside
    the envelope; the final span covers the raw terminator like AE's
    cache), their baselines, and whether the text overflows the box.

    Raises:
        CompositionUnsupported: When the document uses any feature
            outside the verified envelope, a font is not installed, or
            `uharfbuzz` is unavailable (Python 3.7).
    """
    raw = str(cos_get(doc._doc, "0", "0") or "")
    box_size = doc.box_text_size
    if box_size is None:
        raise CompositionUnsupported("not a box-text document")
    _check_envelope(doc, raw)
    styles = _char_styles(doc, raw)
    inset = doc.box_inset_spacing
    width, height = float(box_size[0]), float(box_size[1])

    para_geo: list[tuple[float, float]] = []
    for _start, _end, style in run_spans(doc._doc, "5", "5"):
        base = (
            width - 2 * inset - float(style.get("2", 0.0)) - float(style.get("3", 0.0))
        )
        para_geo.append((base, base - float(style.get("1", 0.0))))

    body = raw[:-1] if raw.endswith("\r") else raw
    paragraphs = body.split("\r")
    if len(para_geo) != len(paragraphs):
        # AE stores exactly one paragraph run per paragraph (and
        # _splice_text preserves that); a mismatch means a malformed
        # document whose geometry we must not guess.
        raise CompositionUnsupported("paragraph runs do not cover the paragraphs")

    spans: list[tuple[int, int]] = []
    offset = 0
    for index, paragraph in enumerate(paragraphs):
        limit, first_limit = para_geo[index]
        lengths = _break_paragraph(paragraph, styles, offset, limit, first_limit)
        for line_no, length in enumerate(lengths):
            end = offset + length
            if line_no == len(lengths) - 1:
                end += 1  # the paragraph's \r (or the raw terminator)
            spans.append((offset, end))
            offset = end

    # The inset shrinks the usable width but does NOT shift the first
    # baseline (probed M_INSET8); faux bold raises the ascent by half
    # its advance bump (probed M_FAUXB).
    baselines: list[float] = []
    y = 0.0
    for line_no, (start, end) in enumerate(spans):
        line_styles = styles[start : min(end, len(styles))] or [styles[-1]]
        if line_no == 0:
            y += max(
                (
                    _ascender_ratio(s.font)
                    + (_FAUX_BOLD_ADVANCE / 2 if s.fauxbold else 0.0)
                )
                * s.size
                for s in line_styles
            )
        else:
            y += max(s.leading for s in line_styles)
        baselines.append(y)

    kept = sum(1 for b in baselines if b <= height)
    return ComposedLines(spans[:kept], baselines[:kept], kept < len(spans))


def calibrate(
    doc: TextDocument,
    cached_spans: list[tuple[int, int]],
    cached_baselines: list[float | None],
) -> bool:
    """Verify the composer against the document's own persisted cache.

    Composes the CURRENT (still clean) text and compares line spans and
    baselines with what AE saved. Success proves the installed fonts
    and every composition rule match AE's composer for this document,
    making post-mutation recomposition trustworthy; any mismatch (or an
    envelope refusal) means the composer must not be used for it.
    """
    try:
        composed = compose_lines(doc)
    except CompositionUnsupported:
        return False
    if composed.spans != list(cached_spans):
        return False
    for computed, cached in zip(composed.baselines, cached_baselines):
        if cached is None:
            continue
        # TrueType ascenders reproduce AE within ~1.4 font units
        # (<= 0.03 px at 36 pt); breaks are unaffected, only a box
        # height landing inside that sliver could mis-clip.
        if abs(computed - float(cached)) > 0.05:
            return False
    return True
