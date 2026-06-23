"""Outline SVG text into After Effects vector subpaths.

After Effects' own SVG importer drops `<text>`; py_aep renders it by outlining
each glyph with `fontTools` and converting the contours to the same cubic
[Subpath][py_aep.svg.types.Subpath]s the shape importer uses, so they flow
through the existing shape-layer builder unchanged.

A `<text>` is split into [TextRun][py_aep.svg.text.TextRun]s (the parent text
plus each `<tspan>`), laid out left-to-right by glyph advance width. Kerning,
bidirectional text, and complex-script shaping are out of scope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from .path_data import RawSubpath
from .shapes import cubics_to_subpath
from .transform import Affine

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from .path_data import CubicSeg
    from .types import Subpath

#: Parsed-font cache keyed by file path (one parse per font per process).
_font_cache: dict[str, Any] = {}


@dataclass
class TextRun:
    """One styled run of text within a `<text>` (the parent text or a `<tspan>`).

    Positioning follows SVG: `abs_x` / `abs_y` (when not `None`) reset the
    cursor; otherwise `dx` / `dy` offset it from the previous run's end.
    """

    text: str
    font_path: Path
    font_size: float
    letter_spacing: float = 0.0
    abs_x: float | None = None
    abs_y: float | None = None
    dx: float = 0.0
    dy: float = 0.0
    #: CSS `text-anchor` for this run's chunk (`None` = inherit the caller's).
    anchor: str | None = None
    #: Face index within a `.ttc` collection (0 for a single-face file).
    font_number: int = 0


def _load_font(path: Path, font_number: int = 0) -> Any:
    key = f"{path}#{font_number}"
    font = _font_cache.get(key)
    if font is None:
        font = TTFont(str(path), fontNumber=font_number, lazy=True)
        _font_cache[key] = font
    return font


class _CubicContourPen(BasePen):
    """Collect glyph contours as closed cubic `RawSubpath`s.

    `BasePen` converts TrueType quadratics (and any implied on-curve points)
    to cubics for us and decomposes composite glyphs, so only straight and
    cubic segments reach `_lineTo` / `_curveToOne`.
    """

    def __init__(self, glyph_set: Any) -> None:
        super().__init__(glyph_set)
        self.contours: list[RawSubpath] = []
        self._segs: list[CubicSeg] = []
        self._cur = (0.0, 0.0)
        self._start = (0.0, 0.0)

    def _moveTo(self, pt: Any) -> None:
        self._segs = []
        self._cur = pt
        self._start = pt

    def _lineTo(self, pt: Any) -> None:
        x0, y0 = self._cur
        x1, y1 = pt
        self._segs.append((x0, y0, x0, y0, x1, y1, x1, y1))
        self._cur = pt

    def _curveToOne(self, c1: Any, c2: Any, pt: Any) -> None:
        x0, y0 = self._cur
        self._segs.append((x0, y0, c1[0], c1[1], c2[0], c2[1], pt[0], pt[1]))
        self._cur = pt

    def _closePath(self) -> None:
        if self._cur != self._start:
            x0, y0 = self._cur
            x1, y1 = self._start
            self._segs.append((x0, y0, x0, y0, x1, y1, x1, y1))
        if self._segs:
            self.contours.append(RawSubpath(self._segs, True))
        self._segs = []

    def _endPath(self) -> None:
        if self._segs:
            self.contours.append(RawSubpath(self._segs, False))
        self._segs = []


def _glyph_contours(glyph_set: Any, glyph_name: str) -> list[RawSubpath]:
    pen = _CubicContourPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.contours


def _glyphs(font: Any, text: str) -> tuple[list[str | None], list[float], float, Any]:
    # `getBestCmap()` is None for a font with no Unicode cmap subtable (the
    # Windows symbol faces Wingdings/Webdings/Symbol/Marlett, and similar). Treat
    # it as empty so every char maps to no glyph and the run is dropped, matching
    # the "unresolved font is skipped" behaviour rather than crashing read_svg.
    cmap = font.getBestCmap() or {}
    glyph_set = font.getGlyphSet()
    units_per_em = font["head"].unitsPerEm
    names: list[str | None] = []
    advances: list[float] = []
    for ch in text:
        gname = cmap.get(ord(ch))
        names.append(gname)
        advances.append(glyph_set[gname].width if gname in glyph_set else 0.0)
    return names, advances, units_per_em, glyph_set


def _advance_width(
    run: TextRun, glyphs: tuple[list[str | None], list[float], float, Any]
) -> float:
    """Advance width of a run's text in user units (incl. letter-spacing)."""
    _, advances, units_per_em, _ = glyphs
    scale = run.font_size / units_per_em
    return sum(advances) * scale + run.letter_spacing * len(run.text)


def _outline_run(
    run: TextRun,
    pen_x: float,
    pen_y: float,
    ctm: Affine,
    glyphs: tuple[list[str | None], list[float], float, Any],
) -> tuple[list[Subpath], float]:
    """Outline one run starting at `(pen_x, pen_y)`; return (subpaths, end_x)."""
    names, advances, units_per_em, glyph_set = glyphs
    scale = run.font_size / units_per_em
    subpaths: list[Subpath] = []
    for gname, advance in zip(names, advances):
        if gname is not None and gname in glyph_set:
            # Scale + y-flip (font units are y-up) into user space at the pen
            # position, then apply the element transform.
            glyph_tf = ctm.multiply(Affine(a=scale, d=-scale, e=pen_x, f=pen_y))
            for raw in _glyph_contours(glyph_set, gname):
                sub = cubics_to_subpath(raw, glyph_tf)
                if sub is not None:
                    subpaths.append(sub)
        pen_x += advance * scale + run.letter_spacing
    return subpaths, pen_x


