"""After Effects' built-in metrics for the standard-14 PDF fonts.

A `.ai`/`.pdf` font dictionary may carry no `/Widths` and no
`/FontDescriptor`, in which case nothing in the file says how wide or how tall
its text is and the consumer is expected to supply the metrics. These are the
ones After Effects supplies, which `resolvers.ai_bounds` needs to reproduce a
"Layer Size" artwork box over such text.

Every number here was **measured from AE 2026**, not transcribed from Adobe's
published AFMs. `scripts/make_std14_probe.py` and
`scripts/dev/make_std14_width_probe.py` build probe PDFs that draw one glyph
per optional content group from a bare font dictionary, so a
`COMP_CROPPED_LAYERS` import solves each layer for the metric AE used:

    ymin  = (box_y0 - pen_y) * 1000 / size
    width = (box_x1 - pen_x) * 1000 / size

Measuring rather than transcribing is not ceremony. All 1330 advances came
back equal to the AFMs, but the vertical extents did not: all four Courier
faces disagree, and AE inverts the AFM's bold/regular relationship there (see
`STD14_EXTENT`). Trusting the published tables would have shipped four wrong
fonts with nothing to catch it.

Two names AE cannot resolve at all are absent by design: it refuses to import
such a document, so there is no artwork box to reproduce.
"""

from __future__ import annotations

#: First character code the width tables cover.
STD14_FIRST_CODE = 32

#: Last character code the width tables cover. Codes above this need the
#: encoding's glyph names, which are not tabulated - see `STD14_WIDTHS`.
STD14_LAST_CODE = 126

#: `/FontBBox` bottom and top, in glyph space.
#:
#: Only these two components are ever needed - a text cell spans the pen
#: position to the pen plus the advance horizontally, and this extent
#: vertically - and the horizontal ones cannot be measured this way, so they
#: are not stored.
#:
#: The Courier faces are where AE parts company with the published AFM: it has
#: -249/803 where the AFM has -250/805, and makes Courier-Bold *taller* than
#: Courier (811) where the AFM makes it shorter (801). That is a different
#: metric source, not a rounding difference.
STD14_EXTENT: dict[str, tuple[float, float]] = {
    "Courier": (-249.0, 803.0),
    "Courier-Bold": (-249.0, 811.0),
    "Courier-Oblique": (-249.0, 803.0),
    "Courier-BoldOblique": (-249.0, 811.0),
    "Helvetica": (-225.0, 931.0),
    "Helvetica-Bold": (-228.0, 962.0),
    "Helvetica-Oblique": (-225.0, 931.0),
    "Helvetica-BoldOblique": (-228.0, 962.0),
    "Times-Roman": (-218.0, 898.0),
    "Times-Bold": (-218.0, 935.0),
    "Times-Italic": (-217.0, 883.0),
    "Times-BoldItalic": (-218.0, 921.0),
    "Symbol": (-293.0, 1010.0),
    "ZapfDingbats": (-143.0, 820.0),
    "Arial": (-225.0, 931.0),
    "TimesNewRoman": (-218.0, 898.0),
}

_MONOSPACE = (600,) * (STD14_LAST_CODE - STD14_FIRST_CODE + 1)

