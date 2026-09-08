"""Regenerate `samples/assets/ai_bounds_probe.pdf`.

One optional content group per construct that
[read_ai_layer_bounds][py_aep.resolvers.ai_bounds.read_ai_layer_bounds] has to
measure, so an After Effects `COMP_CROPPED_LAYERS` import of the file yields one
unambiguous artwork box per rule.

`.pdf` goes through the same AE importer as `.ai`, and a hand-written PDF
reaches constructs Illustrator never emits: a `cm`-scaled stroke (Illustrator
bakes transforms into coordinates), a font with no `/FontDescriptor`,
`Tz`/`Tw`/`Tr`, an even-odd fill, and coordinates past the `opti` box's signed
16.16 range.

Usage:
    uv run python scripts/make_ai_bounds_probe.py

The ground-truth fixture is `samples/models/import/ai_bounds_probe.aep`, an AE
2026 `COMP_CROPPED_LAYERS` import of this file. See
`.claude/plans/ai-layer-size.md` for how it was captured and what each rule is.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path("samples/assets")
NAME = "ai_bounds_probe.pdf"
PAGE_W, PAGE_H = 600, 600

#: `(layer name, content-stream body, what the layer pins down)`.
#:
#: The graphics and text state deliberately persists across `BDC`/`EMC` here
#: (the `4 M` set by `q_miter_m4` still applies later, as do `200 Tz` and
#: `1 Tr`), which is itself part of what the fixture pins: After Effects runs
#: one state machine over the whole stream rather than parsing each layer's
#: section independently.
LAYERS: list[tuple[str, str, str]] = [
    (
        "q_ctm_uniform2x",
        "q 2 0 0 2 0 0 cm 10 w 10 280 m 40 280 l S Q",
        "a stroke under a 2x CTM: the line width scales with the matrix",
    ),
    (
        "q_ctm_nonuniform",
        "q 4 0 0 1 0 0 cm 10 w 5 500 m 35 500 l S Q",
        "a stroke under a 4x/1x CTM: the expansion is per-axis, not a single "
        "geometric-mean scale",
    ),
    (
        "q_miter_m4",
        "4 M 10 w 40 400 m 70 440 l 100 400 l S",
        "a joined stroke expands by (lw/2)*(miter limit/2), here 10",
    ),
    (
        "q_evenodd",
        "200 400 100 60 re 220 420 60 20 re f*",
        "an even-odd fill behaves like a non-zero fill",
    ),
    (
        "q_font_no_descriptor",
        "BT /F1 24 Tf 40 300 Td (Hg) Tj ET",
        "no /Widths and no /FontDescriptor: the built-in standard-14 metrics",
    ),
    (
        "q_font_widths_only",
        "BT /F2 24 Tf 200 300 Td (Hg) Tj ET",
        "/Widths present, still no descriptor: widths honoured, AFM box used",
    ),
    (
        "q_tz200",
        "BT /F2 24 Tf 200 Tz 40 250 Td (Hg) Tj ET",
        "horizontal scaling doubles the advance and not the cell height",
    ),
    (
        "q_tw20",
        "BT /F2 24 Tf 20 Tw 200 250 Td (a a) Tj ET",
        "word spacing widens the cell at code 32",
    ),
    (
        "q_tr3_invisible",
        "BT /F2 24 Tf 3 Tr 40 200 Td (Hg) Tj ET",
        "render mode 3 is invisible but still measured",
    ),
    (
        "q_tr1_stroke",
        "BT /F2 24 Tf 1 Tr 10 w 200 200 Td (Hg) Tj ET",
        "a stroking render mode grows the cell by the stroke half-width",
    ),
    (
        "q_huge_coords",
        "40000 40000 5000 5000 re f",
        "coordinates past the signed 16.16 range saturate to a 1x1 footage",
    ),
    (
        "q_fill_stroke_thin",
        "0.04 w 400 200 m 460 200 l 460 260 l h B",
        "fill+stroke uses the stroke rule outright, not max(fill, stroke)",
    ),
    (
        "q_ascent_vs_fontbbox",
        "BT /F3 24 Tf 40 100 Td (Hg) Tj ET",
        "a descriptor whose /Ascent and /FontBBox disagree: the /FontBBox wins",
    ),
    (
        "q_open_fill",
        "400 300 m 460 300 l 460 360 l f",
        "an open subpath that is filled measures like a closed one",
    ),
    (
        "q_stroke_re",
        "10 w 10 M 480 40 60 40 re S",
        "a stroked rectangle takes the exact 90-degree miter, not the "
        "worst-case miter-limit expansion",
    ),
    (
        "q_wild_cubic",
        "40 480 m 240 630 -60 630 140 480 c f",
        "the control-point hull, not the true curve bounds: the curve peaks "
        "112.5 above its ends but its control points sit 150 above",
    ),
    (
        "q_form_bbox",
        "q 1 0 0 1 20 20 cm /Fm0 Do Q",
        "a form XObject contributes its /BBox through /Matrix x CTM, unpadded",
    ),
    (
        "q_image",
        "q 50 0 0 40 200 40 cm /Im0 Do Q",
        "an image XObject contributes the unit square through the CTM, unpadded",
    ),
    (
        "q_shading",
        "q 300 40 80 60 re W n /Sh0 sh Q",
        "a shading paints the current clip region",
    ),
    (
        "q_two_islands",
        "20 160 40 40 re f 200 560 30 30 re f",
        "two disjoint contributions union into one box",
    ),
    (
        "q_mixed_regimes",
        "100 100 40 40 re f q 1 0 0 1 300 300 cm /Fm0 Do Q",
        "one layer mixing a padded fill with an unpadded form: the expansion "
        "is per contribution, not applied to the union",
    ),
    (
        "q_empty",
        "",
        "no artwork at all: the 1/65536 epsilon box and a 1x1 footage",
    ),
]


def build() -> bytes:
    """The probe PDF's bytes."""
    objs: dict[int, bytes] = {}
    count = len(LAYERS)
    ocg_first = 5
    font1 = ocg_first + count
    font2 = font1 + 1
    font3 = font2 + 1
    descriptor = font3 + 1
    form = descriptor + 1
    image = form + 1
    shading = image + 1
    function = shading + 1

    ocgs = " ".join(f"{ocg_first + i} 0 R" for i in range(count)).encode()
    objs[1] = (
        b"<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [%s] "
        b"/D << /ON [%s] /Order [%s] /RBGroups [] >> >> >>" % (ocgs, ocgs, ocgs)
    )
    objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"

    props = " ".join(f"/MC{i} {ocg_first + i} 0 R" for i in range(count)).encode()
    objs[3] = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents 4 0 R "
        b"/Resources << /Properties << %s >> "
        b"/Font << /F1 %d 0 R /F2 %d 0 R /F3 %d 0 R >> "
        b"/XObject << /Fm0 %d 0 R /Im0 %d 0 R >> "
        b"/Shading << /Sh0 %d 0 R >> "
        b"/ProcSet [/PDF /Text /ImageC] >> >>"
        % (PAGE_W, PAGE_H, props, font1, font2, font3, form, image, shading)
    )

    body = "".join(
        f"/OC /MC{i} BDC\n{content}\nEMC\n"
        for i, (_name, content, _note) in enumerate(LAYERS)
    ).encode("latin-1")
    objs[4] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body)

    for i, (name, _content, _note) in enumerate(LAYERS):
        objs[ocg_first + i] = b"<< /Type /OCG /Name (%s) >>" % name.encode("latin-1")

    # F1 has neither /Widths nor a descriptor, so only the built-in
    # standard-14 metrics can measure it.
    objs[font1] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    widths = " ".join(["600"] * 224).encode()
    objs[font2] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding /FirstChar 32 /LastChar 255 "
        b"/Widths [%s] >>" % widths
    )
    # F3's /Ascent and /Descent deliberately disagree with its /FontBBox, so
    # the fixture records which one After Effects measures.
    objs[font3] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /ProbeFont "
        b"/Encoding /WinAnsiEncoding /FirstChar 32 /LastChar 255 "
        b"/Widths [%s] /FontDescriptor %d 0 R >>" % (widths, descriptor)
    )
    objs[descriptor] = (
        b"<< /Type /FontDescriptor /FontName /ProbeFont /Flags 32 "
        b"/FontBBox [-100 -400 1000 1000] /ItalicAngle 0 /Ascent 800 "
        b"/Descent -200 /CapHeight 700 /StemV 80 >>"
    )

    # A form whose /BBox and /Matrix are both non-trivial, so the measured box
    # exercises the whole /BBox x /Matrix x CTM chain.
    inner = b"0 0 1 rg 0 0 40 30 re f"
    objs[form] = (
        b"<< /Type /XObject /Subtype /Form /BBox [0 0 40 30] "
        b"/Matrix [2 0 0 2 0 0] /Resources << /ProcSet [/PDF] >> "
        b"/Length %d >>\nstream\n%s\nendstream" % (len(inner), inner)
    )
    # A 1x1 grey image: no /BBox, so the unit square through the CTM.
    objs[image] = (
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
        b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
        b"stream\n\x80\nendstream"
    )
    objs[shading] = (
        b"<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [300 40 380 100] "
        b"/Function %d 0 R /Extend [true true] >>" % function
    )
    objs[function] = b"<< /FunctionType 2 /Domain [0 1] /C0 [1 0 0] /C1 [0 0 1] /N 1 >>"

    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for number in sorted(objs):
        offsets[number] = len(out)
        out += b"%d 0 obj\n" % number + objs[number] + b"\nendobj\n"
    xref_at = len(out)
    top = max(objs) + 1
    out += b"xref\n0 %d\n" % top
    out += b"0000000000 65535 f \n"
    for number in range(1, top):
        if number in offsets:
            out += b"%010d 00000 n \n" % offsets[number]
        else:
            out += b"0000000000 65535 f \n"
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        top,
        xref_at,
    )
    return bytes(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / NAME
    path.write_bytes(build())
    print(f"wrote {path} ({path.stat().st_size} bytes, {len(LAYERS)} layers)")
    print()
    for index, (name, content, note) in enumerate(LAYERS):
        print(f"  [{index:2d}] {name:<22} {note}")
        if content:
            print(f"       {content}")


if __name__ == "__main__":
    main()
