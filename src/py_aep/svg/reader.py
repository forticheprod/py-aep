"""Flatten an SVG file into absolute-coordinate drawables.

`read_svg` walks the document depth-first, accumulating transforms and
inherited styles, expands `<use>` references, drops SMIL animation and
non-rendered content, and emits one [SvgDrawable][py_aep.svg.types.SvgDrawable]
per leaf shape in document (paint) order - mirroring what After Effects
produces for an SVG imported as cropped-comp layers.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Union
from xml.etree.ElementTree import Element, fromstring

from ._util import local_name, parse_number, parse_ratio
from .colors import parse_color
from .document import canvas
from .errors import UnsupportedSVGError
from .fonts import resolve_font
from .gradients import GradientDef, collect_gradients, resolve_gradient
from .shapes import cubics_to_subpath, element_subpaths
from .style import CssRule, parse_css, resolve_properties
from .text import TextRun, outline_runs, outline_text_path
from .transform import Affine, parse_transform
from .types import (
    GradientPaint,
    SolidPaint,
    StrokeStyle,
    Subpath,
    SvgDocument,
    SvgDrawable,
)

if TYPE_CHECKING:
    Bbox = tuple[float, float, float, float]
    Paint = Union[SolidPaint, GradientPaint, None]

_DRAWABLE_TAGS = frozenset(
    {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
)
_CONTAINER_TAGS = frozenset({"g", "a", "svg"})
# Non-rendered or definition-only elements skipped without recursing into
# them for drawables (gradients/symbols are resolved on demand elsewhere).
_SKIP_TAGS = frozenset(
    {
        "defs",
        "symbol",
        "title",
        "desc",
        "metadata",
        "style",
        "script",
        "linearGradient",
        "radialGradient",
        "pattern",
        "clipPath",
        "mask",
        "filter",
        "marker",
        "animate",
        "animateTransform",
        "animateMotion",
        "animateColor",
        "set",
        "mpath",
        "switch",
        "foreignObject",
    }
)
# Unsupported as standalone elements: `<tspan>`/`<textPath>` outside a `<text>`
# (invalid SVG); within a `<text>`, _visit_text renders both. Raster `<image>` is
# handled in _visit (skipped with a warning - it is not yet rendered).
_UNSUPPORTED_TAGS = frozenset({"tspan", "textPath"})

# Bound on container nesting (<g>/<svg>/<use>) so a pathologically deep
# document raises a clean UnsupportedSVGError instead of a RecursionError.
# Each level costs ~2 Python frames (walk -> _visit -> walk), so this stays
# well under the interpreter's ~1000-frame recursion limit; no real SVG nests
# anywhere near this deep.
_MAX_SVG_DEPTH = 250

_CAP = {"butt": 1, "round": 2, "square": 3}
_JOIN = {"miter": 1, "round": 2, "bevel": 3}
_URL_RE = re.compile(r"url\(\s*#([^)\s]+)\s*\)")


def read_svg(source: str | os.PathLike[str] | bytes) -> SvgDocument:
    """Parse an SVG file into a flattened [SvgDocument][py_aep.svg.types.SvgDocument].

    Args:
        source: Path to an `.svg` file, or its raw bytes/markup.

    Returns:
        The flattened document (canvas size + drawables).

    Raises:
        UnsupportedSVGError: For SVG features py_aep cannot import.
    """
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    elif isinstance(source, str) and source.lstrip().startswith("<"):
        data = source.encode("utf-8")
    else:
        data = Path(os.fspath(source)).read_bytes()
    root = fromstring(data)
    if local_name(root.tag) != "svg":
        raise UnsupportedSVGError(
            f"Root element is <{local_name(root.tag)}>, not <svg>"
        )

    width, height, root_tf = canvas(root)
    reader = _Reader(root)
    # The root <svg>'s own presentation attributes (e.g. fill="none") form
    # the inherited base for all children.
    root_style = resolve_properties({}, "svg", root.attrib, reader._css)
    root_tf = root_tf.multiply(parse_transform(root.get("transform", "")))
    reader._root_ctm = root_tf
    reader._viewport = (width, height)
    root_opacity = parse_ratio(root_style.get("opacity"), 1.0)
    drawables = reader.walk(root, root_tf, root_style, root_opacity)
    return SvgDocument(width=width, height=height, drawables=drawables)


class _Reader:
    def __init__(self, root: Element) -> None:
        self._gradients: dict[str, GradientDef] = collect_gradients(root)
        self._css: list[CssRule] = self._collect_css(root)
        self._by_id: dict[str, Element] = {}
        for elem in root.iter():
            eid = elem.get("id")
            if eid:
                self._by_id[eid] = elem
        self._root = root
        # Child -> parent map for reconstructing a by-id element's accumulated
        # transform (ElementTree has no parent links). Built lazily on first
        # _element_ctm call - only <textPath> needs it, so the common SVG with
        # no text path never pays for the whole-tree walk. `_root_ctm` is the
        # base (viewBox + root transform), set by read_svg before the walk.
        self._parents: dict[Element, Element] | None = None
        self._root_ctm: Affine = Affine()
        self._viewport: tuple[float, float] = (0.0, 0.0)
        self._use_stack: list[str] = []

    @staticmethod
    def _collect_css(root: Element) -> list[CssRule]:
        rules: list[CssRule] = []
        for elem in root.iter():
            if local_name(elem.tag) == "style" and elem.text:
                rules.extend(parse_css(elem.text))
        return rules

    def _element_ctm(self, elem: Element) -> Affine:
        """Accumulated transform of `elem`: the root base (viewBox + root
        transform) composed with every ancestor's `transform` down to and
        including `elem`'s own."""
        if self._parents is None:
            self._parents = {
                child: parent for parent in self._root.iter() for child in parent
            }
        chain: list[Element] = []
        cur: Element | None = elem
        while cur is not None and cur in self._parents:
            chain.append(cur)
            cur = self._parents.get(cur)
        ctm = self._root_ctm
        for node in reversed(chain):
            ctm = ctm.multiply(parse_transform(node.get("transform", "")))
        return ctm

    def walk(
        self,
        elem: Element,
        ctm: Affine,
        parent_style: dict[str, str],
        opacity: float,
        depth: int = 0,
    ) -> list[SvgDrawable]:
        if depth > _MAX_SVG_DEPTH:
            raise UnsupportedSVGError("SVG container nesting too deep")
        out: list[SvgDrawable] = []
        for child in elem:
            self._visit(child, ctm, parent_style, opacity, out, depth)
        return out

    def _visit(
        self,
        elem: Element,
        ctm: Affine,
        parent_style: dict[str, str],
        opacity: float,
        out: list[SvgDrawable],
        depth: int = 0,
    ) -> None:
        tag = local_name(elem.tag)
        if tag in _SKIP_TAGS:
            return
        if tag == "image":
            # Raster <image> is not rendered (AE drops it too). Unlike the
            # silent _SKIP_TAGS, warn once - it is visible content the author
            # expected to appear.
            warnings.warn(
                "SVG <image> elements are not imported (skipped).", stacklevel=2
            )
            return
        if tag in _UNSUPPORTED_TAGS:
            raise UnsupportedSVGError(f"Unsupported element: <{tag}>")

        style = resolve_properties(parent_style, tag, elem.attrib, self._css)
        if style.get("display") == "none":
            return
        local_tf = ctm.multiply(parse_transform(elem.get("transform", "")))
        # `opacity` is a non-inherited compositing factor; AE flattens an SVG
        # group/element opacity by multiplying it into the leaf's paint
        # opacity, so accumulate it down the tree and fold it into the leaf.
        eff_opacity = opacity * parse_ratio(style.get("opacity"), 1.0)

        if tag in _CONTAINER_TAGS:
            out.extend(self.walk(elem, local_tf, style, eff_opacity, depth + 1))
            return
        if tag == "use":
            self._visit_use(elem, local_tf, style, eff_opacity, out, depth)
            return
        if tag == "text":
            self._visit_text(elem, local_tf, style, eff_opacity, out)
            return
        if tag in _DRAWABLE_TAGS:
            drawable = self._build_drawable(tag, elem, local_tf, style, eff_opacity)
            if drawable is not None:
                out.append(drawable)
            return
        # Unknown element: ignore (forward-compatible) but recurse in case
        # it wraps drawables.
        out.extend(self.walk(elem, local_tf, style, eff_opacity, depth + 1))

    def _visit_use(
        self,
        elem: Element,
        ctm: Affine,
        style: dict[str, str],
        opacity: float,
        out: list[SvgDrawable],
        depth: int = 0,
    ) -> None:
        ref = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href")
        if not ref or not ref.startswith("#"):
            return
        target_id = ref[1:]
        if target_id in self._use_stack:
            raise UnsupportedSVGError(f"Recursive <use> reference: #{target_id}")
        target = self._by_id.get(target_id)
        if target is None:
            return
        x = parse_number(elem.get("x", "0"))
        y = parse_number(elem.get("y", "0"))
        use_tf = ctm.multiply(Affine(e=x, f=y))
        self._use_stack.append(target_id)
        try:
            t_tag = local_name(target.tag)
            if t_tag in ("symbol", "svg"):
                out.extend(self.walk(target, use_tf, style, opacity, depth + 1))
            else:
                self._visit(target, use_tf, style, opacity, out, depth)
        finally:
            self._use_stack.pop()

    def _visit_text(
        self,
        elem: Element,
        ctm: Affine,
        style: dict[str, str],
        opacity: float,
        out: list[SvgDrawable],
    ) -> None:
        # A <text> is outlined into vector shapes: its direct text and each
        # <tspan> become a run (carrying its own font/fill), laid out
        # left-to-right. <textPath> children are dispatched to _add_text_path;
        # a run with an absolute x starts a new anchor chunk (outline_runs).
        if style.get("visibility") == "hidden":
            return
        runs: list[tuple[TextRun, dict[str, str]]] = []
        if elem.text and elem.text.strip():
            run = self._make_run(elem.text, style, None)
            if run is not None:
                runs.append((run, style))
        for child in elem:
            ctag = local_name(child.tag)
            if ctag == "tspan":
                cstyle = resolve_properties(style, "tspan", child.attrib, self._css)
                if child.text and child.text.strip():
                    run = self._make_run(child.text, cstyle, child)
                    if run is not None:
                        runs.append((run, cstyle))
            elif ctag == "textPath":
                self._add_text_path(elem, child, style, opacity, out)
            # Text after a child element (its `tail`) belongs to the parent.
            tail = child.tail
            if tail and tail.strip():
                run = self._make_run(tail, style, None)
                if run is not None:
                    runs.append((run, style))
            elif tail and not tail.strip() and runs:
                # A whitespace-only tail between two runs (e.g.
                # `<tspan>foo</tspan> <tspan>bar</tspan>`) is a significant SVG
                # space that collapses to one space. Fold it into the preceding
                # run so the pen advances by a space glyph before the next run,
                # rather than laying the runs out flush. A leading whitespace-
                # only tail (no prior run) is document-leading and dropped.
                last_run = runs[-1][0]
                if not last_run.text.endswith(" "):
                    last_run.text += " "
        if not runs:
            return
        # Trim the whole sequence's leading/trailing whitespace (each run's
        # internal whitespace was already collapsed in _make_run); a single
        # space between runs stays significant.
        runs[0][0].text = runs[0][0].text.lstrip(" ")
        runs[-1][0].text = runs[-1][0].text.rstrip(" ")
        origin_x = parse_number(elem.get("x", "0"))
        origin_y = parse_number(elem.get("y", "0"))
        anchor = (style.get("text-anchor") or "start").strip()
        per_run = outline_runs([r for r, _ in runs], origin_x, origin_y, ctm, anchor)
        for (_, run_style), subpaths in zip(runs, per_run):
            if not subpaths:
                continue
            out.append(self._emit(subpaths, run_style, ctm, elem.get("id"), opacity))

    def _make_run(
        self, text: str, style: dict[str, str], elem: Element | None
    ) -> TextRun | None:
        # Font is resolved from the cascaded/inherited style; position
        # attributes (x/y/dx/dy) come from the run's own element.
        text = _collapse_ws(text)
        family = style.get("font-family", "sans-serif")
        weight = (style.get("font-weight") or "").strip()
        font_style = (style.get("font-style") or "").strip()
        bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 600)
        italic = font_style in ("italic", "oblique")
        resolved = resolve_font(family, bold=bold, italic=italic)
        if resolved is None:
            return None
        font_path, font_number = resolved
        abs_x = (
            parse_number(elem.get("x")) if elem is not None and elem.get("x") else None
        )
        abs_y = (
            parse_number(elem.get("y")) if elem is not None and elem.get("y") else None
        )
        dx = (
            parse_number(elem.get("dx")) if elem is not None and elem.get("dx") else 0.0
        )
        dy = (
            parse_number(elem.get("dy")) if elem is not None and elem.get("dy") else 0.0
        )
        return TextRun(
            text=text,
            font_path=font_path,
            font_number=font_number,
            font_size=parse_number(style.get("font-size") or "16"),
            letter_spacing=parse_number(style.get("letter-spacing") or "0"),
            abs_x=abs_x,
            abs_y=abs_y,
            dx=dx,
            dy=dy,
            anchor=(style.get("text-anchor") or "").strip() or None,
        )

    def _add_text_path(
        self,
        text_elem: Element,
        tp_elem: Element,
        parent_style: dict[str, str],
        opacity: float,
        out: list[SvgDrawable],
    ) -> None:
        # A <textPath> lays its text along a referenced path's geometry, in the
        # path's own coordinate space (its accumulated transform).
        href = tp_elem.get("href") or tp_elem.get("{http://www.w3.org/1999/xlink}href")
        if not href or not href.startswith("#"):
            return
        target = self._by_id.get(href[1:])
        if target is None or not (tp_elem.text and tp_elem.text.strip()):
            return
        ctm = self._element_ctm(target)
        style = resolve_properties(parent_style, "textPath", tp_elem.attrib, self._css)
        run = self._make_run(tp_elem.text, style, None)
        if run is None:
            return
        try:
            path = element_subpaths(local_name(target.tag), target.attrib)
        except UnsupportedSVGError:
            return  # referenced element is not a path/basic shape
        raw_off = (tp_elem.get("startOffset") or "0").strip()
        if raw_off.endswith("%"):
            off_abs, off_frac = 0.0, parse_number(raw_off) / 100.0
        else:
            off_abs, off_frac = parse_number(raw_off), None
        subpaths = outline_text_path(
            _collapse_ws(tp_elem.text).strip(),
            path,
            run.font_path,
            run.font_size,
            ctm,
            font_number=run.font_number,
            start_offset=off_abs,
            start_offset_frac=off_frac,
            letter_spacing=run.letter_spacing,
        )
        if not subpaths:
            return
        out.append(self._emit(subpaths, style, ctm, text_elem.get("id"), opacity))

    def _build_drawable(
        self,
        tag: str,
        elem: Element,
        ctm: Affine,
        style: dict[str, str],
        opacity: float,
    ) -> SvgDrawable | None:
        raws = element_subpaths(tag, elem.attrib)
        subpaths: list[Subpath] = []
        for raw in raws:
            sp = cubics_to_subpath(raw, ctm)
            if sp is not None:
                subpaths.append(sp)
        if not subpaths:
            return None
        if style.get("visibility") == "hidden":
            return None

        # `opacity` already includes this element's own opacity (folded in by
        # the caller alongside every ancestor's), so use it directly.
        return self._emit(subpaths, style, ctm, elem.get("id"), opacity)

    def _emit(
        self,
        subpaths: list[Subpath],
        style: dict[str, str],
        ctm: Affine,
        name: str | None,
        opacity: float,
    ) -> SvgDrawable:
        bbox = _bbox(subpaths)
        return SvgDrawable(
            subpaths=subpaths,
            fill=self._paint(style.get("fill", "black"), bbox, ctm),
            stroke=self._stroke(style, bbox, ctm),
            name=name,
            opacity=opacity,
        )

    def _paint(self, value: str | None, bbox: Bbox, ctm: Affine) -> Paint:
        if value is None:
            return None
        value = value.strip()
        if value == "none":
            return None
        url = _URL_RE.match(value)
        if url:
            gd = self._gradients.get(url.group(1))
            if gd is not None and gd.stops:
                return resolve_gradient(gd, bbox, ctm, self._viewport)
            # Unknown paint server (pattern, missing gradient): no paint.
            return None
        color = parse_color(value)
        if color is None:
            return None
        # AE's SVG cropped import ignores the fill-opacity/stroke-opacity
        # presentation attributes (verified against AE 2026); only the
        # element/group `opacity` (applied by the builder) and the paint's
        # own color alpha affect the imported opacity.
        return SolidPaint(color=color)

    def _stroke(
        self, style: dict[str, str], bbox: Bbox, ctm: Affine
    ) -> StrokeStyle | None:
        paint = self._paint(style.get("stroke", "none"), bbox, ctm)
        if paint is None:
            return None
        width = parse_number(style.get("stroke-width", "1")) * ctm.mean_scale
        if width <= 0:
            return None
        cap = _CAP.get((style.get("stroke-linecap") or "").strip(), 1)
        join = _JOIN.get((style.get("stroke-linejoin") or "").strip(), 1)
        miter = parse_number(style.get("stroke-miterlimit", "4"))
        dashes = [
            parse_number(t) * ctm.mean_scale
            for t in re.split(r"[,\s]+", (style.get("stroke-dasharray") or "").strip())
            if t and t != "none"
        ]
        return StrokeStyle(
            paint=paint,
            width=width,
            cap=cap,
            join=join,
            miter_limit=miter,
            dashes=dashes,
        )


def _bbox(subpaths: list[Subpath]) -> Bbox:
    xs: list[float] = []
    ys: list[float] = []
    for sp in subpaths:
        for vx, vy in sp.vertices:
            xs.append(vx)
            ys.append(vy)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


_WS_RE = re.compile(r"\s+")


def _collapse_ws(text: str) -> str:
    """Collapse internal whitespace runs (incl. newlines/tabs) to one space.

    SVG default white-space handling renders a run of source whitespace as a
    single space; without this, the indentation of a pretty-printed `<text>`
    is laid out as leading glyph advances. Edge spaces are kept here and
    trimmed once across the whole run sequence by the caller.
    """
    return _WS_RE.sub(" ", text)
