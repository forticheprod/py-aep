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
from pathlib import Path
from typing import TYPE_CHECKING, Union
from xml.etree.ElementTree import Element, fromstring

from ._util import NUMBER_RE, clamp01, local_name
from .colors import parse_color
from .document import canvas
from .errors import UnsupportedSVGError
from .gradients import GradientDef, collect_gradients, resolve_gradient
from .shapes import cubics_to_subpath, element_subpaths
from .style import CssRule, parse_css, resolve_properties
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
# Elements that are valid SVG content but py_aep cannot import as shapes.
_UNSUPPORTED_TAGS = frozenset({"image", "text", "tspan", "textPath"})

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
    root_opacity = _ratio(root_style.get("opacity"), 1.0)
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
        self._use_stack: list[str] = []

    @staticmethod
    def _collect_css(root: Element) -> list[CssRule]:
        rules: list[CssRule] = []
        for elem in root.iter():
            if local_name(elem.tag) == "style" and elem.text:
                rules.extend(parse_css(elem.text))
        return rules

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
        if tag in _UNSUPPORTED_TAGS:
            raise UnsupportedSVGError(f"Unsupported element: <{tag}>")

        style = resolve_properties(parent_style, tag, elem.attrib, self._css)
        if style.get("display") == "none":
            return
        local_tf = ctm.multiply(parse_transform(elem.get("transform", "")))
        # `opacity` is a non-inherited compositing factor; AE flattens an SVG
        # group/element opacity by multiplying it into the leaf's paint
        # opacity, so accumulate it down the tree and fold it into the leaf.
        eff_opacity = opacity * _ratio(style.get("opacity"), 1.0)

        if tag in _CONTAINER_TAGS:
            out.extend(self.walk(elem, local_tf, style, eff_opacity, depth + 1))
            return
        if tag == "use":
            self._visit_use(elem, local_tf, style, eff_opacity, out, depth)
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
        x = _num(elem.get("x", "0"))
        y = _num(elem.get("y", "0"))
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

        bbox = _bbox(subpaths)
        fill = self._paint(style.get("fill", "black"), bbox, ctm)
        stroke = self._stroke(style, bbox, ctm)
        # `opacity` already includes this element's own opacity (folded in by
        # the caller alongside every ancestor's), so use it directly.
        return SvgDrawable(
            subpaths=subpaths,
            fill=fill,
            stroke=stroke,
            name=elem.get("id"),
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
                return resolve_gradient(gd, bbox, ctm)
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
        width = _num(style.get("stroke-width", "1")) * ctm.mean_scale
        if width <= 0:
            return None
        cap = _CAP.get((style.get("stroke-linecap") or "").strip(), 1)
        join = _JOIN.get((style.get("stroke-linejoin") or "").strip(), 1)
        miter = _num(style.get("stroke-miterlimit", "4"))
        dashes = [
            _num(t) * ctm.mean_scale
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


def _num(text: str | None) -> float:
    if not text:
        return 0.0
    m = NUMBER_RE.search(text)
    return float(m.group()) if m else 0.0


def _ratio(text: str | None, default: float) -> float:
    if text is None or text == "":
        return default
    text = text.strip()
    val = float(text[:-1]) / 100.0 if text.endswith("%") else float(text)
    return clamp01(val)
