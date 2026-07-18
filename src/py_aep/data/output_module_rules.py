"""Allowed values for output-module settings, per format / codec / context.

Encodes what After Effects' Output Module Settings dialog allows for each
output format: which settings are locked by the format kind (audio formats
never have video output), which value sets each format offers (PNG has no
floating-point depth), and which values depend on other settings (WAV's
GSM codec forces mono, PNG forces straight alpha only when channels are
RGB+Alpha).

Sources: AE 2025/2026 dialog research (`format_rules.txt`) cross-checked
against AE-saved samples in `samples/models/format_options/`,
`samples/models/renderqueue/` and `samples/unused/output_module_settings/`.
Where the notes and the binaries disagreed, the binaries won (e.g. the
QuickTime depth union, and PNG's Color byte being free when channels are
plain RGB).

Lookup contract (`allowed_values`):
- `None` means UNCONSTRAINED - the key has no rule under this format and
  context. (Contrast `data/file_formats.py`, where an empty result means
  "nothing allowed": callers here must gate on `is None` first.)
- Constraint keys are the ExtendScript setting names from `OM_SETTINGS`
  (e.g. `"Depth"`, `"Audio Sample Rate"`) plus format-option context keys
  (e.g. `"Audio Codec"`, `"BitRate"`).
- Conditional entries are ordered general -> specific; a later matching
  entry REPLACES earlier constraints per key. Entries constraining the
  same key within one format must have mutually exclusive conditions.
- A condition key absent from the context never matches (permissive
  degradation: stale or unparseable context disables the rule, it never
  rejects).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, FrozenSet, Tuple

if TYPE_CHECKING:
    from typing import Mapping

from ..enums import (
    AudioBitDepth,
    AudioChannels,
    AudioCodec,
    FormatKind,
    MPEGAudioFormat,
    MPEGAudioLayer,
    MPEGMultiplexer,
    OutputAudio,
    OutputChannels,
    OutputColorDepth,
    OutputColorMode,
    OutputFormat,
    VideoCodec,
)

#: One conditional rule: (conditions, constraints). Every condition must
#: match the context (a tuple value means "in"); constraints then apply.
Rule = Tuple[Dict[str, object], Dict[str, FrozenSet[object]]]

_MILLIONS = OutputColorDepth.MILLIONS_OF_COLORS
_MILLIONS_PLUS = OutputColorDepth.MILLIONS_OF_COLORS_PLUS
_TRILLIONS = OutputColorDepth.TRILLIONS_OF_COLORS
_TRILLIONS_PLUS = OutputColorDepth.TRILLIONS_OF_COLORS_PLUS
_FLOAT = OutputColorDepth.FLOATING_POINT
_FLOAT_PLUS = OutputColorDepth.FLOATING_POINT_PLUS

_8_TO_16_BPC = frozenset({_MILLIONS, _MILLIONS_PLUS, _TRILLIONS, _TRILLIONS_PLUS})
_8_TO_32_BPC = _8_TO_16_BPC | frozenset({_FLOAT, _FLOAT_PLUS})

_RGB_OR_ALPHA = frozenset({OutputChannels.RGB, OutputChannels.ALPHA})

# Rates AE offers for plain PCM-style audio (AIFF, WAV Uncompressed, AVI).
_PCM_RATES = frozenset({8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000})

# WAV ADPCM/GSM codecs offer this reduced set; A-Law/u-Law add 16000.
_ADPCM_RATES = frozenset({8000, 11025, 22050, 44100})
_CCITT_RATES = _ADPCM_RATES | frozenset({16000})

_SIXTEEN_BIT_ONLY = frozenset({AudioBitDepth.SIXTEEN_BIT})


_KIND_RULES: dict[FormatKind, dict[str, frozenset[object]]] = {
    FormatKind.AUDIO: {
        "Video Output": frozenset({False}),
        "Output Audio": frozenset({OutputAudio.ON}),
    },
    FormatKind.MOVIE: {},
    FormatKind.SEQUENCE: {
        "Video Output": frozenset({True}),
        "Output Audio": frozenset({OutputAudio.OFF}),
    },
}


_FORMAT_RULES: dict[OutputFormat, dict[str, frozenset[object]]] = {
    OutputFormat.AIFF: {
        "Audio Sample Rate": _PCM_RATES,
    },
    OutputFormat.AVI: {
        # 48/64 only reachable via V210 (union over codecs); the 64
        # entry keeps the channels<->depth pairing closed under RGBA.
        "Depth": frozenset({_MILLIONS, _MILLIONS_PLUS, _TRILLIONS, _TRILLIONS_PLUS}),
        "Audio Sample Rate": _PCM_RATES,
    },
    OutputFormat.DPX_CINEON_SEQUENCE: {
        "Depth": frozenset({_TRILLIONS, _TRILLIONS_PLUS}),
    },
    OutputFormat.H264: {
        "Channels": _RGB_OR_ALPHA,
        "Depth": frozenset({_MILLIONS}),
        # Union over audio formats: AAC set + MPEG {32k,44.1k,48k} + PCM
        # {48k,96k}; conditional rows narrow per Audio Format.
        "Audio Sample Rate": frozenset(
            {16000, 22050, 24000, 32000, 44100, 48000, 96000}
        ),
    },
    OutputFormat.IFF_SEQUENCE: {
        "Depth": _8_TO_16_BPC,
    },
    OutputFormat.JPEG_SEQUENCE: {
        "Channels": _RGB_OR_ALPHA,
        "Depth": frozenset({_MILLIONS}),
    },
    OutputFormat.MP3: {
        # The depth control is hidden; AE always stores 16-bit (verified
        # across the 18-bitrate sweep in samples/unused/output_module_settings).
        "Audio Bit Depth": _SIXTEEN_BIT_ONLY,
        # Union over (bitrate, channels) pairs observed in AE-saved files
        # (12000 comes from mono at 18/20 kbps).
        "Audio Sample Rate": frozenset(
            {8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000}
        ),
    },
    OutputFormat.OPENEXR_SEQUENCE: {
        "Depth": frozenset({_FLOAT, _FLOAT_PLUS}),
    },
    OutputFormat.PNG_SEQUENCE: {
        "Depth": _8_TO_16_BPC,
    },
    OutputFormat.PHOTOSHOP_SEQUENCE: {
        "Depth": _8_TO_32_BPC,
    },
    OutputFormat.QUICKTIME: {
        # Alpha IS QuickTime-legal despite the dialog research notes:
        # AE's own factory template "High Quality with Alpha" writes a
        # QT Rouu with depth 32 (millions+), and alpha-capable codecs
        # (Animation, ProRes 4444, ...) offer RGB+Alpha. 48 comes from
        # the 10-bit YUV codecs (AE-saved sample evidence). Which codecs
        # allow alpha is future per-codec narrowing.
        "Depth": frozenset({_MILLIONS, _MILLIONS_PLUS, _TRILLIONS, _TRILLIONS_PLUS}),
    },
    OutputFormat.RADIANCE_SEQUENCE: {
        "Channels": _RGB_OR_ALPHA,
        "Depth": frozenset({_FLOAT}),
    },
    OutputFormat.SGI_SEQUENCE: {
        "Depth": _8_TO_16_BPC,
    },
    OutputFormat.TIFF_SEQUENCE: {
        "Depth": _8_TO_32_BPC,
    },
    OutputFormat.TARGA_SEQUENCE: {
        "Depth": frozenset({_MILLIONS, _MILLIONS_PLUS}),
    },
    OutputFormat.WAV: {
        # Unions over codecs; per-codec rows below narrow them.
        "Audio Sample Rate": _PCM_RATES,
        "Audio Bit Depth": frozenset(
            {
                AudioBitDepth.EIGHT_BIT,
                AudioBitDepth.SIXTEEN_BIT,
                AudioBitDepth.THIRTY_TWO_BIT,
            }
        ),
    },
}

# Format-option fields each format's dialog offers (member sets for the
# codec/container dropdowns and the MP3 bitrate list).
_FORMAT_RULES[OutputFormat.AVI]["Video Codec"] = frozenset(
    {
        VideoCodec.NONE,
        VideoCodec.V210,
        VideoCodec.UYVY,
        VideoCodec.INTEL_IYUV,
        VideoCodec.DV_24P,
        VideoCodec.DV_NTSC,
        VideoCodec.DV_PAL,
    }
)
_FORMAT_RULES[OutputFormat.AVI]["Audio Codec"] = frozenset({AudioCodec.UNCOMPRESSED})
_FORMAT_RULES[OutputFormat.H264]["Audio Codec"] = frozenset(
    {AudioCodec.AAC, AudioCodec.AAC_PLUS_V1, AudioCodec.AAC_PLUS_V2}
)
_FORMAT_RULES[OutputFormat.H264]["Multiplexer"] = frozenset(
    {MPEGMultiplexer.MP4, MPEGMultiplexer.THREEGPP, MPEGMultiplexer.NONE}
)
_FORMAT_RULES[OutputFormat.MP3]["BitRate"] = frozenset(
    {16, 18, 20, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320}
)
_FORMAT_RULES[OutputFormat.WAV]["Audio Codec"] = frozenset(
    {
        AudioCodec.UNCOMPRESSED,
        AudioCodec.IMA_ADPCM,
        AudioCodec.MICROSOFT_ADPCM,
        AudioCodec.CCITT_A_LAW,
        AudioCodec.CCITT_U_LAW,
        AudioCodec.GSM_6_10,
    }
)
_FORMAT_RULES[OutputFormat.QUICKTIME]["Video Codec"] = frozenset(
    {
        VideoCodec.ANIMATION,
        VideoCodec.APPLE_PRORES_422,
        VideoCodec.APPLE_PRORES_422_HQ,
        VideoCodec.APPLE_PRORES_422_LT,
        VideoCodec.APPLE_PRORES_422_PROXY,
        VideoCodec.APPLE_PRORES_4444,
        VideoCodec.APPLE_PRORES_4444_XQ,
        VideoCodec.DNXHR_DNXHD,
        VideoCodec.DV25_NTSC,
        VideoCodec.DV25_NTSC_24P,
        VideoCodec.DV25_PAL,
        VideoCodec.DV50_NTSC,
        VideoCodec.DV50_PAL,
        VideoCodec.DVCPRO_HD_1080I50,
        VideoCodec.DVCPRO_HD_1080I60,
        VideoCodec.DVCPRO_HD_1080P25,
        VideoCodec.DVCPRO_HD_1080P30,
        VideoCodec.DVCPRO_HD_720P50,
        VideoCodec.DVCPRO_HD_720P60,
        VideoCodec.GOPRO_CINEFORM,
        VideoCodec.AVC1,
        VideoCodec.UNCOMPRESSED_RGB_8_BIT,
        VideoCodec.UNCOMPRESSED_YUV_10_BIT_422,
        VideoCodec.UNCOMPRESSED_YUV_8_BIT_422,
    }
)


# The H.264 AAC audio-bitrate matrix: (codec, rate group, channels) ->
# allowed kbps. The kbps ladders are irregular (not simple slices), so
# they are transcribed literally from the AE dialog research.
def _aac_bitrate_rows() -> list[Rule]:
    rows: list[Rule] = []
    matrix = (
        (
            AudioCodec.AAC,
            (
                (
                    (16000,),
                    AudioChannels.MONO,
                    (16, 20, 24, 28, 32, 40, 48, 56, 64, 80),
                ),
                (
                    (16000,),
                    AudioChannels.STEREO,
                    (16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160),
                ),
                (
                    (22050, 24000),
                    AudioChannels.MONO,
                    (16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 96, 112, 128),
                ),
                (
                    (22050, 24000),
                    AudioChannels.STEREO,
                    (
                        16,
                        20,
                        24,
                        28,
                        32,
                        40,
                        48,
                        56,
                        64,
                        80,
                        96,
                        112,
                        128,
                        160,
                        192,
                        224,
                        256,
                    ),
                ),
                (
                    (32000,),
                    AudioChannels.MONO,
                    (16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160),
                ),
                (
                    (32000,),
                    AudioChannels.STEREO,
                    (
                        16,
                        20,
                        24,
                        28,
                        32,
                        40,
                        48,
                        56,
                        64,
                        80,
                        96,
                        112,
                        128,
                        160,
                        192,
                        224,
                        256,
                        320,
                    ),
                ),
                (
                    (44100, 48000),
                    AudioChannels.MONO,
                    (
                        16,
                        20,
                        24,
                        28,
                        32,
                        40,
                        48,
                        56,
                        64,
                        80,
                        96,
                        112,
                        128,
                        160,
                        192,
                        224,
                        256,
                    ),
                ),
                (
                    (44100, 48000),
                    AudioChannels.STEREO,
                    (
                        16,
                        20,
                        24,
                        28,
                        32,
                        40,
                        48,
                        56,
                        64,
                        80,
                        96,
                        112,
                        128,
                        160,
                        192,
                        224,
                        256,
                        320,
                        384,
                        448,
                        512,
                    ),
                ),
            ),
        ),
        (
            AudioCodec.AAC_PLUS_V1,
            (
                ((16000,), AudioChannels.MONO, (16, 20, 24, 28, 32, 40)),
                ((16000,), AudioChannels.STEREO, (16, 20, 24, 28, 32, 40, 48, 56)),
                ((22050, 24000), AudioChannels.MONO, (16, 20, 24, 28, 32, 40, 48)),
                (
                    (22050, 24000),
                    AudioChannels.STEREO,
                    (16, 20, 24, 28, 32, 40, 48, 56, 64),
                ),
                ((32000,), AudioChannels.MONO, (16, 20, 24, 28, 32, 40, 48, 56)),
                ((32000,), AudioChannels.STEREO, (24, 28, 32, 40, 48, 56, 64, 80)),
                (
                    (44100, 48000),
                    AudioChannels.MONO,
                    (16, 20, 24, 28, 32, 40, 48, 56, 64),
                ),
                ((44100, 48000), AudioChannels.STEREO, (32, 40, 48, 56, 64, 80, 96)),
            ),
        ),
        (
            AudioCodec.AAC_PLUS_V2,
            (
                ((16000,), AudioChannels.STEREO, (16, 20, 24, 28, 32, 40)),
                ((22050, 24000), AudioChannels.STEREO, (16, 20, 24, 28, 32, 40, 48)),
                ((32000,), AudioChannels.STEREO, (16, 20, 24, 28, 32, 40, 48, 56)),
                (
                    (44100, 48000),
                    AudioChannels.STEREO,
                    (16, 20, 24, 28, 32, 40, 48, 56, 64),
                ),
            ),
        ),
    )
    for codec, groups in matrix:
        for rates, channels, kbps in groups:
            rate_cond: object = rates if len(rates) > 1 else rates[0]
            rows.append(
                (
                    {
                        "Audio Format": MPEGAudioFormat.AAC,
                        "Audio Codec": codec,
                        "Audio Sample Rate": rate_cond,
                        "Audio Channels": channels,
                    },
                    {"Audio Bitrate": frozenset(kbps)},
                )
            )
    return rows


# Ordered general -> specific; a later match replaces earlier constraints
# per key. Same-key entries within a format must be mutually exclusive.
_CONDITIONAL_RULES: dict[OutputFormat, list[Rule]] = {
    OutputFormat.AVI: [
        (
            {"Video Codec": VideoCodec.NONE},
            {
                "Channels": frozenset(
                    {OutputChannels.RGB, OutputChannels.RGBA, OutputChannels.ALPHA}
                ),
                "Depth": frozenset({_MILLIONS, _MILLIONS_PLUS}),
            },
        ),
        (
            {
                "Video Codec": (
                    VideoCodec.DV_24P,
                    VideoCodec.DV_NTSC,
                    VideoCodec.DV_PAL,
                    VideoCodec.INTEL_IYUV,
                    VideoCodec.UYVY,
                )
            },
            {
                "Channels": _RGB_OR_ALPHA,
                "Depth": frozenset({_MILLIONS}),
            },
        ),
        (
            {"Video Codec": VideoCodec.V210},
            {
                "Channels": _RGB_OR_ALPHA,
                "Depth": frozenset({_TRILLIONS}),
            },
        ),
    ],
    OutputFormat.H264: [
        (
            {"Audio Format": MPEGAudioFormat.AAC},
            {
                "Audio Sample Rate": frozenset(
                    {16000, 22050, 24000, 32000, 44100, 48000}
                ),
            },
        ),
        (
            {"Audio Format": MPEGAudioFormat.MPEG},
            {"Audio Sample Rate": frozenset({32000, 44100, 48000})},
        ),
        (
            {"Audio Format": MPEGAudioFormat.PCM},
            {"Audio Sample Rate": frozenset({48000, 96000})},
        ),
    ],
    OutputFormat.OPENEXR_SEQUENCE: [
        # The premultiplied/straight choice only exists when alpha is
        # included; with plain RGB the stored byte is inert and AE-saved
        # files hold either value.
        (
            {"Channels": OutputChannels.RGBA},
            {"Color": frozenset({OutputColorMode.PREMULTIPLIED})},
        ),
    ],
    OutputFormat.PNG_SEQUENCE: [
        (
            {"Channels": OutputChannels.RGBA},
            {"Color": frozenset({OutputColorMode.STRAIGHT_UNMATTED})},
        ),
    ],
    OutputFormat.MP3: [
        # (bitrate kbps, channels) -> the single sample rate AE resolves,
        # decoded from the AE-saved sweeps in
        # samples/unused/output_module_settings/mp3_*.aep (18 stereo
        # files + 4 mono probes). The research notes' mono/stereo
        # columns were swapped wholesale relative to these binaries
        # (every mono probe matches the notes' "stereo" column, incl.
        # the 12000 Hz rows); the binaries won.
        (
            {"BitRate": kbps, "Audio Channels": channels},
            {"Audio Sample Rate": frozenset({rate})},
        )
        for channels, table in (
            (
                AudioChannels.STEREO,
                (
                    (16, 8000),
                    (18, 8000),
                    (20, 11025),
                    (24, 11025),
                    (32, 16000),
                    (40, 16000),
                    (48, 22050),
                    (56, 22050),
                    (64, 24000),
                    (80, 24000),
                    (96, 32000),
                    (112, 44100),
                    (128, 44100),
                    (160, 44100),
                    (192, 44100),
                    (224, 44100),
                    (256, 44100),
                    (320, 48000),
                ),
            ),
            (
                AudioChannels.MONO,
                (
                    (16, 11025),
                    (18, 12000),
                    (20, 12000),
                    (24, 16000),
                    (32, 22050),
                    (40, 22050),
                    (48, 24000),
                    (56, 32000),
                    (64, 44100),
                    (80, 44100),
                    (96, 44100),
                    (112, 44100),
                    (128, 44100),
                    (160, 44100),
                    (192, 44100),
                    (224, 44100),
                    (256, 44100),
                    (320, 44100),
                ),
            ),
        )
        for kbps, rate in table
    ],
    OutputFormat.WAV: [
        (
            {"Audio Codec": AudioCodec.UNCOMPRESSED},
            {
                "Audio Sample Rate": _PCM_RATES,
                "Audio Bit Depth": frozenset(
                    {
                        AudioBitDepth.EIGHT_BIT,
                        AudioBitDepth.SIXTEEN_BIT,
                        AudioBitDepth.THIRTY_TWO_BIT,
                    }
                ),
            },
        ),
        (
            {"Audio Codec": (AudioCodec.IMA_ADPCM, AudioCodec.MICROSOFT_ADPCM)},
            {
                "Audio Sample Rate": _ADPCM_RATES,
                "Audio Bit Depth": _SIXTEEN_BIT_ONLY,
            },
        ),
        (
            {"Audio Codec": (AudioCodec.CCITT_A_LAW, AudioCodec.CCITT_U_LAW)},
            {
                "Audio Sample Rate": _CCITT_RATES,
                "Audio Bit Depth": _SIXTEEN_BIT_ONLY,
            },
        ),
        (
            {"Audio Codec": AudioCodec.GSM_6_10},
            {
                "Audio Sample Rate": _ADPCM_RATES,
                "Audio Bit Depth": _SIXTEEN_BIT_ONLY,
                # AE forces mono for GSM and writes the byte (sample-verified).
                "Audio Channels": frozenset({AudioChannels.MONO}),
            },
        ),
    ],
}


# The container gates which audio families exist; the MPEG layer gates
# the kbps ladder (transcribed literally - the ladders are irregular).
_CONDITIONAL_RULES[OutputFormat.H264].extend(
    [
        (
            {"Multiplexer": MPEGMultiplexer.MP4},
            {"Audio Format": frozenset({MPEGAudioFormat.AAC, MPEGAudioFormat.MPEG})},
        ),
        (
            {"Multiplexer": MPEGMultiplexer.THREEGPP},
            {"Audio Format": frozenset({MPEGAudioFormat.AAC})},
        ),
        (
            {"Multiplexer": MPEGMultiplexer.NONE},
            {
                "Audio Format": frozenset(
                    {MPEGAudioFormat.AAC, MPEGAudioFormat.MPEG, MPEGAudioFormat.PCM}
                )
            },
        ),
        (
            {
                "Audio Format": MPEGAudioFormat.MPEG,
                "Audio Layer": MPEGAudioLayer.LAYER_I,
            },
            {
                "Audio Bitrate": frozenset(
                    {128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448}
                )
            },
        ),
        (
            {
                "Audio Format": MPEGAudioFormat.MPEG,
                "Audio Layer": MPEGAudioLayer.LAYER_II,
                "Audio Channels": AudioChannels.MONO,
            },
            {"Audio Bitrate": frozenset({64, 96, 112, 128, 160, 192})},
        ),
        (
            {
                "Audio Format": MPEGAudioFormat.MPEG,
                "Audio Layer": MPEGAudioLayer.LAYER_II,
                "Audio Channels": AudioChannels.STEREO,
            },
            {
                "Audio Bitrate": frozenset(
                    {64, 96, 112, 128, 160, 192, 224, 256, 320, 384}
                )
            },
        ),
        # HE-AACv2 is parametric stereo: mono is not offered at all.
        (
            {"Audio Codec": AudioCodec.AAC_PLUS_V2},
            {"Audio Channels": frozenset({AudioChannels.STEREO})},
        ),
    ]
)
_CONDITIONAL_RULES[OutputFormat.H264].extend(_aac_bitrate_rows())

# NOTE: Targa's bits-per-pixel radio is NOT coupled to the OM channels
# in the binary: AE-saved files hold RGB + 32 bpp (targa/base.aep) AND
# RGB+Alpha + 24 bpp (tga_rgba.aep) - the Ropt byte only changes when
# the Targa Options dialog itself is visited, like Cineon's FIDO
# bit_depth. The OM Depth setting is the authoritative alpha/depth
# choice; bits_per_pixel is validated as 24/32 only.


# AE keeps the depth paired to the alpha choice: with RGB+Alpha channels
# the dialog offers only "+" depths, with RGB/Alpha only base depths
# (438 video-on corpus modules, 0 exceptions). Encode the pairing as
# generated conditional rows so Depth writes, validate_state and batch
# exits all enforce it through the ordinary lookup. Inserted FIRST so
# codec-specific Depth rows still win the general->specific merge.
_PLUS_DEPTHS = frozenset({_MILLIONS_PLUS, _TRILLIONS_PLUS, _FLOAT_PLUS})
for _fmt, _fmt_rules in _FORMAT_RULES.items():
    _depths = _fmt_rules.get("Depth")
    if _depths is None:
        continue
    _rows = _CONDITIONAL_RULES.setdefault(_fmt, [])
    _rgba_depths = _depths & _PLUS_DEPTHS
    if _rgba_depths:
        _rows.insert(0, ({"Channels": OutputChannels.RGBA}, {"Depth": _rgba_depths}))
    _base_depths = _depths - _PLUS_DEPTHS
    if _base_depths:
        _rows.insert(
            0,
            (
                {"Channels": (OutputChannels.RGB, OutputChannels.ALPHA)},
                {"Depth": _base_depths},
            ),
        )


# Context keys whose write re-resolves dependent settings (the keys AE's
# dialog re-clamps when the value changes). Consumed by the write hooks in
# XmlFormatOptions and OutputModule via
# `OutputModule._apply_singleton_clamps`.
CLAMP_DEPENDENTS: dict[str, tuple[str, ...]] = {
    # Order matters: channels first, so a forced mono (GSM) feeds the
    # rate/depth lookups that follow.
    "Audio Codec": ("Audio Channels", "Audio Sample Rate", "Audio Bit Depth"),
    "Audio Format": ("Audio Sample Rate",),
    "BitRate": ("Audio Sample Rate",),
    "Multiplexer": ("Audio Format",),
    "Video Codec": ("Depth",),
}


def _conditions_match(
    conditions: Mapping[str, object], context: Mapping[str, object]
) -> bool:
    """True when every condition matches the context.

    A tuple condition value means "in"; a context key that is absent
    never matches (permissive degradation).
    """
    for key, expected in conditions.items():
        actual = context.get(key)
        if actual is None:
            return False
        if isinstance(expected, tuple):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def constrained_keys(fmt: OutputFormat) -> frozenset[str]:
    """Every setting key that has (or can have) a rule under `fmt`.

    Drives whole-state validation (`OutputModule.validate_state`): keys
    outside this set are unconstrained for the format and never checked.
    """
    keys = set(_KIND_RULES[fmt.kind])
    keys.update(_FORMAT_RULES.get(fmt, {}))
    for _, constraints in _CONDITIONAL_RULES.get(fmt, []):
        keys.update(constraints)
    return frozenset(keys)


def allowed_values(
    fmt: OutputFormat,
    key: str,
    context: Mapping[str, object] | None = None,
) -> frozenset[object] | None:
    """Allowed values for an output-module setting under `fmt`.

    Args:
        fmt: The output format of the module.
        key: The setting name (`OM_SETTINGS` key or format-option
            context key, e.g. `"Depth"`, `"Audio Codec"`).
        context: Current values of the other settings, used to match
            conditional rules. Missing keys disable the rules that
            need them.

    Returns:
        The allowed value set, or `None` when unconstrained.
    """
    rules: dict[str, frozenset[object]] = {}
    rules.update(_KIND_RULES[fmt.kind])
    rules.update(_FORMAT_RULES.get(fmt, {}))
    if context is None:
        context = {}
    for conditions, constraints in _CONDITIONAL_RULES.get(fmt, []):
        if _conditions_match(conditions, context):
            rules.update(constraints)
    return rules.get(key)
