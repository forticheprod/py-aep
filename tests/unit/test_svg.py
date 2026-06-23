"""Tests for the SVG reader package (`py_aep.svg`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.svg import (
    GradientPaint,
    SolidPaint,
    SvgDocument,
    UnsupportedSVGError,
    read_svg,
)
from py_aep.svg.colors import parse_color
from py_aep.svg.path_data import parse_path
from py_aep.svg.shapes import cubics_to_subpath, element_subpaths
from py_aep.svg.style import parse_css, resolve_properties
from py_aep.svg.transform import IDENTITY, parse_transform

SAMPLE = Path(__file__).parent.parent.parent / "samples" / "assets" / "svg.svg"


def _approx(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class TestTransform:
    def test_translate(self):
        t = parse_transform("translate(10, 20)")
        assert t.apply(1.0, 2.0) == (11.0, 22.0)

    def test_scale_single_arg_uniform(self):
        t = parse_transform("scale(3)")
        assert t.apply(2.0, 4.0) == (6.0, 12.0)

    def test_matrix(self):
        t = parse_transform("matrix(1,0,0,1,530,-84)")
        assert t.apply(480.5, 316.5) == (1010.5, 232.5)

    def test_rotate_90(self):
        t = parse_transform("rotate(90)")
        x, y = t.apply(1.0, 0.0)
        assert _approx((x, y), (0.0, 1.0), tol=1e-9)

    def test_rotate_about_center(self):
        t = parse_transform("rotate(180 5 5)")
        assert _approx(t.apply(5.0, 0.0), (5.0, 10.0), tol=1e-9)

    def test_compose_left_applies_last(self):
        # translate then scale: scale applies first to the point.
        t = parse_transform("translate(10,0) scale(2)")
        assert t.apply(3.0, 0.0) == (16.0, 0.0)

    def test_mean_scale(self):
        assert parse_transform("scale(2,8)").mean_scale == pytest.approx(4.0)

    def test_unknown_transform_raises(self):
        with pytest.raises(UnsupportedSVGError):
            parse_transform("warp(3)")


class TestPathData:
    def test_move_line_close_square(self):
        subs = parse_path("M0,0 L10,0 L10,10 L0,10 Z")
        assert len(subs) == 1
        assert subs[0].closed is True
        # 4 drawn segments + a closing segment back to start would be 5, but
        # the explicit return is not needed; closing segment added since the
        # last point (0,10) != start (0,0).
        assert len(subs[0].segments) == 4

    def test_horizontal_vertical(self):
        subs = parse_path("M0,0 H10 V10")
        seg0, seg1 = subs[0].segments
        assert (seg0[6], seg0[7]) == (10.0, 0.0)
        assert (seg1[6], seg1[7]) == (10.0, 10.0)

    def test_cubic(self):
        subs = parse_path("M0,0 C1,2 3,4 5,6")
        seg = subs[0].segments[0]
        assert seg == (0, 0, 1, 2, 3, 4, 5, 6)

    def test_smooth_cubic_reflects_control(self):
        subs = parse_path("M0,0 C1,1 2,2 3,3 S5,5 6,6")
        s2 = subs[0].segments[1]
        # Reflected control of (2,2) about (3,3) is (4,4).
        assert (s2[2], s2[3]) == (4.0, 4.0)

    def test_quadratic_elevated_to_cubic(self):
        subs = parse_path("M0,0 Q3,3 6,0")
        seg = subs[0].segments[0]
        assert _approx((seg[2], seg[3]), (2.0, 2.0))
        assert _approx((seg[4], seg[5]), (4.0, 2.0))

    def test_relative_commands(self):
        subs = parse_path("m10,10 l5,0 l0,5")
        seg0, seg1 = subs[0].segments
        assert (seg0[6], seg0[7]) == (15.0, 10.0)
        assert (seg1[6], seg1[7]) == (15.0, 15.0)

    def test_multiple_subpaths(self):
        subs = parse_path("M0,0 L1,0 M5,5 L6,5 Z")
        assert len(subs) == 2
        assert subs[0].closed is False
        assert subs[1].closed is True

    def test_arc_quarter_circle(self):
        # Quarter circle radius 10 from (10,0) to (0,10).
        subs = parse_path("M10,0 A10,10 0 0 1 0,10")
        seg = subs[0].segments[-1]
        assert _approx((seg[6], seg[7]), (0.0, 10.0), tol=1e-6)

    def test_arc_compacted_flags_match_spaced(self):
        # The W3C path grammar allows the large-arc-flag and sweep-flag to be
        # written with no separator from each other or the next coordinate
        # (e.g. "11" or fused "110"); they must parse the same as the spaced
        # form. Regression for the context-free tokenizer that misread "11"
        # as the single number 11 (crash or wrong arc). AE 2026 imports the
        # compacted arc to exactly this geometry.
        spaced = parse_path("M10,0 A10,10 0 1 1 0,10")
        compact = parse_path("M10,0 A10,10 0 11 0,10")
        fused = parse_path("M10,0 A10,10 0 110,10")
        assert compact[0].segments == spaced[0].segments
        assert fused[0].segments == spaced[0].segments

    def test_arc_compacted_zero_flags(self):
        # "00" must split into two 0/0 flags, not the number 0.
        spaced = parse_path("M10,0 A10,10 0 0 0 0,10")
        compact = parse_path("M10,0 A10,10 0 00 0,10")
        assert compact[0].segments == spaced[0].segments


class TestShapes:
    def test_rect_sharp(self):
        raws = element_subpaths(
            "rect", {"x": "0", "y": "0", "width": "4", "height": "2"}
        )
        sp = cubics_to_subpath(raws[0], IDENTITY)
        assert sp.closed is True
        assert sp.vertices == [[0, 0], [4, 0], [4, 2], [0, 2]]
        assert all(t == [0.0, 0.0] for t in sp.out_tangents)

    def test_rect_rounded_has_bezier_corners(self):
        raws = element_subpaths(
            "rect", {"width": "10", "height": "10", "rx": "2", "ry": "2"}
        )
        sp = cubics_to_subpath(raws[0], IDENTITY)
        assert len(sp.vertices) == 8
        assert any(t != [0.0, 0.0] for t in sp.in_tangents)

    def test_ellipse_four_vertices(self):
        raws = element_subpaths(
            "ellipse", {"cx": "0", "cy": "0", "rx": "10", "ry": "5"}
        )
        sp = cubics_to_subpath(raws[0], IDENTITY)
        assert len(sp.vertices) == 4
        assert sp.closed is True
        assert _approx(sp.vertices[0], (10.0, 0.0))

    def test_polygon_closed(self):
        raws = element_subpaths("polygon", {"points": "0,0 10,0 5,8"})
        sp = cubics_to_subpath(raws[0], IDENTITY)
        assert sp.closed is True
        assert sp.vertices == [[0, 0], [10, 0], [5, 8]]

    def test_polyline_open(self):
        raws = element_subpaths("polyline", {"points": "0,0 10,0 5,8"})
        sp = cubics_to_subpath(raws[0], IDENTITY)
        assert sp.closed is False

    def test_unsupported_element(self):
        with pytest.raises(UnsupportedSVGError):
            element_subpaths("image", {})

    def test_transform_applied_to_vertices(self):
        raws = element_subpaths("rect", {"width": "2", "height": "2"})
        sp = cubics_to_subpath(raws[0], parse_transform("translate(100,50)"))
        assert sp.vertices[0] == [100.0, 50.0]


class TestColors:
    def test_hex6(self):
        assert _approx(parse_color("#ffa619"), (1.0, 166 / 255, 25 / 255, 1.0))

    def test_hex3_expands(self):
        assert parse_color("#fff") == (1.0, 1.0, 1.0, 1.0)

    def test_rgb(self):
        assert parse_color("rgb(255,0,0)") == (1.0, 0.0, 0.0, 1.0)

    def test_rgba_alpha(self):
        assert parse_color("rgba(0,0,0,0.5)") == (0.0, 0.0, 0.0, 0.5)

    def test_named(self):
        assert parse_color("red") == (1.0, 0.0, 0.0, 1.0)

    def test_hsl_red(self):
        assert _approx(parse_color("hsl(0,100%,50%)"), (1.0, 0.0, 0.0, 1.0))

    def test_none_is_none(self):
        assert parse_color("none") is None

    def test_currentcolor(self):
        assert parse_color("currentColor", current=(0.1, 0.2, 0.3, 1.0)) == (
            0.1,
            0.2,
            0.3,
            1.0,
        )


class TestStyle:
    def test_inheritance_of_fill(self):
        parent = resolve_properties({}, "svg", {"fill": "none"}, [])
        child = resolve_properties(parent, "path", {}, [])
        assert child["fill"] == "none"

    def test_child_overrides_parent(self):
        parent = resolve_properties({}, "g", {"fill": "red"}, [])
        child = resolve_properties(parent, "path", {"fill": "blue"}, [])
        assert child["fill"] == "blue"

    def test_opacity_not_inherited(self):
        parent = resolve_properties({}, "g", {"opacity": "0.5"}, [])
        child = resolve_properties(parent, "path", {}, [])
        assert "opacity" not in child

    def test_css_class_beats_presentation_attr(self):
        rules = parse_css(".hi { fill: green; }")
        style = resolve_properties({}, "path", {"class": "hi", "fill": "red"}, rules)
        assert style["fill"] == "green"

    def test_inline_style_strongest(self):
        rules = parse_css("path { fill: green; }")
        style = resolve_properties(
            {}, "path", {"style": "fill:purple", "fill": "red"}, rules
        )
        assert style["fill"] == "purple"

    def test_id_specificity_beats_class(self):
        rules = parse_css(".c { fill: green; } #a { fill: orange; }")
        style = resolve_properties({}, "path", {"id": "a", "class": "c"}, rules)
        assert style["fill"] == "orange"


class TestReadSvgSample:
    def test_canvas_from_viewbox(self):
        doc = read_svg(SAMPLE)
        assert (doc.width, doc.height) == (1070.0, 456.0)

    def test_drawable_count_matches_ae(self):
        # AE 2026 produced 29 vector groups for this SVG (one per leaf).
        doc = read_svg(SAMPLE)
        assert len(doc.drawables) == 29

    def test_group_opacity_folded_into_drawable(self):
        # svg.svg has two <g opacity="0.3"> groups; AE bakes group opacity
        # into the leaf's paint opacity, so the reader folds it into each
        # affected drawable (the rest stay fully opaque).
        doc = read_svg(SAMPLE)
        opacities = sorted(d.opacity for d in doc.drawables if d.opacity != 1.0)
        assert opacities == pytest.approx([0.3, 0.3])

    def test_nested_opacity_multiplies(self):
        # Nested element/group opacities composite multiplicatively.
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<g opacity="0.5"><g opacity="0.4">'
            '<rect x="0" y="0" width="4" height="4" fill="#f00"/>'
            "</g></g></svg>"
        )
        doc = read_svg(svg)
        assert len(doc.drawables) == 1
        assert doc.drawables[0].opacity == pytest.approx(0.2)

    def test_fill_stroke_opacity_attrs_ignored(self):
        # AE's cropped import ignores fill-opacity/stroke-opacity attributes;
        # only element opacity and the color's own alpha affect opacity.
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<rect x="0" y="0" width="4" height="4" fill="#f00" '
            'fill-opacity="0.5" stroke="#00f" stroke-width="1" '
            'stroke-opacity="0.25"/></svg>'
        )
        drawable = read_svg(svg).drawables[0]
        assert isinstance(drawable.fill, SolidPaint)
        assert drawable.fill.color[3] == 1.0
        assert isinstance(drawable.stroke.paint, SolidPaint)
        assert drawable.stroke.paint.color[3] == 1.0
        assert drawable.opacity == 1.0

    def test_first_drawable_geometry_absolute(self):
        doc = read_svg(SAMPLE)
        # Tail Shape 1, group matrix(1,0,0,1,530,-84), path M480.5,316.5.
        assert doc.drawables[0].subpaths[0].vertices[0] == [1010.5, 232.5]

    def test_stroke_only_paths_have_no_fill(self):
        # Root <svg fill="none"> -> stroke-only paths inherit no fill.
        doc = read_svg(SAMPLE)
        stroke_only = [
            d for d in doc.drawables if d.stroke is not None and d.fill is None
        ]
        assert len(stroke_only) == 4

    def test_smil_animation_dropped(self):
        # The SVG has animateTransform elements; none should appear as
        # geometry, and the count stays at the leaf-drawable total.
        doc = read_svg(SAMPLE)
        assert all(isinstance(d.fill, (SolidPaint, type(None))) for d in doc.drawables)


class TestReadSvgFeatures:
    def test_use_expands_reference(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
          <defs><rect id="r" width="10" height="10"/></defs>
          <use href="#r" x="5" y="5"/>
        </svg>"""
        doc = read_svg(svg)
        assert len(doc.drawables) == 1
        assert doc.drawables[0].subpaths[0].vertices[0] == [5.0, 5.0]

    def test_gradient_fill_resolved(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
          <defs>
            <linearGradient id="g" gradientUnits="userSpaceOnUse"
                x1="0" y1="0" x2="100" y2="0">
              <stop offset="0" stop-color="#ff0000"/>
              <stop offset="1" stop-color="#0000ff"/>
            </linearGradient>
          </defs>
          <rect width="100" height="100" fill="url(#g)"/>
        </svg>"""
        doc = read_svg(svg)
        paint = doc.drawables[0].fill
        assert isinstance(paint, GradientPaint)
        assert paint.kind == "linear"
        assert len(paint.stops) == 2
        assert _approx(paint.start, (0.0, 0.0))
        assert _approx(paint.end, (100.0, 0.0))

    def test_gradient_stop_offset_over_one_clamped(self):
        # SVG spec clamps stop offsets to [0, 1]; an offset > 100% must not
        # crash the strict normalized-float validator in the AE gradient model.
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
          <defs><linearGradient id="g">
            <stop offset="0%" stop-color="#ff0000"/>
            <stop offset="150%" stop-color="#0000ff"/>
          </linearGradient></defs>
          <rect width="100" height="100" fill="url(#g)"/>
        </svg>"""
        paint = read_svg(svg).drawables[0].fill
        assert isinstance(paint, GradientPaint)
        assert paint.stops[-1].offset == 1.0

    def test_gradient_coord_with_unit_suffix(self):
        # A unit-suffixed gradient coordinate/radius (legal in userSpaceOnUse)
        # must parse, not raise on bare float("40px").
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
          <defs><radialGradient id="g" gradientUnits="userSpaceOnUse"
              cx="50" cy="50" r="40px">
            <stop offset="0" stop-color="#fff"/>
            <stop offset="1" stop-color="#000"/>
          </radialGradient></defs>
          <circle cx="50" cy="50" r="40" fill="url(#g)"/>
        </svg>"""
        paint = read_svg(svg).drawables[0].fill
        assert isinstance(paint, GradientPaint)
        assert _approx(paint.start, (50.0, 50.0))
        assert _approx(paint.end, (90.0, 50.0))

    def test_deeply_nested_groups_raise_clean_error(self):
        # Unbounded <g> nesting must raise UnsupportedSVGError, not RecursionError.
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'>"
            + "<g>" * 600
            + "<rect width='1' height='1'/>"
            + "</g>" * 600
            + "</svg>"
        )
        with pytest.raises(UnsupportedSVGError):
            read_svg(svg)

    def test_display_none_skipped(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
          <rect width="5" height="5" display="none"/>
          <rect width="5" height="5"/>
        </svg>"""
        assert len(read_svg(svg).drawables) == 1

    def test_nested_group_transforms_compose(self):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
          <g transform="translate(10,10)">
            <g transform="scale(2)">
              <rect width="1" height="1"/>
            </g>
          </g>
        </svg>"""
        doc = read_svg(svg)
        assert doc.drawables[0].subpaths[0].vertices[0] == [10.0, 10.0]
        assert doc.drawables[0].subpaths[0].vertices[2] == [12.0, 12.0]

    def test_non_svg_root_raises(self):
        with pytest.raises(UnsupportedSVGError):
            read_svg("<html xmlns='http://www.w3.org/2000/svg'></html>")

    def test_accepts_bytes(self):
        svg = b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 8'><rect width='8' height='8'/></svg>"
        doc = read_svg(svg)
        assert isinstance(doc, SvgDocument)
        assert doc.width == 8.0


class TestTextWhitespace:
    """Significant whitespace between adjacent <tspan> runs is preserved."""

    @staticmethod
    def _last_run_min_x(svg: str) -> float | None:
        doc = read_svg(svg)
        # Text outlining needs a resolvable font; if none is installed the
        # runs produce no drawables and there is nothing to assert.
        if len(doc.drawables) < 2:
            return None
        return min(
            v[0] for sp in doc.drawables[-1].subpaths for v in sp.vertices
        )

    def test_inter_tspan_space_advances_next_run(self):
        head = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
            '<text x="20" y="130" font-size="72">'
        )
        spaced = self._last_run_min_x(
            head + "<tspan>foo</tspan> <tspan>bar</tspan></text></svg>"
        )
        flush = self._last_run_min_x(
            head + "<tspan>foo</tspan><tspan>bar</tspan></text></svg>"
        )
        if spaced is None or flush is None:
            pytest.skip("no outline font available to render text")
        # The space between the runs pushes `bar` to the right; without the
        # fix the two runs lay out flush and the min-x would be equal.
        assert spaced > flush
