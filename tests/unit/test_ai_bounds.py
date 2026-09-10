"""Unit tests for `resolvers.ai_bounds`, the AI/PDF artwork-box measurer.

Each case is a one-layer PDF built in memory from a content-stream snippet, so
a rule can be pinned without a sample file. The measured values come from
After Effects 2026; `tests/read_only/test_ai_bounds.py` checks the same rules
against AE's own fixtures.
"""

from __future__ import annotations

import pytest

from py_aep.data.std14_metrics import (
    STD14_EXTENT,
    STD14_FIRST_CODE,
    STD14_STANDARD_QUOTES,
    STD14_WIDTHS,
)
from py_aep.resolvers.ai_bounds import (
    EMPTY_BOX,
    footage_size,
    read_ai_layer_bounds,
)
from py_aep.resolvers.ai_layers import UnsupportedAiLayersError

PAGE = 600

#: Spelled by code point: a content stream's escapes must reach the measurer
#: as the bytes they are, not as whatever a source-level escape survives as.
SOLIDUS = chr(92)
LF = chr(10)
CR = chr(13)


def build_pdf(*layers: str, extra_objects: str = "", resources: str = "") -> bytes:
    """A minimal layered PDF with one optional content group per `layers` body.

    `extra_objects` is spliced in verbatim after the numbered objects, and
    `resources` is merged into the page's `/Resources` dictionary, so a case
    can bring its own font or XObject.
    """
    count = len(layers)
    ocg_first = 5
    objs: dict[int, str] = {}
    refs = " ".join(f"{ocg_first + i} 0 R" for i in range(count))
    objs[1] = (
        f"<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [{refs}] "
        f"/D << /ON [{refs}] /Order [{refs}] >> >> >>"
    )
    objs[2] = "<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    props = " ".join(f"/MC{i} {ocg_first + i} 0 R" for i in range(count))
    objs[3] = (
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE} {PAGE}] "
        f"/Contents 4 0 R /Resources << /Properties << {props} >> "
        f"{resources} /ProcSet [/PDF /Text] >> >>"
    )
    body = "".join(
        f"/OC /MC{i} BDC\n{content}\nEMC\n" for i, content in enumerate(layers)
    )
    objs[4] = f"<< /Length {len(body)} >>\nstream\n{body}\nendstream"
    for i in range(count):
        objs[ocg_first + i] = f"<< /Type /OCG /Name (L{i}) >>"

    out = "%PDF-1.5\n"
    for number in sorted(objs):
        out += f"{number} 0 obj\n{objs[number]}\nendobj\n"
    out += extra_objects
    # A cross-reference section is required: the COS lexer treats `xref` as
    # end-of-object, and without one an object parse runs on into `trailer`
    # and raises on the unknown keyword.
    out += "xref\n0 1\n0000000000 65535 f \n"
    out += "trailer\n<< /Size 99 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
    return out.encode("latin-1")


def measure(content: str, **kwargs: str) -> tuple[float, float, float, float] | None:
    """The artwork box of a single-layer PDF built from `content`."""
    return read_ai_layer_bounds("probe.pdf", build_pdf(content, **kwargs))[0]


def approx(box: tuple[float, float, float, float]) -> object:
    # A couple of 1/65536 quanta: After Effects' own arithmetic differs from
    # ours in the last fixed-point step or two.
    return pytest.approx(box, abs=3 / 65536)


class TestFills:
    def test_rect_fill_expands_by_a_quarter_point(self) -> None:
        assert measure("50 200 100 80 re f") == approx((49.75, 199.75, 150.25, 280.25))

    def test_even_odd_fill_matches_non_zero(self) -> None:
        nonzero = measure("50 200 100 80 re f")
        assert measure("50 200 100 80 re f*") == approx(nonzero)  # type: ignore[arg-type]

    def test_open_subpath_fill_is_measured(self) -> None:
        assert measure("400 300 m 460 300 l 460 360 l f") == approx(
            (399.75, 299.75, 460.25, 360.25)
        )

    def test_unpainted_path_contributes_nothing(self) -> None:
        assert measure("50 200 100 80 re n") is None

    def test_control_point_hull_not_curve_bounds(self) -> None:
        # The cubic peaks 112.5 above its ends; its control points sit 150
        # above, and After Effects measures the control points.
        assert measure("40 480 m 240 630 -60 630 140 480 c f") == approx(
            (-60.25, 479.75, 240.25, 630.25)
        )

    def test_contributions_union(self) -> None:
        assert measure("20 160 40 40 re f 200 560 30 30 re f") == approx(
            (19.75, 159.75, 230.25, 590.25)
        )


