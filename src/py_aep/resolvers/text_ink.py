"""Ink bounds of a text layer, for `AVLayer.source_rect_at_time`.

After Effects measures a text layer's content as the tight box around its
glyphs' outlines. Rules measured on After Effects 2026 (point and box text
at sizes 8-500, several fonts, justifications, leading, tracking, stroke):

- Glyphs sit where the composer places them (see `text_composition`):
  point text keeps one line per paragraph, its first baseline on the layer
  origin, the next ones a line's leading below; box text breaks and
  baselines exactly as the box composer does, below the box's top inset.
  A left-justified line starts at its origin, a centered or right-justified
  one is shifted back by half or all of its advance width, without the
  tracking after its last character.
- A glyph's ink is its outline's bounds at the character's font size, a
  PostScript (CFF) outline scaled by a further `1031.25 / 1024` about the
  glyph origin (every CFF font measured, whatever its units per em;
  TrueType outlines are exact).
- A stroked character grows the box by the whole stroke width on every
  side, with or without `extents`.
- A layer without ink measures `0, 0, 0, 0`.

Anything the measurements did not cover raises `NotImplementedError`
rather than guess: text animators, text on a path, per-character 3D, faux
bold / italic, small or all caps, horizontal / vertical scale, trailing
spaces on a centered or right-justified line, and everything the box
composer itself refuses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from ..cos import cos_get, run_spans
from ..enums import ParagraphJustification
from . import text_composition as tc
from .shape_bounds import BoxAccumulator

if TYPE_CHECKING:
    from ..models.text.text_document import TextDocument

    # A glyph's outline bounds in font units, `None` for an empty glyph.
    _GlyphBounds = dict[str, "tuple[float, float, float, float] | None"]

_CFF_INK_SCALE = 1031.25 / 1024

_glyph_cache: dict[tuple[str, int], tuple[TTFont, bool, _GlyphBounds]] = {}


def _font_outlines(ps_name: str) -> tuple[TTFont, bool, _GlyphBounds]:
    """`(font, is_cff, outline bounds by glyph name)` for a PostScript name,
    cached; the bounds fill in as glyphs are measured."""
    path, face_index = tc._resolve_face(ps_name)
    key = (str(path), face_index)
    if key not in _glyph_cache:
        try:
            font = TTFont(str(path), fontNumber=face_index, lazy=True)
        except OSError as exc:
            raise NotImplementedError(
                f"font file for {ps_name!r} is unreadable: {path}"
            ) from exc
        _glyph_cache[key] = (font, "CFF " in font or "CFF2" in font, {})
    return _glyph_cache[key]


def _refuse(reason: str) -> NotImplementedError:
    return NotImplementedError(f"source_rect_at_time does not model text with {reason}")


def _check_styles(doc: TextDocument) -> None:
    for _start, _end, style in run_spans(doc._doc, "6", "6"):
        if style.get("2"):
            raise _refuse("faux bold")
        if style.get("3"):
            raise _refuse("faux italic")
        if int(style.get("12", 0)) != 0:
            raise _refuse("small or all caps")
        if float(style.get("6", 1.0)) != 1.0 or float(style.get("7", 1.0)) != 1.0:
            raise _refuse("horizontal or vertical scale")


def _stroke_width(style: dict) -> float:
    """The stroke a character's run draws, 0 when it has none (the width
    defaults to 1, as `TextDocument.stroke_width` reads it)."""
    if not style.get("57", False):
        return 0.0
    return float(style.get("63", 1.0))


def _line_ink(
    text: str,
    styles: list[tc._CharStyle],
    strokes: list[float],
    offset: int,
    origin_x: float,
    baseline: float,
    box: BoxAccumulator,
) -> None:
    """Grow `box` by the ink of one line whose pen starts at `origin_x`.

    Glyphs are placed by the composer's own shaping and advances
    (`text_composition`), the ones that break and justify the lines.
    """
    x = origin_x
    i = 0
    while i < len(text):
        style = styles[offset + i]
        key = style.stretch_key()
        j = i
        while j < len(text) and styles[offset + j].stretch_key() == key:
            j += 1
        stretch = text[i:j]
        buf, scale = tc._shape_glyphs(stretch, style)
        pens = []
        for advance in tc._glyph_advances(stretch, style, buf, scale):
            pens.append(x)
            x += advance
        font, is_cff, glyph_bounds = _font_outlines(style.font)
        ink_scale = scale * (_CFF_INK_SCALE if is_cff else 1.0)
        order = font.getGlyphOrder()
        glyph_set = font.getGlyphSet()
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = order[info.codepoint]
            if name not in glyph_bounds:
                pen = BoundsPen(glyph_set)
                glyph_set[name].draw(pen)
                glyph_bounds[name] = pen.bounds
            bounds = glyph_bounds[name]
            if bounds is None:
                continue
            x_min, y_min, x_max, y_max = bounds
            gx = pens[info.cluster] + pos.x_offset * scale
            gy = baseline - pos.y_offset * scale
            grow = strokes[offset + i + info.cluster]
            box.add(
                gx + x_min * ink_scale - grow,
                gy - y_max * ink_scale - grow,
                gx + x_max * ink_scale + grow,
                gy - y_min * ink_scale + grow,
            )
        i = j


def _justified_origin(
    justification: ParagraphJustification, width: float, text: str
) -> float:
    """Where a point-text line that is not left-justified starts its pen,
    from its advance width."""
    if text != text.rstrip(" "):
        raise _refuse("trailing spaces on a centered or right-justified line")
    if justification == ParagraphJustification.CENTER_JUSTIFY:
        return -width / 2
    if justification == ParagraphJustification.RIGHT_JUSTIFY:
        return -width
    raise _refuse(f"{justification.name} paragraphs")


def text_ink_rect(doc: TextDocument) -> dict[str, float]:
    """`sourceRectAtTime` of a text layer's document (see module rules).

    Raises:
        NotImplementedError: Outside the measured envelope (module
            docstring), or when a font is not installed.
    """
    raw = str(cos_get(doc._doc, "0", "0") or "")
    _check_styles(doc)
    try:
        tc._check_envelope(doc, raw)
        styles = tc._char_styles(doc, raw)
    except tc.CompositionUnsupported as exc:
        raise _refuse(str(exc)) from exc
    strokes: list[float] = []
    for start, end, style in run_spans(doc._doc, "6", "6"):
        strokes.extend([_stroke_width(style)] * (end - start))
    paragraph_styles = [style for _s, _e, style in run_spans(doc._doc, "5", "5")]
    box = BoxAccumulator()
    try:
        if doc.box_text_size is not None:
            _box_text_ink(doc, raw, styles, strokes, paragraph_styles, box)
        else:
            _point_text_ink(raw, styles, strokes, paragraph_styles, box)
    except tc.CompositionUnsupported as exc:
        raise _refuse(str(exc)) from exc
    return box.rect()


def _justification(paragraph_style: dict) -> ParagraphJustification:
    return ParagraphJustification.from_binary(int(paragraph_style.get("0", 0)))


def _point_text_ink(
    raw: str,
    styles: list[tc._CharStyle],
    strokes: list[float],
    paragraph_styles: list[dict],
    box: BoxAccumulator,
) -> None:
    body = raw[:-1] if raw.endswith("\r") else raw
    paragraphs = body.split("\r")
    if len(paragraph_styles) != len(paragraphs):
        raise _refuse("paragraph runs that do not cover the paragraphs")
    offset = 0
    baseline = 0.0
    for index, paragraph in enumerate(paragraphs):
        line_styles = styles[offset : offset + len(paragraph) + 1] or [styles[-1]]
        if index > 0:
            baseline += max(s.leading for s in line_styles)
        if paragraph:
            style = paragraph_styles[index]
            justification = _justification(style)
            origin = 0.0
            if justification != ParagraphJustification.LEFT_JUSTIFY:
                # AE justifies the line without the tracking after its last
                # character (measured on AE 2026: a centered line shifts by
                # half of `tracking * size / 1000`, a right-justified one by
                # all of it). A left-justified line needs no width, so its
                # glyphs are shaped once, by `_line_ink`.
                last = styles[offset + len(paragraph) - 1]
                width = (
                    tc._width(paragraph, styles, offset)
                    - last.tracking / 1000.0 * last.size
                )
                origin = _justified_origin(justification, width, paragraph)
            # A point-text paragraph is one line, its first: AE 2026 moves it
            # by the first-line indent whatever the justification, plus the
            # start indent when left-justified or minus the end indent when
            # right-justified (a centered line ignores both).
            origin += float(style.get("1", 0.0))
            if justification == ParagraphJustification.LEFT_JUSTIFY:
                origin += float(style.get("2", 0.0))
            elif justification == ParagraphJustification.RIGHT_JUSTIFY:
                origin -= float(style.get("3", 0.0))
            _line_ink(paragraph, styles, strokes, offset, origin, baseline, box)
        offset += len(paragraph) + 1


def _box_text_ink(
    doc: TextDocument,
    raw: str,
    styles: list[tc._CharStyle],
    strokes: list[float],
    paragraph_styles: list[dict],
    box: BoxAccumulator,
) -> None:
    composed = tc.compose_lines(doc)
    position = doc.box_text_pos
    if position is None:
        raise _refuse("a text box without a position")
    left, top = float(position[0]), float(position[1])
    inset = doc.box_inset_spacing
    # Map each character to its paragraph for the justification and indents.
    paragraph_of: list[int] = []
    for index, (start, end, _style) in enumerate(run_spans(doc._doc, "5", "5")):
        paragraph_of.extend([index] * (end - start))
    for (start, end), baseline in zip(composed.spans, composed.baselines):
        text = raw[start:end].rstrip("\r")
        if not text:
            continue
        style = paragraph_styles[paragraph_of[start]]
        if _justification(style) != ParagraphJustification.LEFT_JUSTIFY:
            raise _refuse("non-left-justified box text")
        first_line = start == 0 or raw[start - 1] == "\r"
        origin = left + inset + float(style.get("2", 0.0))
        if first_line:
            origin += float(style.get("1", 0.0))
        # The inset pads the box on every side, the top included (AE 2026:
        # an inset of 8 or 20 lowers the ink by exactly that much).
        _line_ink(text, styles, strokes, start, origin, top + inset + baseline, box)