#: Advances in glyph space for codes `STD14_FIRST_CODE`..`STD14_LAST_CODE`,
#: under the encoding a PDF normally names (`/WinAnsiEncoding`, and
#: `/MacRomanEncoding`, which agree over this range) - or, for the symbolic
#: fonts, under their built-in encoding, which no `/Encoding` entry overrides.
#:
#: Codes outside this range are not tabulated: they need the encoding's glyph
#: names to resolve, where WinAnsi, MacRoman and StandardEncoding all diverge.
#: A `/Differences` array is not applied either, for the same reason.
# fmt: off
STD14_WIDTHS: dict[str, tuple[int, ...]] = {
    "Courier": _MONOSPACE,
    "Courier-Bold": _MONOSPACE,
    "Courier-Oblique": _MONOSPACE,
    "Courier-BoldOblique": _MONOSPACE,
    "Helvetica": (
        278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584,
        278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
        556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722,
        722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278,
        278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556,
        556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500,
        278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
    ),
    "Helvetica-Bold": (
        278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584,
        278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
        556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722,
        722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333,
        278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611,
        611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556,
        333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
    ),
    "Helvetica-Oblique": (
        278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584,
        278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
        556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722,
        722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278,
        278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556,
        556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500,
        278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
    ),
    "Helvetica-BoldOblique": (
        278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584,
        278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
        556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722,
        722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333,
        278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611,
        611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556,
        333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
    ),
    "Times-Roman": (
        250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564,
        250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500,
        500, 500, 278, 278, 564, 564, 564, 444, 921, 722, 667, 667,
        722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722,
        556, 722, 667, 556, 611, 722, 722, 944, 722, 722, 611, 333,
        278, 333, 469, 500, 333, 444, 500, 444, 500, 444, 333, 500,
        500, 278, 278, 500, 278, 778, 500, 500, 500, 500, 333, 389,
        278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541,
    ),
    "Times-Bold": (
        250, 333, 555, 500, 500, 1000, 833, 278, 333, 333, 500, 570,
        250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500,
        500, 500, 333, 333, 570, 570, 570, 500, 930, 722, 667, 722,
        722, 667, 611, 778, 778, 389, 500, 778, 667, 944, 722, 778,
        611, 778, 722, 556, 667, 722, 722, 1000, 722, 722, 667, 333,
        278, 333, 581, 500, 333, 500, 556, 444, 556, 444, 333, 500,
        556, 278, 333, 556, 278, 833, 556, 500, 556, 556, 444, 389,
        333, 556, 500, 722, 500, 500, 444, 394, 220, 394, 520,
    ),
    "Times-Italic": (
        250, 333, 420, 500, 500, 833, 778, 214, 333, 333, 500, 675,
        250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500,
        500, 500, 333, 333, 675, 675, 675, 500, 920, 611, 611, 667,
        722, 611, 611, 722, 722, 333, 444, 667, 556, 833, 667, 722,
        611, 722, 611, 500, 556, 722, 611, 833, 611, 556, 556, 389,
        278, 389, 422, 500, 333, 500, 500, 444, 500, 444, 278, 500,
        500, 278, 278, 444, 278, 722, 500, 500, 500, 500, 389, 389,
        278, 500, 444, 667, 444, 444, 389, 400, 275, 400, 541,
    ),
    "Times-BoldItalic": (
        250, 389, 555, 500, 500, 833, 778, 278, 333, 333, 500, 570,
        250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500,
        500, 500, 333, 333, 570, 570, 570, 500, 832, 667, 667, 667,
        722, 667, 667, 722, 778, 389, 500, 667, 611, 889, 722, 722,
        611, 722, 667, 556, 611, 722, 667, 889, 667, 611, 611, 333,
        278, 333, 570, 500, 333, 500, 500, 444, 500, 444, 333, 500,
        556, 278, 278, 500, 278, 778, 556, 500, 500, 500, 389, 389,
        278, 556, 444, 667, 500, 444, 389, 348, 220, 348, 570,
    ),
    "Symbol": (
        250, 333, 713, 500, 549, 833, 778, 439, 333, 333, 500, 549,
        250, 549, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500,
        500, 500, 278, 278, 549, 549, 549, 444, 549, 722, 667, 722,
        612, 611, 763, 603, 722, 333, 631, 722, 686, 889, 722, 722,
        768, 741, 556, 592, 611, 690, 439, 768, 645, 795, 611, 333,
        863, 333, 658, 500, 500, 631, 549, 549, 494, 439, 521, 411,
        603, 329, 603, 549, 549, 576, 521, 549, 549, 521, 549, 603,
        439, 576, 713, 686, 493, 686, 494, 480, 200, 480, 549,
    ),
    "ZapfDingbats": (
        278, 974, 961, 974, 980, 719, 789, 790, 791, 690, 960, 939,
        549, 855, 911, 933, 911, 945, 974, 755, 846, 762, 761, 571,
        677, 763, 760, 759, 754, 494, 552, 537, 577, 692, 786, 788,
        788, 790, 793, 794, 816, 823, 789, 841, 823, 833, 816, 831,
        923, 744, 723, 749, 790, 792, 695, 776, 768, 792, 759, 707,
        708, 682, 701, 826, 815, 789, 789, 707, 687, 696, 689, 786,
        787, 713, 791, 785, 791, 873, 761, 762, 762, 759, 759, 892,
        892, 788, 784, 438, 138, 277, 415, 392, 392, 668, 668,
    ),
    "Arial": (
        278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584,
        278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
        556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722,
        722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278,
        278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556,
        556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500,
        278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
    ),
    "TimesNewRoman": (
        250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564,
        250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500,
        500, 500, 278, 278, 564, 564, 564, 444, 921, 722, 667, 667,
        722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722,
        556, 722, 667, 556, 611, 722, 722, 944, 722, 722, 611, 333,
        278, 333, 469, 500, 333, 444, 500, 444, 500, 444, 333, 500,
        500, 278, 278, 500, 278, 778, 500, 500, 500, 500, 333, 389,
        278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541,
    ),
}
# fmt: on

#: Advances for codes 39 and 96 when the font uses StandardEncoding - which is
#: what an absent `/Encoding` means - where they are `quoteright` and
#: `quoteleft` rather than WinAnsi's `quotesingle` and `grave`. These are the
#: only two codes in the tabulated range where the encodings disagree, and AE
#: was measured to honour the declared one. Fonts whose two glyphs happen to
#: share a width (the monospaced Courier faces) need no entry.
STD14_STANDARD_QUOTES: dict[str, tuple[int, int]] = {
    "Helvetica": (222, 222),
    "Helvetica-Bold": (278, 278),
    "Helvetica-Oblique": (222, 222),
    "Helvetica-BoldOblique": (278, 278),
    "Times-Roman": (333, 333),
    "Times-Bold": (333, 333),
    "Times-Italic": (333, 333),
    "Times-BoldItalic": (333, 333),
    "Arial": (222, 222),
    "TimesNewRoman": (333, 333),
}