def outline_runs(
    runs: list[TextRun],
    origin_x: float,
    origin_y: float,
    ctm: Affine,
    anchor: str = "start",
) -> list[list[Subpath]]:
    """Outline `runs` into per-run subpath lists (parallel to `runs`).

    `origin_x` / `origin_y` are the `<text>` baseline anchor. Runs are grouped
    into SVG text chunks - a run carrying an absolute `x` starts a new chunk -
    and `text-anchor` (`start` / `middle` / `end`) is applied per chunk, taken
    from the run that starts the chunk (falling back to `anchor`). Each run's
    glyphs are measured once and reused for both the anchor width and the
    outline.
    """
    glyph_data = [
        _glyphs(_load_font(run.font_path, run.font_number), run.text) for run in runs
    ]
    widths = [_advance_width(run, gd) for run, gd in zip(runs, glyph_data)]
    result: list[list[Subpath]] = [[] for _ in runs]
    pen_x = origin_x
    pen_y = origin_y
    n = len(runs)
    i = 0
    while i < n:
        # The chunk runs from `i` up to (not including) the next absolute-x run.
        j = i + 1
        while j < n and runs[j].abs_x is None:
            j += 1
        first = runs[i]
        chunk_advance = sum(widths[k] + runs[k].dx for k in range(i, j))
        chunk_anchor = first.anchor or anchor
        shift = (
            chunk_advance / 2.0
            if chunk_anchor == "middle"
            else chunk_advance
            if chunk_anchor == "end"
            else 0.0
        )
        # An absolute x resets the cursor; otherwise the (first) chunk continues
        # from the running pen. The anchor shifts the whole chunk left.
        base_x = first.abs_x if first.abs_x is not None else pen_x
        pen_x = base_x - shift
        for k in range(i, j):
            run = runs[k]
            pen_x = pen_x + run.dx
            pen_y = run.abs_y if run.abs_y is not None else pen_y + run.dy
            subpaths, pen_x = _outline_run(run, pen_x, pen_y, ctm, glyph_data[k])
            result[k] = subpaths
        i = j
    return result


def _flatten_cubic(seg: CubicSeg, steps: int = 16) -> list[tuple[float, float]]:
    """Sample a cubic bezier into points (excluding the start point)."""
    x0, y0, c1x, c1y, c2x, c2y, x3, y3 = seg
    pts: list[tuple[float, float]] = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1.0 - t
        a, b, c, d = mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t
        pts.append(
            (a * x0 + b * c1x + c * c2x + d * x3, a * y0 + b * c1y + c * c2y + d * y3)
        )
    return pts


def _polyline(raw: RawSubpath) -> list[tuple[float, float]]:
    """Flatten a raw subpath's cubics into a polyline (path-local coords)."""
    segs = raw.segments
    if not segs:
        return []
    pts = [(segs[0][0], segs[0][1])]
    for seg in segs:
        pts.extend(_flatten_cubic(seg))
    return pts


def _arc_lengths(pts: list[tuple[float, float]]) -> list[float]:
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(
            cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        )
    return cum


def _point_at(
    pts: list[tuple[float, float]], cum: list[float], dist: float
) -> tuple[float, float, float]:
    """Point and tangent angle at arc-length `dist` along the polyline."""
    dist = max(0.0, min(dist, cum[-1]))
    i = 1
    while i < len(cum) - 1 and cum[i] < dist:
        i += 1
    x0, y0 = pts[i - 1]
    x1, y1 = pts[i]
    span = cum[i] - cum[i - 1]
    f = (dist - cum[i - 1]) / span if span > 1e-9 else 0.0
    return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, math.atan2(y1 - y0, x1 - x0)


def outline_text_path(
    text: str,
    path: list[RawSubpath],
    font_path: Path,
    font_size: float,
    ctm: Affine,
    *,
    font_number: int = 0,
    start_offset: float = 0.0,
    start_offset_frac: float | None = None,
    letter_spacing: float = 0.0,
) -> list[Subpath]:
    """Outline `text` laid along `path` (a `<textPath>`'s referenced geometry).

    Each glyph is placed with its advance midpoint at the corresponding
    arc-length along the (first subpath of the) path and rotated to the local
    tangent. Glyphs past the path end are dropped. `start_offset` is in user
    units; `start_offset_frac` (0-1) is the percentage form. The path's own
    transform is not applied (it is taken in the text's coordinate space).
    """
    if not path:
        return []
    pts = _polyline(path[0])
    if len(pts) < 2:
        return []
    cum = _arc_lengths(pts)
    total = cum[-1]
    names, advances, units_per_em, glyph_set = _glyphs(
        _load_font(font_path, font_number), text
    )
    scale = font_size / units_per_em

    dist = start_offset_frac * total if start_offset_frac is not None else start_offset
    subpaths: list[Subpath] = []
    for gname, advance in zip(names, advances):
        advance_user = advance * scale + letter_spacing
        mid = dist + advance_user / 2.0
        if gname is not None and gname in glyph_set and 0.0 <= mid <= total:
            px, py, angle = _point_at(pts, cum, mid)
            cos, sin = math.cos(angle), math.sin(angle)
            # place at path point, rotate to tangent, scale+y-flip, then shift
            # the glyph left by half its advance (font units) so its advance
            # midpoint sits on the path.
            glyph_tf = (
                ctm.multiply(Affine(e=px, f=py))
                .multiply(Affine(a=cos, b=sin, c=-sin, d=cos))
                .multiply(Affine(a=scale, d=-scale))
                .multiply(Affine(e=-advance / 2.0))
            )
            for raw in _glyph_contours(glyph_set, gname):
                sub = cubics_to_subpath(raw, glyph_tf)
                if sub is not None:
                    subpaths.append(sub)
        dist += advance_user
    return subpaths