class TestStrokes:
    def test_single_straight_segment_has_no_join_term(self) -> None:
        assert measure("10 w 50 250 m 150 250 l S") == approx(
            (45.0, 245.0, 155.0, 255.0)
        )

    @pytest.mark.parametrize("cap", [0, 1, 2])
    def test_cap_style_is_ignored(self, cap: int) -> None:
        assert measure(f"10 w {cap} J 50 250 m 150 250 l S") == approx(
            (45.0, 245.0, 155.0, 255.0)
        )

    @pytest.mark.parametrize("join", [0, 1, 2])
    def test_join_style_is_ignored(self, join: int) -> None:
        # All three joins expand by the same worst-case miter term.
        assert measure(f"10 w 4 M {join} j 40 400 m 70 440 l 100 400 l S") == approx(
            (30.0, 390.0, 110.0, 450.0)
        )

    @pytest.mark.parametrize(
        "miter,expected",
        [(2, (35.0, 395.0, 105.0, 445.0)), (4, (30.0, 390.0, 110.0, 450.0))],
    )
    def test_joined_stroke_scales_with_the_miter_limit(
        self, miter: int, expected: tuple[float, float, float, float]
    ) -> None:
        # A joined path expands by (lw / 2) * (miter limit / 2).
        assert measure(f"10 w {miter} M 40 400 m 70 440 l 100 400 l S") == approx(
            expected
        )

    def test_stroked_rectangle_takes_the_exact_right_angle_miter(self) -> None:
        # sqrt(2) * lw / 2, not the worst-case miter-limit expansion.
        assert measure("10 w 10 M 480 40 60 40 re S") == approx(
            (472.9289, 32.9289, 547.0711, 87.0711)
        )

    def test_line_width_scales_with_the_matrix(self) -> None:
        assert measure("q 2 0 0 2 0 0 cm 10 w 10 280 m 40 280 l S Q") == approx(
            (10.0, 550.0, 90.0, 570.0)
        )

    def test_expansion_is_per_axis_not_a_single_scale(self) -> None:
        # A 4x/1x matrix expands x by 20 and y by 5; a geometric-mean scale
        # would give 10 for both.
        assert measure("q 4 0 0 1 0 0 cm 10 w 5 500 m 35 500 l S Q") == approx(
            (0.0, 495.0, 160.0, 505.0)
        )

    def test_fill_and_stroke_uses_the_stroke_rule_outright(self) -> None:
        # The 0.25 fill pad is not also applied and no max() is taken: at
        # lw 0.04 with miter 4 the expansion is 0.04, well under 0.25.
        assert measure("0.04 w 4 M 400 200 m 460 200 l 460 260 l h B") == approx(
            (399.96, 199.96, 460.04, 260.04)
        )


