"""Regression tests for the v9 SVG import fixes.

Expected values are the SVG / CSS specifications' and, where stated, what
After Effects 2026 writes for its own import of the same SVG.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from py_aep import ImportAsType, ImportOptions, new
from py_aep.models.items.composition import CompItem
from py_aep.svg import GradientPaint, SolidPaint, UnsupportedSVGError, read_svg
from py_aep.svg.colors import parse_color
from py_aep.svg.transform import IDENTITY, parse_transform

NS = 'xmlns="http://www.w3.org/2000/svg"'


def _svg(body: str, attrs: str = 'viewBox="0 0 200 100"') -> str:
    return f"<svg {NS} {attrs}>{body}</svg>"


def _vertices(markup: str) -> list[list[float]]:
    return read_svg(markup).drawables[0].subpaths[0].vertices


def _bbox(markup: str) -> tuple[float, float, float, float]:
    vs = _vertices(markup)
    xs, ys = [v[0] for v in vs], [v[1] for v in vs]
    return min(xs), min(ys), max(xs), max(ys)


def _import(tmp_path: Path, markup: str) -> CompItem:
    svg = tmp_path / "probe.svg"
    svg.write_text(markup, encoding="utf-8")
    app = new()
    opts = ImportOptions(svg)
    opts.import_as = ImportAsType.COMP_CROPPED_LAYERS
    comp = app.project.import_file(opts)
    assert isinstance(comp, CompItem)
    return comp


def _approx(a: tuple[float, ...], b: tuple[float, ...], tol: float = 1e-9) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class TestMiterLimit:
    @pytest.mark.parametrize("value", ["0.5", "0", "-4"])
    def test_below_one_clamps_to_one(self, tmp_path: Path, value: str) -> None:
        # AE 2026 imports stroke-miterlimit="0.5" with Miter Limit 1.0.
        comp = _import(
            tmp_path,
            _svg(
                "<path d='M10 10 L50 50 L90 10' stroke='red' fill='none' "
                f"stroke-miterlimit='{value}'/>"
            ),
        )
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        stroke = contents[0]["ADBE Vectors Group"]["ADBE Vector Graphic - Stroke"]
        assert stroke["ADBE Vector Stroke Miter Limit"].value == 1.0


class TestBoundingBoxGradients:
    _RECT = "<rect x='20' y='10' width='80' height='40' fill='url(#g)'/>"

    def _paint(self, gradient: str) -> GradientPaint:
        paint = read_svg(_svg(f"<defs>{gradient}</defs>{self._RECT}")).drawables[0].fill
        assert isinstance(paint, GradientPaint)
        return paint

    def test_plain_number_radius_is_a_box_fraction(self) -> None:
        # AE 2026: r="0.25" on an 80 x 40 box -> a 20 px x radius and Grad
        # Scale [100, 50].
        paint = self._paint(
            "<radialGradient id='g' r='0.25'><stop offset='0' stop-color='red'/>"
            "<stop offset='1' stop-color='blue'/></radialGradient>"
        )
        assert _approx(paint.start, (60.0, 30.0))
        assert _approx(paint.end, (80.0, 30.0))
        assert _approx(paint.scale, (100.0, 50.0))

    def test_gradient_transform_rotates_in_box_space(self) -> None:
        # AE 2026: rotate(90) turns the left-to-right gradient top-to-bottom.
        paint = self._paint(
            "<linearGradient id='g' gradientTransform='rotate(90)'>"
            "<stop offset='0' stop-color='red'/><stop offset='1' stop-color='blue'/>"
            "</linearGradient>"
        )
        assert _approx(paint.start, (20.0, 10.0))
        assert _approx(paint.end, (20.0, 50.0))

    def test_gradient_transform_translates_in_box_units(self) -> None:
        # AE 2026: translate(0.5, 0) moves the gradient half the box (40 px).
        paint = self._paint(
            "<linearGradient id='g' gradientTransform='translate(0.5,0)'>"
            "<stop offset='0' stop-color='red'/><stop offset='1' stop-color='blue'/>"
            "</linearGradient>"
        )
        assert _approx(paint.start, (60.0, 10.0))
        assert _approx(paint.end, (140.0, 10.0))

    def test_out_of_order_stops_clamp_to_the_running_maximum(self) -> None:
        # AE 2026 and SVG: 0.6 red then 0.3 blue is red, then blue at 0.6.
        paint = self._paint(
            "<linearGradient id='g'><stop offset='0.6' stop-color='red'/>"
            "<stop offset='0.3' stop-color='blue'/></linearGradient>"
        )
        assert [(s.offset, s.color[:3]) for s in paint.stops] == [
            (0.6, (1.0, 0.0, 0.0)),
            (0.6, (0.0, 0.0, 1.0)),
        ]


class TestMalformedInput:
    def test_wrong_arity_transform_is_ignored(self) -> None:
        # AE 2026 imports a `matrix(1 0 0 1)` group untransformed.
        assert parse_transform("matrix(1 0 0 1)") == IDENTITY
        assert parse_transform("translate(5) skewX()") == IDENTITY
        bbox = _bbox(
            _svg(
                "<g transform='matrix(1 0 0 1)'><rect x='3' width='10' height='10'/></g>"
            )
        )
        assert bbox == (3.0, 0.0, 13.0, 10.0)

    def test_non_finite_transform_is_ignored(self) -> None:
        assert parse_transform("rotate(1e400)") == IDENTITY
        assert parse_transform("skewY(1e400)") == IDENTITY

    def test_unknown_transform_still_raises(self) -> None:
        with pytest.raises(UnsupportedSVGError, match="perspective"):
            parse_transform("perspective(3)")

    def test_tiny_arc_radius_scales_up(self) -> None:
        # Radii too small to reach the end point grow to a half ellipse
        # (SVG F.6.6) instead of dividing by an underflowed square.
        vs = _vertices(
            _svg("<path d='M10 10 A 1e-200 1e-200 0 0 1 80 40' stroke='red'/>")
        )
        assert _approx(tuple(vs[0]), (10.0, 10.0))
        assert _approx(tuple(vs[-1]), (80.0, 40.0), 1e-9)

    @pytest.mark.parametrize(
        "body",
        [
            "<path d='M0 0 L 1e400 10 L 0 10 Z'/>",
            # Finite, but past float32: the saved path could not hold it.
            "<path d='M0 0 L 1e39 10 L 0 10 Z'/>",
            "<rect width='10' height='10' stroke='red' stroke-width='1e400'/>",
        ],
    )
    def test_out_of_range_number_raises_unsupported(self, body: str) -> None:
        with pytest.raises(UnsupportedSVGError, match="out of range"):
            read_svg(_svg(body))

    @pytest.mark.parametrize(
        "markup",
        ["", "not xml", f"<svg {NS}><rect>", f"<svg {NS}>&undefined;</svg>"],
    )
    def test_malformed_xml_raises_unsupported(self, markup: str) -> None:
        with pytest.raises(UnsupportedSVGError, match="Malformed SVG"):
            read_svg(markup.encode("utf-8"))

    @pytest.mark.parametrize(
        "attrs",
        [
            'viewBox="0 0 0.5 100"',
            'viewBox="0 0 1e400 100"',
            'viewBox="0 0 0 0"',
            "",
        ],
    )
    def test_unusable_canvas_raises_unsupported(
        self, tmp_path: Path, attrs: str
    ) -> None:
        with pytest.raises(UnsupportedSVGError, match="1 to 30000 px"):
            _import(tmp_path, _svg("<rect width='2' height='2'/>", attrs))


class TestLengths:
    def test_percentage_corner_radius_refers_to_the_viewport(self) -> None:
        # AE 2026: rx="10%" in a 200-wide viewport is 20 (ry = rx, clamped
        # to half the 20 px height).
        vs = _vertices(_svg("<rect width='50' height='20' rx='10%'/>"))
        assert _approx(tuple(vs[0]), (20.0, 0.0))

    def test_percentage_stroke_width_refers_to_the_diagonal(self) -> None:
        # AE 2026: 5 % of a 200 x 100 viewBox is 7.906.
        stroke = (
            read_svg(
                _svg("<rect width='10' height='10' stroke='red' stroke-width='5%'/>")
            )
            .drawables[0]
            .stroke
        )
        assert stroke is not None
        assert stroke.width == pytest.approx(0.05 * math.sqrt((200**2 + 100**2) / 2))

    @pytest.mark.parametrize(
        ("value", "px"),
        [
            ("1in", 96.0),
            ("2.54cm", 96.0),
            ("25.4mm", 96.0),
            ("72pt", 96.0),
            ("6pc", 96.0),
            ("3em", 48.0),
            ("4px", 4.0),
        ],
    )
    def test_absolute_units_follow_css(self, value: str, px: float) -> None:
        bbox = _bbox(_svg(f"<rect width='{value}' height='10'/>"))
        assert bbox[2] == pytest.approx(px)

    def test_em_follows_the_font_size(self) -> None:
        bbox = _bbox(_svg("<rect width='2em' height='10' font-size='20'/>"))
        assert bbox[2] == pytest.approx(40.0)

    def test_auto_radius_takes_the_other_one(self) -> None:
        # SVG 2 `auto`: a 20-radius circle (py_aep dropped the ellipse; AE
        # 2026 imports it zero-width - a documented divergence).
        bbox = _bbox(_svg("<ellipse cx='50' cy='50' rx='auto' ry='20'/>"))
        assert _approx(bbox, (30.0, 30.0, 70.0, 70.0))


class TestCascadeAndViewports:
    def test_important_rule_beats_inline_style(self) -> None:
        # AE 2026: `rect{fill:red !important}` wins over style="fill:blue".
        fill = (
            read_svg(
                _svg(
                    "<style>rect{fill:red !important}</style>"
                    "<rect style='fill:blue' width='10' height='10'/>"
                )
            )
            .drawables[0]
            .fill
        )
        assert isinstance(fill, SolidPaint)
        assert fill.color == (1.0, 0.0, 0.0, 1.0)

    def test_inline_important_beats_important_rule(self) -> None:
        fill = (
            read_svg(
                _svg(
                    "<style>rect{fill:red !important}</style>"
                    "<rect style='fill:blue !important' width='10' height='10'/>"
                )
            )
            .drawables[0]
            .fill
        )
        assert isinstance(fill, SolidPaint)
        assert fill.color == (0.0, 0.0, 1.0, 1.0)

    def test_nested_svg_maps_its_viewbox(self) -> None:
        # AE 2026: a 10 x 10 viewBox shown in a 50 x 50 box at (10, 10).
        bbox = _bbox(
            _svg(
                "<svg x='10' y='10' width='50' height='50' viewBox='0 0 10 10'>"
                "<rect width='10' height='10'/></svg>"
            )
        )
        assert _approx(bbox, (10.0, 10.0, 60.0, 60.0))

    def test_nested_svg_meets_and_centres(self) -> None:
        bbox = _bbox(
            _svg(
                "<svg width='100' height='50' viewBox='0 0 10 10'>"
                "<rect width='10' height='10'/></svg>"
            )
        )
        assert _approx(bbox, (25.0, 0.0, 75.0, 50.0))

    def test_nested_svg_percentages_use_its_viewbox(self) -> None:
        bbox = _bbox(
            _svg(
                "<svg width='100' height='100' viewBox='0 0 10 10'>"
                "<rect width='50%' height='10'/></svg>"
            )
        )
        assert _approx(bbox, (0.0, 0.0, 50.0, 100.0))

    def test_use_maps_a_symbol_viewbox(self) -> None:
        # AE 2026: a 10 x 10 symbol instanced at x=20 with width 50 is a
        # 50 x 50 square at (20, 0).
        bbox = _bbox(
            _svg(
                "<symbol id='s' viewBox='0 0 10 10'><rect width='10' height='10'/>"
                "</symbol><use href='#s' x='20' width='50' height='50'/>"
            )
        )
        assert _approx(bbox, (20.0, 0.0, 70.0, 50.0))


class TestRadialRotation:
    @pytest.mark.parametrize(
        ("rotate", "expected"),
        [("rotate(30 100 50)", 330.0), ("rotate(-60 100 50)", 420.0), ("", 360.0)],
    )
    def test_grad_rotation_is_360_minus_the_screen_angle(
        self, rotate: str, expected: float
    ) -> None:
        # AE 2026 writes Grad Rotation 330 / 420 / 360 for these.
        paint = (
            read_svg(
                _svg(
                    "<defs><radialGradient id='g' gradientUnits='userSpaceOnUse' "
                    f"cx='100' cy='50' r='30' gradientTransform='{rotate}'>"
                    "<stop offset='0' stop-color='white'/>"
                    "<stop offset='1' stop-color='blue'/></radialGradient></defs>"
                    "<rect x='40' width='120' height='100' fill='url(#g)'/>"
                )
            )
            .drawables[0]
            .fill
        )
        assert isinstance(paint, GradientPaint)
        assert paint.rotation == pytest.approx(expected)


class TestColors:
    def test_hsl_clamps_saturation_and_lightness_first(self) -> None:
        assert parse_color("hsl(400, 150%, -5%)") == (0.0, 0.0, 0.0, 1.0)
        assert parse_color("hsl(120, 100%, 25%)") == (0.0, 0.5, 0.0, 1.0)
