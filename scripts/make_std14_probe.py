"""Regenerate `samples/assets/std14_probe.pdf`.

One optional content group per (font, sample) pair, each drawing a single
glyph from a font dictionary with **no** `/Widths` and **no**
`/FontDescriptor`, so the only metrics After Effects can possibly use are the
standard-14 ones it has built in. An AE `COMP_CROPPED_LAYERS` import therefore
measures those metrics directly: with a known pen position and font size,

    ymin  = (box_y0 - pen_y) * 1000 / size
    ymax  = (box_y1 - pen_y) * 1000 / size
    width = (box_x1 - pen_x) * 1000 / size

Two single-glyph samples per font, at a different glyph and size, check that
the cell height really is a property of the font rather than of the glyph that
happened to be drawn, and that it scales linearly with the size. A third
sample draws every tabulated code in one run, so its box width is the sum of
all 95 advances and no single width can regress unnoticed.

Usage:
    uv run python scripts/make_std14_probe.py

The ground-truth fixture is `samples/models/import/std14_probe.aep`, an AE 2026
`COMP_CROPPED_LAYERS` import of this file. The per-code widths themselves were
measured by `scripts/dev/make_std14_width_probe.py`, which draws one code per
layer; both sets of values live in `data.std14_metrics`.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path("samples/assets")
NAME = "std14_probe.pdf"
PAGE_W, PAGE_H = 1200, 1600

#: The 14 fonts every PDF consumer must have metrics for, plus the two names
#: After Effects resolves onto them. A `/BaseFont` AE cannot resolve at all is
#: deliberately absent: AE refuses the whole document rather than substituting,
#: so such a file has no artwork box to reproduce in the first place.
FONTS = [
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Symbol",
    "ZapfDingbats",
    "Arial",
    "TimesNewRoman",
]

#: Symbolic fonts carry a built-in encoding; naming WinAnsi for them would be
#: a lie the measurement might trip over.
SYMBOLIC = {"Symbol", "ZapfDingbats"}

#: `(name prefix, glyph, font size)` - two independent samples per font, so a
#: cell height that happened to fit one glyph cannot pass.
SAMPLES = [("A", "H", 100.0), ("B", "g", 37.0)]

#: Every tabulated code in one run, whose box width is the sum of all 95
#: advances - a single wrong entry in the width table moves it.
SWEEP_PREFIX = "C"
SWEEP_SIZE = 10.0
FIRST_CODE, LAST_CODE = 32, 126

COLS = 6
CELL_W, CELL_H = 190, 145
ORIGIN_X, ORIGIN_Y = 30.0, 1460.0
SWEEP_X, SWEEP_Y, SWEEP_STEP = 30.0, 650.0, 40.0


def layers() -> list[tuple[str, str]]:
    """`(optional content group name, content stream fragment)`."""
    out = []
    pairs = [(font, sample) for font in FONTS for sample in SAMPLES]
    for slot, (font, (prefix, glyph, size)) in enumerate(pairs):
        pen_x = ORIGIN_X + (slot % COLS) * CELL_W
        pen_y = ORIGIN_Y - (slot // COLS) * CELL_H
        content = (
            f"BT /F{FONTS.index(font)} {size:g} Tf "
            f"{pen_x:g} {pen_y:g} Td ({glyph}) Tj ET"
        )
        out.append((f"{prefix}_{font}", content))
    codes = "".join(f"{code:02x}" for code in range(FIRST_CODE, LAST_CODE + 1))
    for row, font in enumerate(FONTS):
        pen_y = SWEEP_Y - row * SWEEP_STEP
        out.append(
            (
                f"{SWEEP_PREFIX}_{font}",
                f"BT /F{FONTS.index(font)} {SWEEP_SIZE:g} Tf "
                f"{SWEEP_X:g} {pen_y:g} Td <{codes}> Tj ET",
            )
        )
    return out


def build(entries: list[tuple[str, str]]) -> bytes:
    """The probe PDF's bytes."""
    objs: dict[int, bytes] = {}
    count = len(entries)
    ocg_first = 5
    font_first = ocg_first + count

    ocgs = " ".join(f"{ocg_first + i} 0 R" for i in range(count)).encode()
    objs[1] = (
        b"<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [%s] "
        b"/D << /ON [%s] /Order [%s] /RBGroups [] >> >> >>" % (ocgs, ocgs, ocgs)
    )
    objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"

    props = " ".join(f"/MC{i} {ocg_first + i} 0 R" for i in range(count))
    font_res = " ".join(f"/F{i} {font_first + i} 0 R" for i in range(len(FONTS)))
    objs[3] = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents 4 0 R "
        b"/Resources << /Properties << %s >> /Font << %s >> "
        b"/ProcSet [/PDF /Text] >> >>"
        % (PAGE_W, PAGE_H, props.encode(), font_res.encode())
    )

    body = "".join(
        f"/OC /MC{i} BDC\n{content}\nEMC\n"
        for i, (_name, content) in enumerate(entries)
    ).encode("latin-1")
    objs[4] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body)

    for i, (name, _content) in enumerate(entries):
        objs[ocg_first + i] = b"<< /Type /OCG /Name (%s) >>" % name.encode("latin-1")

    for i, font in enumerate(FONTS):
        encoding = b"" if font in SYMBOLIC else b" /Encoding /WinAnsiEncoding"
        objs[font_first + i] = b"<< /Type /Font /Subtype /Type1 /BaseFont /%s%s >>" % (
            font.encode("latin-1"),
            encoding,
        )

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
    entries = layers()
    path = OUT / NAME
    path.write_bytes(build(entries))
    print(
        f"wrote {path} ({path.stat().st_size} bytes, "
        f"{len(entries)} layers, {len(FONTS)} fonts)"
    )


if __name__ == "__main__":
    main()