class TestShadings:
    _SHADING = (
        "20 0 obj\n<< /ShadingType 2 /ColorSpace /DeviceGray "
        "/Coords [0 0 1 1] /Function << /FunctionType 2 /C0 [0] /C1 [1] "
        "/Domain [0 1] /N 1 >> >>\nendobj\n"
    )
    _RES = "/Shading << /Sh0 20 0 R >>"

    def _shade(self, content: str) -> tuple[float, float, float, float] | None:
        return measure(content, extra_objects=self._SHADING, resources=self._RES)

    def test_shading_paints_the_clip_region(self) -> None:
        assert self._shade("q 0 0 20 20 re W n /Sh0 sh Q") == approx(
            (-0.25, -0.25, 20.25, 20.25)
        )

    @pytest.mark.parametrize(
        "content",
        [
            # A second `W n` at the same level, and one a `q` deeper: both
            # narrow the region, they do not replace it.
            "q 0 0 20 20 re W n 0 0 100 100 re W n /Sh0 sh Q",
            "q 0 0 20 20 re W n q 0 0 100 100 re W n /Sh0 sh Q Q",
            "q 0 0 100 100 re W n q 0 0 20 20 re W n /Sh0 sh Q Q",
        ],
    )
    def test_a_further_clip_intersects_rather_than_replaces(self, content: str) -> None:
        assert self._shade(content) == approx((-0.25, -0.25, 20.25, 20.25))

    def test_a_clip_restored_by_Q_widens_again(self) -> None:
        assert self._shade(
            "q 0 0 100 100 re W n q 0 0 20 20 re W n Q /Sh0 sh Q"
        ) == approx((-0.25, -0.25, 100.25, 100.25))


class TestState:
    def test_graphics_state_spans_layer_boundaries(self) -> None:
        # A `q` pushed in one layer is popped by the next layer's `Q`, so the
        # measurer has to run one state machine over the whole stream.
        boxes = read_ai_layer_bounds(
            "probe.pdf",
            build_pdf(
                "q 1 0 0 1 100 100 cm 0 0 40 40 re f",
                "Q 0 0 40 40 re f",
            ),
        )
        assert boxes[0] == approx((99.75, 99.75, 140.25, 140.25))
        assert boxes[1] == approx((-0.25, -0.25, 40.25, 40.25))

    def test_line_width_persists_across_layers(self) -> None:
        boxes = read_ai_layer_bounds(
            "probe.pdf", build_pdf("10 w", "50 250 m 150 250 l S")
        )
        assert boxes[1] == approx((45.0, 245.0, 155.0, 255.0))

    def test_clip_is_ignored_except_for_shadings(self) -> None:
        # Illustrator pre-trims the geometry it writes, and After Effects
        # measures straight through a residual clip.
        assert measure("q 0 0 10 10 re W n 50 200 100 80 re f Q") == approx(
            (49.75, 199.75, 150.25, 280.25)
        )

    def test_saturates_at_the_fixed_point_range(self) -> None:
        box = measure("40000 40000 5000 5000 re f")
        assert box is not None
        limit = (2**31 - 1) / 65536
        assert box[2] == pytest.approx(limit, abs=1e-4)
        assert box[3] == pytest.approx(limit, abs=1e-4)
        assert box[2] - box[0] == pytest.approx(0.25, abs=1e-3)


class TestXObjects:
    _FORM = (
        "20 0 obj\n<< /Type /XObject /Subtype /Form /BBox [0 0 40 30] "
        "/Matrix [2 0 0 2 0 0] /Length 0 >>\nstream\n\nendstream\nendobj\n"
    )
    _IMAGE = (
        "21 0 obj\n<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
        "/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
        "stream\nA\nendstream\nendobj\n"
    )
    _RES = "/XObject << /Fm0 20 0 R /Im0 21 0 R >>"

    def test_form_bbox_through_matrix_and_ctm_unpadded(self) -> None:
        assert measure(
            "q 1 0 0 1 20 20 cm /Fm0 Do Q",
            extra_objects=self._FORM,
            resources=self._RES,
        ) == approx((20.0, 20.0, 100.0, 80.0))

    def test_image_unit_square_through_ctm_unpadded(self) -> None:
        assert measure(
            "q 50 0 0 40 200 40 cm /Im0 Do Q",
            extra_objects=self._IMAGE,
            resources=self._RES,
        ) == approx((200.0, 40.0, 250.0, 80.0))

    def test_inline_image_measures_like_an_image_xobject(self) -> None:
        # `BI ... ID ... EI` is the same painting operator as an image
        # XObject, spelled inline, so it contributes the same unit square.
        ctm = "q 40 0 0 30 100 100 cm"
        inline = measure(f"{ctm} BI /W 1 /H 1 /CS /G /BPC 8 ID \x00 EI Q")
        assert inline == approx((100.0, 100.0, 140.0, 130.0))
        assert inline == approx(
            measure(  # type: ignore[arg-type]
                f"{ctm} /Im0 Do Q",
                extra_objects=self._IMAGE,
                resources=self._RES,
            )
        )

    def test_a_layer_may_mix_padded_and_unpadded_contributions(self) -> None:
        # The expansion is applied per contribution, never to the union.
        assert measure(
            "100 100 40 40 re f q 1 0 0 1 300 300 cm /Fm0 Do Q",
            extra_objects=self._FORM,
            resources=self._RES,
        ) == approx((99.75, 99.75, 380.0, 360.0))


