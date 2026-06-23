"""Tests for SVG `<text>` / `<tspan>` outlining (svg.text + reader._visit_text).

Geometry is checked against a tiny font built on the fly with `fontBuilder`
(known square glyphs at 1000 upm), so assertions are exact and machine
independent. Reader-level tests monkeypatch font resolution for determinism.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import py_aep.svg.reader as reader_mod
from py_aep.svg import read_svg
from py_aep.svg.path_data import parse_path
from py_aep.svg.text import TextRun, _glyphs, outline_runs, outline_text_path
from py_aep.svg.transform import IDENTITY


def _build_test_font(path):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    def box(x0, y0, x1, y1):
        pen = TTGlyphPen(None)
        pen.moveTo((x0, y0))
        pen.lineTo((x1, y0))
        pen.lineTo((x1, y1))
        pen.lineTo((x0, y1))
        pen.closePath()
        return pen.glyph()

    empty = TTGlyphPen(None).glyph()
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "space", "A", "B"])
    fb.setupCharacterMap({0x20: "space", 0x41: "A", 0x42: "B"})
    # 'A' and 'B' are identical 400x700 boxes; advance 600 units.
    fb.setupGlyf(
        {
            ".notdef": empty,
            "space": empty,
            "A": box(100, 0, 500, 700),
            "B": box(100, 0, 500, 700),
        }
    )
    fb.setupHorizontalMetrics(
        {".notdef": (600, 0), "space": (600, 0), "A": (600, 100), "B": (600, 100)}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "PyAepTest", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))


@pytest.fixture(scope="module")
def test_font(tmp_path_factory):
    path = tmp_path_factory.mktemp("fonts") / "pyaeptest.ttf"
    _build_test_font(path)
    return path


def _xrange(sp):
    xs = [v[0] for v in sp.vertices]
    return (min(xs), max(xs))


def _yrange(sp):
    ys = [v[1] for v in sp.vertices]
    return (min(ys), max(ys))


def test_glyph_outline_geometry(test_font):
    # 'A' box 100..500 x, 0..700 y at font-size 100 (scale 0.1), baseline 0:
    # x -> 10..50, y flipped -> -70..0.
    [subs] = outline_runs([TextRun("A", test_font, 100.0)], 0.0, 0.0, IDENTITY)
    assert len(subs) == 1
    sp = subs[0]
    assert sp.closed
    assert len(sp.vertices) == 4
    assert _xrange(sp) == (10.0, 50.0)
    assert _yrange(sp) == (-70.0, 0.0)


def test_advance_layout(test_font):
    # Two glyphs in one run; advance 600 * 0.1 = 60, so 'B' shifts right by 60.
    [subs] = outline_runs([TextRun("AB", test_font, 100.0)], 0.0, 0.0, IDENTITY)
    assert len(subs) == 2
    assert _xrange(subs[0]) == (10.0, 50.0)
    assert _xrange(subs[1]) == (70.0, 110.0)


def test_anchor_end_shifts_left(test_font):
    # Run width 60; text-anchor=end shifts the whole run left by its width.
    [subs] = outline_runs([TextRun("A", test_font, 100.0)], 0.0, 0.0, IDENTITY, "end")
    assert _xrange(subs[0]) == (-50.0, -10.0)


def test_anchor_middle_centers(test_font):
    [subs] = outline_runs(
        [TextRun("A", test_font, 100.0)], 0.0, 0.0, IDENTITY, "middle"
    )
    assert _xrange(subs[0]) == (-20.0, 20.0)


def test_reader_outlines_text(monkeypatch, test_font):
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 100">'
        '<text x="10" y="80" font-size="100" fill="#ff0000">AB</text></svg>'
    )
    doc = read_svg(svg)
    assert len(doc.drawables) == 1
    d = doc.drawables[0]
    assert len(d.subpaths) == 2
    assert d.fill is not None
    assert tuple(d.fill.color[:3]) == (1.0, 0.0, 0.0)


def test_reader_tspan_per_run_fill(monkeypatch, test_font):
    # Parent text and a <tspan> with its own fill become two drawables.
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 100">'
        '<text x="10" y="80" font-size="100" fill="#000000">A'
        '<tspan fill="#ff0000">B</tspan></text></svg>'
    )
    doc = read_svg(svg)
    assert len(doc.drawables) == 2
    assert tuple(doc.drawables[0].fill.color[:3]) == (0.0, 0.0, 0.0)
    assert tuple(doc.drawables[1].fill.color[:3]) == (1.0, 0.0, 0.0)


def test_reader_tspan_inherits_font_size(monkeypatch, test_font):
    # The <tspan> has no font-size; it must inherit 100 from the parent <text>
    # (advance 60), so 'B' lands at x 70..110 just like the single-run case.
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 100">'
        '<text x="0" y="100" font-size="100">A<tspan>B</tspan></text></svg>'
    )
    doc = read_svg(svg)
    assert len(doc.drawables) == 2
    b = doc.drawables[1].subpaths[0]
    assert _xrange(b) == (70.0, 110.0)


def test_reader_text_skipped_without_font(monkeypatch):
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: None)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<text x="0" y="50">hi</text></svg>'
    )
    assert read_svg(svg).drawables == []


def test_letter_spacing(test_font):
    # letter-spacing adds to each glyph's advance: 'B' shifts by 60 + 20.
    [subs] = outline_runs(
        [TextRun("AB", test_font, 100.0, letter_spacing=20.0)], 0.0, 0.0, IDENTITY
    )
    assert _xrange(subs[0]) == (10.0, 50.0)
    assert _xrange(subs[1]) == (90.0, 130.0)


def test_reader_text_stroke(monkeypatch, test_font):
    # A stroked, unfilled <text> yields a stroked drawable with no fill.
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 100">'
        '<text x="10" y="80" font-size="100" fill="none" '
        'stroke="#00ff00" stroke-width="4">A</text></svg>'
    )
    doc = read_svg(svg)
    assert len(doc.drawables) == 1
    d = doc.drawables[0]
    assert d.fill is None
    assert d.stroke is not None
    assert tuple(d.stroke.paint.color[:3]) == (0.0, 1.0, 0.0)
    assert d.stroke.width == 4.0


def test_textpath_horizontal_matches_inline(test_font):
    # On a horizontal path, midpoint placement reproduces the inline advance
    # layout at baseline 100 (glyphs sit above the baseline: y 30..100).
    path = parse_path("M0,100 L300,100")
    subs = outline_text_path("AB", path, test_font, 100.0, IDENTITY)
    assert len(subs) == 2
    assert _xrange(subs[0]) == (10.0, 50.0)
    assert _yrange(subs[0]) == (30.0, 100.0)
    assert _xrange(subs[1]) == (70.0, 110.0)


def test_textpath_offpath_glyphs_dropped(test_font):
    # 'A' midpoint at 30 fits; 'B' midpoint at 90 runs past the 80-unit path.
    path = parse_path("M0,100 L80,100")
    subs = outline_text_path("AB", path, test_font, 100.0, IDENTITY)
    assert len(subs) == 1
    assert _xrange(subs[0]) == (10.0, 50.0)


def test_reader_textpath(monkeypatch, test_font):
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 300 200">'
        '<defs><path id="p" d="M0,100 L300,100"/></defs>'
        '<text font-size="100" fill="#ff0000">'
        '<textPath xlink:href="#p">AB</textPath></text></svg>'
    )
    doc = read_svg(svg)
    assert len(doc.drawables) == 1
    d = doc.drawables[0]
    assert len(d.subpaths) == 2
    assert tuple(d.fill.color[:3]) == (1.0, 0.0, 0.0)


def test_reader_textpath_applies_path_transform(monkeypatch, test_font):
    # The referenced path's OWN transform must apply: translate(0,100) puts the
    # baseline at y=100, so 'A' spans y 30..100 (x is unchanged by the y-shift).
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 300 200">'
        '<defs><path id="p" d="M0,0 L300,0" transform="translate(0,100)"/></defs>'
        '<text font-size="100" fill="#000000">'
        '<textPath xlink:href="#p">A</textPath></text></svg>'
    )
    doc = read_svg(svg)
    assert len(doc.drawables) == 1
    sp = doc.drawables[0].subpaths[0]
    assert _xrange(sp) == (10.0, 50.0)
    assert _yrange(sp) == (30.0, 100.0)


def test_reader_image_skipped_with_warning():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100">'
        '<image x="0" y="0" width="50" height="50" xlink:href="foo.png"/></svg>'
    )
    with pytest.warns(UserWarning, match="image"):
        doc = read_svg(svg)
    assert doc.drawables == []


def test_reader_image_does_not_block_vectors():
    # An <image> next to a <rect> is skipped (warned) but the rect still imports.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100">'
        '<rect x="0" y="0" width="10" height="10" fill="#ff0000"/>'
        '<image x="0" y="0" width="50" height="50" xlink:href="foo.png"/></svg>'
    )
    with pytest.warns(UserWarning):
        doc = read_svg(svg)
    assert len(doc.drawables) == 1


class _NoCmapFont:
    """Duck-typed TTFont whose getBestCmap() is None (a symbol font, e.g.
    Windows Wingdings/Webdings/Symbol/Marlett, which has no Unicode cmap)."""

    def getBestCmap(self):
        return None

    def getGlyphSet(self):
        return {}

    def __getitem__(self, key):
        return SimpleNamespace(unitsPerEm=1000)


def test_glyphs_handles_font_without_unicode_cmap():
    # Regression: getBestCmap() returns None for symbol fonts; _glyphs used to
    # crash with AttributeError, taking down the whole read_svg(). It must now
    # map every char to no glyph so the run is simply dropped.
    names, advances, upm, _ = _glyphs(_NoCmapFont(), "AB")
    assert names == [None, None]
    assert advances == [0.0, 0.0]


def test_reader_collapses_indentation_whitespace(monkeypatch, test_font):
    # Regression: a pretty-printed <text> with leading/trailing indentation
    # used to render those spaces as glyph advances, shifting the text right.
    # SVG collapses internal whitespace and trims the run's edges.
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'

    def min_x(svg):
        return min(
            v[0] for sp in read_svg(svg).drawables[0].subpaths for v in sp.vertices
        )

    flush = head + '<text x="0" y="100" font-size="100">AB</text></svg>'
    indented = head + '<text x="0" y="100" font-size="100">\n   AB\n  </text></svg>'
    assert min_x(indented) == pytest.approx(min_x(flush))


def test_per_chunk_anchor_ignores_abs_x_run_width(test_font):
    # Two text chunks: "A" continues from the origin, "B" resets to x=200.
    # Both are end-anchored. Each chunk must anchor to its OWN width - the old
    # code summed both widths into one shift, dragging "A" far left.
    runs = [
        TextRun("A", test_font, 100.0, anchor="end"),
        TextRun("B", test_font, 100.0, abs_x=200.0, anchor="end"),
    ]
    a, b = outline_runs(runs, 0.0, 0.0, IDENTITY)
    # Chunk "A": advance 60 end-anchored at 0 -> glyph box [-50, -10].
    assert _xrange(a[0]) == (-50.0, -10.0)
    # Chunk "B": advance 60 end-anchored at 200 -> glyph box [150, 190].
    assert _xrange(b[0]) == (150.0, 190.0)


def test_reader_per_tspan_text_anchor(monkeypatch, test_font):
    # A <tspan> that resets x and sets its own text-anchor establishes its own
    # chunk with that anchor; the parent run keeps the default start anchor.
    monkeypatch.setattr(reader_mod, "resolve_font", lambda *a, **k: (test_font, 0))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
        '<text x="0" y="100" font-size="100">A'
        '<tspan x="300" text-anchor="end">B</tspan></text></svg>'
    )
    doc = read_svg(svg)
    assert len(doc.drawables) == 2
    assert _xrange(doc.drawables[0].subpaths[0]) == (10.0, 50.0)  # A at origin
    assert _xrange(doc.drawables[1].subpaths[0]) == (250.0, 290.0)  # B ends at 300


def test_resolve_font_finds_ttc_secondary_face(tmp_path, monkeypatch):
    # Regression: a family that ships only as a non-zero face of a .ttc
    # collection must be discoverable, and resolve to that exact face index.
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTCollection

    import py_aep.svg.fonts as fonts_mod

    def build_face(family: str):
        pen = TTGlyphPen(None)
        pen.moveTo((0, 0))
        pen.lineTo((100, 0))
        pen.lineTo((100, 100))
        pen.closePath()
        fb = FontBuilder(1000, isTTF=True)
        fb.setupGlyphOrder([".notdef", "A"])
        fb.setupCharacterMap({0x41: "A"})
        fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": pen.glyph()})
        fb.setupHorizontalMetrics({".notdef": (600, 0), "A": (600, 0)})
        fb.setupHorizontalHeader(ascent=800, descent=-200)
        fb.setupNameTable({"familyName": family, "styleName": "Regular"})
        fb.setupOS2()
        fb.setupPost()
        return fb.font

    ttc = tmp_path / "combo.ttc"
    coll = TTCollection()
    coll.fonts = [build_face("PrimaryFam"), build_face("SecondaryFam")]
    coll.save(str(ttc))

    monkeypatch.setattr(fonts_mod, "_font_dirs", lambda: [tmp_path])
    monkeypatch.setattr(fonts_mod, "_index", None)
    assert fonts_mod.resolve_font("PrimaryFam") == (ttc, 0)
    assert fonts_mod.resolve_font("SecondaryFam") == (ttc, 1)