def _bare_font(name: str, encoding: str = "") -> str:
    """A font dictionary with neither `/Widths` nor a `/FontDescriptor`."""
    return (
        f"20 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /{name}"
        f"{encoding} >>\nendobj\n"
    )


class TestText:
    _RES = "/Font << /F1 20 0 R >>"
    _HELVETICA = (
        "20 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        "/Encoding /WinAnsiEncoding >>\nendobj\n"
    )
    # /Ascent and /Descent deliberately disagree with /FontBBox.
    _PROBE_FONT = (
        "20 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /ProbeFont "
        "/Encoding /WinAnsiEncoding /FirstChar 32 /LastChar 122 "
        f"/Widths [{' '.join(['600'] * 91)}] /FontDescriptor 22 0 R >>\nendobj\n"
        "22 0 obj\n<< /Type /FontDescriptor /FontName /ProbeFont /Flags 32 "
        "/FontBBox [-100 -400 1000 1000] /Ascent 800 /Descent -200 >>\n"
        "endobj\n"
    )

    def _probe(self, content: str) -> tuple[float, float, float, float] | None:
        return measure(content, extra_objects=self._PROBE_FONT, resources=self._RES)

    def test_vertical_extent_is_the_font_bbox_not_ascent_descent(self) -> None:
        # 1.4 em tall (the FontBBox), not 1.0 em (Ascent minus Descent).
        box = self._probe("BT /F1 24 Tf 40 100 Td (Hg) Tj ET")
        assert box is not None
        assert box[3] - box[1] == pytest.approx(33.6, abs=1e-3)
        assert box[1] == pytest.approx(100 - 0.4 * 24, abs=1e-3)

    def test_horizontal_extent_is_the_full_advance(self) -> None:
        box = self._probe("BT /F1 24 Tf 40 100 Td (Hg) Tj ET")
        assert box is not None
        assert box[2] - box[0] == pytest.approx(2 * 0.6 * 24, abs=1e-3)

    def test_character_spacing_widens_the_cell(self) -> None:
        plain = self._probe("BT /F1 24 Tf 40 100 Td (Hg) Tj ET")
        spaced = self._probe("BT /F1 24 Tf 5 Tc 40 100 Td (Hg) Tj ET")
        assert plain is not None and spaced is not None
        assert (spaced[2] - spaced[0]) - (plain[2] - plain[0]) == pytest.approx(
            10.0, abs=1e-3
        )

    def test_horizontal_scaling_widens_only_the_advance(self) -> None:
        plain = self._probe("BT /F1 24 Tf 40 100 Td (Hg) Tj ET")
        scaled = self._probe("BT /F1 24 Tf 200 Tz 40 100 Td (Hg) Tj ET")
        assert plain is not None and scaled is not None
        assert (scaled[2] - scaled[0]) == pytest.approx(
            2 * (plain[2] - plain[0]), abs=1e-3
        )
        assert (scaled[3] - scaled[1]) == pytest.approx(plain[3] - plain[1], abs=1e-3)

    def test_invisible_render_mode_is_still_measured(self) -> None:
        plain = self._probe("BT /F1 24 Tf 40 100 Td (Hg) Tj ET")
        hidden = self._probe("BT /F1 24 Tf 3 Tr 40 100 Td (Hg) Tj ET")
        assert hidden == approx(plain)  # type: ignore[arg-type]

    def test_stroking_render_mode_grows_the_cell(self) -> None:
        box = self._probe("BT /F1 24 Tf 1 Tr 10 w 40 100 Td (Hg) Tj ET")
        plain = self._probe("BT /F1 24 Tf 40 100 Td (Hg) Tj ET")
        assert box is not None and plain is not None
        assert box[0] == pytest.approx(plain[0] - 5.0, abs=1e-3)
        assert box[2] == pytest.approx(plain[2] + 5.0, abs=1e-3)

    @pytest.mark.parametrize(
        "font", ["Courier", "Courier-Bold", "Times-Bold", "Symbol", "Arial"]
    )
    def test_built_in_metrics_set_the_cell_height(self, font: str) -> None:
        # That the *values* are right is what the AE fixture in
        # tests/read_only proves; this is the plumbing - a font dictionary
        # with no descriptor reaches the table at all, for every face.
        ymin, ymax = STD14_EXTENT[font]
        box = measure(
            "BT /F1 50 Tf 40 300 Td (H) Tj ET",
            extra_objects=_bare_font(font),
            resources=self._RES,
        )
        assert box is not None
        assert box[1] == pytest.approx(300.0 + ymin / 20.0)
        assert box[3] == pytest.approx(300.0 + ymax / 20.0)

    @pytest.mark.parametrize("font", ["Courier", "Times-Roman", "ZapfDingbats"])
    def test_built_in_widths_set_the_advance(self, font: str) -> None:
        # Code 72 is "H"; the table is indexed from STD14_FIRST_CODE.
        expected = STD14_WIDTHS[font][72 - STD14_FIRST_CODE]
        box = measure(
            "BT /F1 50 Tf 40 300 Td <48> Tj ET",
            extra_objects=_bare_font(font),
            resources=self._RES,
        )
        assert box is not None
        assert box[0] == pytest.approx(40.0)
        assert box[2] == pytest.approx(40.0 + expected / 20.0)

    def test_an_absent_encoding_uses_the_standard_quote_widths(self) -> None:
        # Codes 39 and 96 are the only two in the tabulated range where
        # WinAnsiEncoding and the fonts' built-in StandardEncoding disagree,
        # and After Effects honours whichever the file declares.
        quote_39, _quote_96 = STD14_STANDARD_QUOTES["Times-Roman"]
        winansi = STD14_WIDTHS["Times-Roman"][39 - STD14_FIRST_CODE]
        assert quote_39 != winansi
        cases = (("", quote_39), (" /Encoding /WinAnsiEncoding", winansi))
        for encoding, expected in cases:
            box = measure(
                "BT /F1 50 Tf 40 300 Td <27> Tj ET",
                extra_objects=_bare_font("Times-Roman", encoding),
                resources=self._RES,
            )
            assert box is not None
            assert box[2] == pytest.approx(40.0 + expected / 20.0)

    @pytest.mark.parametrize("shown", ["[<48>] TJ", "[<48> -50 <48>] TJ"])
    def test_a_hex_string_in_a_show_array_is_hex_decoded(self, shown: str) -> None:
        # `<48>` is one code (H), not the two characters "4" and "8": the
        # array reader has to decode it exactly as a bare `<48> Tj` does.
        def show(operands: str) -> tuple[float, float, float, float] | None:
            return measure(
                f"BT /F1 50 Tf 40 300 Td {operands} ET",
                extra_objects=self._HELVETICA,
                resources=self._RES,
            )

        assert show(shown) == approx(show(shown.replace("<48>", "(H)")))  # type: ignore[arg-type]

    @pytest.mark.parametrize("eol", [LF, CR + LF])
    def test_a_line_continuation_is_not_a_glyph(self, eol: str) -> None:
        # PDF 7.3.4.2: a reverse solidus before an end-of-line marker is a
        # line continuation, not an escaped newline character.
        def show(text: str) -> tuple[float, float, float, float] | None:
            return measure(
                f"BT /F1 50 Tf 40 300 Td ({text}) Tj ET",
                extra_objects=self._HELVETICA,
                resources=self._RES,
            )

        plain = show("HH")
        assert show("H" + SOLIDUS + eol + "H") == approx(plain)  # type: ignore[arg-type]
        # A `SOLIDUS n` escape is a real linefeed character, still measured.
        assert show("H" + SOLIDUS + "nH") != plain

    def test_font_outside_the_table_uses_the_generic_extent(self) -> None:
        # A face After Effects can resolve but py_aep has no metrics for.
        box = measure(
            "BT /F1 50 Tf 40 300 Td (H) Tj ET",
            extra_objects=_bare_font("Verdana"),
            resources=self._RES,
        )
        assert box is not None
        assert (box[1], box[3]) == pytest.approx((287.5, 337.5))

    def test_standard_14_metrics_without_widths_or_descriptor(self) -> None:
        # /Helvetica with neither /Widths nor /FontDescriptor: the built-in
        # AFM widths (722 + 556) and FontBBox (-225 .. 931).
        box = measure(
            "BT /F1 24 Tf 40 300 Td (Hg) Tj ET",
            extra_objects=self._HELVETICA,
            resources=self._RES,
        )
        assert box == approx((40.0, 294.6, 70.672, 322.344))


class TestUnsupported:
    def test_not_a_pdf_raises(self) -> None:
        with pytest.raises(UnsupportedAiLayersError, match="PDF-compatible"):
            read_ai_layer_bounds("probe.ai", b"not a pdf at all")

    def test_no_layers_raises(self) -> None:
        with pytest.raises(UnsupportedAiLayersError, match="no layers"):
            read_ai_layer_bounds("probe.pdf", b"%PDF-1.5\nnothing here\n")

    def test_object_streams_raise(self) -> None:
        data = build_pdf(
            "50 200 100 80 re f",
            extra_objects="9 0 obj\n<< /Type /ObjStm >>\nendobj\n",
        )
        with pytest.raises(UnsupportedAiLayersError, match="object streams"):
            read_ai_layer_bounds("probe.pdf", data)

    def test_encrypted_raises(self) -> None:
        data = build_pdf("50 200 100 80 re f").replace(
            b"trailer\n<< /Size 99", b"trailer\n<< /Encrypt 9 0 R /Size 99", 1
        )
        with pytest.raises(UnsupportedAiLayersError, match="encrypted"):
            read_ai_layer_bounds("probe.pdf", data)


class TestMultipleArtboards:
    def test_warns_and_measures_the_first_page(self) -> None:
        # After Effects measures the SECOND page here and reports
        # first-artboard layers as empty; py_aep measures the first and warns
        # rather than discarding artwork.
        data = build_pdf(
            "50 200 100 80 re f",
            extra_objects=(
                "30 0 obj\n<< /Type /Page /Parent 2 0 R "
                "/MediaBox [0 0 200 200] >>\nendobj\n"
            ),
        ).replace(b"/Kids [3 0 R] /Count 1", b"/Kids [3 0 R 30 0 R] /Count 2", 1)
        with pytest.warns(UserWarning, match="artboards"):
            boxes = read_ai_layer_bounds("probe.pdf", data)
        assert boxes[0] == approx((49.75, 199.75, 150.25, 280.25))


class TestFootageSize:
    """`footage_size`, the pixel size After Effects derives from a box."""

    def test_empty_layer_floors_at_one_pixel(self) -> None:
        assert footage_size(None) == (1, 1)
        assert footage_size(EMPTY_BOX) == (1, 1)

    def test_a_fractional_extent_ceils(self) -> None:
        assert footage_size((112.748, 239.5073, 593.931, 675.999)) == (482, 437)

    @pytest.mark.parametrize("noise", [0.0, 1e-12, -1e-12])
    def test_float_noise_around_an_integer_does_not_add_a_pixel(
        self, noise: float
    ) -> None:
        # The box reaches AE as signed 16.16, so the extent is quantized
        # before it is ceilinged: 80 + 1e-12 must not measure 81 pixels.
        assert footage_size((10.0, 20.0, 90.0 + noise, 40.0 + noise)) == (80, 20)
