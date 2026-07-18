"""Output module enumerations for After Effects.

These enums match the values used in After Effects ExtendScript.
"""

from __future__ import annotations

from enum import IntEnum


class OutputChannels(IntEnum):
    """Output channels setting.

    Used in OutputModule Settings > Channels

    Not documented in AE scripting reference.
    """

    RGB = 0
    RGBA = 1
    ALPHA = 2

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _OUTPUT_CHANNELS_LABELS[self.value]


_OUTPUT_CHANNELS_LABELS: dict[int, str] = {
    0: "RGB",
    1: "RGB + Alpha",
    2: "Alpha",
}


class OutputColorDepth(IntEnum):
    """Output color depth in total bits per pixel.

    The value represents total bits per pixel: 24 or 32 for 8 bpc
    (with/without alpha), 48 or 64 for 16 bpc, 96 or 128 for 32 bpc
    (floating point). The `+` label suffix indicates alpha is included.

    Used in OutputModule Settings > Depth

    Not documented in AE scripting reference.
    """

    FLOATING_POINT_GRAY = -32  # 32 bpc gray (single channel float)
    COLORS_256 = 8  # 8 bpc indexed (256 colors)
    MILLIONS_OF_COLORS = 24  # 8 bpc RGB (24 bpp)
    MILLIONS_OF_COLORS_PLUS = 32  # 8 bpc RGBA (32 bpp)
    GRAYS_256 = 40  # 8 bpc grayscale (256 grays)
    TRILLIONS_OF_COLORS = 48  # 16 bpc RGB (48 bpp)
    TRILLIONS_OF_COLORS_PLUS = 64  # 16 bpc RGBA (64 bpp)
    FLOATING_POINT = 96  # 32 bpc RGB (96 bpp)
    FLOATING_POINT_PLUS = 128  # 32 bpc RGBA (128 bpp)

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _OUTPUT_COLOR_DEPTH_LABELS[self.value]

    @classmethod
    def from_binary(cls, value: int) -> OutputColorDepth:
        """Decode the `Rouu` depth field.

        Modern AE builds write noise in the upper three bytes of the s4
        field with the real bpp in the low byte (constant `0xF8529Axx`
        observed across every AE 2026 save on this corpus); older files
        store the plain value. Raises `ValueError` when neither form
        decodes, mirroring a plain enum call.
        """
        if value in cls._value2member_map_:
            return cls(value)
        low_byte = value & 0xFF
        if low_byte in cls._value2member_map_:
            return cls(low_byte)
        raise ValueError(f"{value!r} is not a valid {cls.__name__}")


_OUTPUT_COLOR_DEPTH_LABELS: dict[int, str] = {
    -32: "Floating Point Gray",
    8: "256 Colors",
    24: "Millions of Colors",
    32: "Millions of Colors+",
    40: "256 Grays",
    48: "Trillions of Colors",
    64: "Trillions of Colors+",
    96: "Floating Point",
    128: "Floating Point+",
}


class OutputColorMode(IntEnum):
    """Output color mode (premultiplied vs straight).

    Used in OutputModule Settings > Color

    Not documented in AE scripting reference.
    """

    STRAIGHT_UNMATTED = 0
    PREMULTIPLIED = 1

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _OUTPUT_COLOR_MODE_LABELS[self.value]


_OUTPUT_COLOR_MODE_LABELS: dict[int, str] = {
    0: "Straight (Unmatted)",
    1: "Premultiplied (Matted)",
}


class OutputAudio(IntEnum):
    """Audio output mode.

    Used in OutputModule Settings > Output Audio

    Not documented in AE scripting reference.
    """

    OFF = 1
    ON = 2
    AUTO = 3

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _OUTPUT_AUDIO_LABELS[self.value]


_OUTPUT_AUDIO_LABELS: dict[int, str] = {
    1: "Off",
    2: "On",
    3: "Auto",
}


class FormatKind(IntEnum):
    """Output plugin capability class.

    Mirrors the capability flags an AE output plugin declares
    (`AEIO_MFlag_FILE_SEQUENCE` / `_VIDEO` / `_AUDIO` in the AE SDK's
    `AE_IO.h`). The `.aep` binary carries no such flag (all `Rouu`
    reserved bytes are identical across formats), so the classification
    is static data keyed by the format identity.

    Not available in ExtendScript.
    """

    AUDIO = 1
    """Audio stream only (AIFF, MP3, WAV): video output is always off."""

    MOVIE = 2
    """Single movie file, video and/or audio (AVI, H.264, QuickTime)."""

    SEQUENCE = 3
    """One still image per frame (TIFF, PNG, ...): audio is always off."""


class OutputFormat(IntEnum):
    """Output file format.

    Used in OutputModule Settings > Format

    Not documented in AE scripting reference.
    """

    AIFF = 0
    AVI = 1
    DPX_CINEON_SEQUENCE = 2
    H264 = 3
    IFF_SEQUENCE = 4
    JPEG_SEQUENCE = 5
    MP3 = 6
    OPENEXR_SEQUENCE = 7
    PNG_SEQUENCE = 8
    PHOTOSHOP_SEQUENCE = 9
    QUICKTIME = 10
    RADIANCE_SEQUENCE = 11
    SGI_SEQUENCE = 12
    TIFF_SEQUENCE = 13
    TARGA_SEQUENCE = 14
    WAV = 15

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _OUTPUT_FORMAT_LABELS[self.value]

    @property
    def kind(self) -> FormatKind:
        """Whether this format is an audio file, a movie, or a still
        sequence. See [FormatKind][]."""
        return _OUTPUT_FORMAT_KINDS[self.value]

    @classmethod
    def from_format_id(cls, format_id: str | bytes) -> OutputFormat:
        """Convert a Roou 4-char format identifier to OutputFormat.

        Args:
            format_id: The 4-char format identifier from the Roou chunk
                (e.g. `"H264"`, `"TIF "`, `"png!"`).

        Raises:
            ValueError: If the format identifier is not recognised.
        """
        if isinstance(format_id, bytes):
            format_id = format_id.decode("ascii")
        try:
            return _FORMAT_ID_TO_OUTPUT_FORMAT[format_id]
        except KeyError:
            raise ValueError(
                f"Unknown output format identifier: {format_id!r}"
            ) from None

    def to_format_id(self) -> str:
        """Convert OutputFormat to a Roou 4-char format identifier."""
        return _OUTPUT_FORMAT_TO_FORMAT_ID[self]


_OUTPUT_FORMAT_LABELS: dict[int, str] = {
    0: "AIFF",
    1: "AVI",
    2: "DPX/Cineon Sequence",
    3: "H.264",
    4: "IFF Sequence",
    5: "JPEG Sequence",
    6: "MP3",
    7: "OpenEXR Sequence",
    8: "PNG Sequence",
    9: "Photoshop Sequence",
    10: "QuickTime",
    11: "Radiance Sequence",
    12: "SGI Sequence",
    13: "TIFF Sequence",
    14: "Targa Sequence",
    15: "WAV",
}


# Explicit classification (see FormatKind): never derive this from names -
# OM/template names are user-defined and the binary has no category flag.
_OUTPUT_FORMAT_KINDS: dict[int, FormatKind] = {
    OutputFormat.AIFF: FormatKind.AUDIO,
    OutputFormat.AVI: FormatKind.MOVIE,
    OutputFormat.DPX_CINEON_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.H264: FormatKind.MOVIE,
    OutputFormat.IFF_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.JPEG_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.MP3: FormatKind.AUDIO,
    OutputFormat.OPENEXR_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.PNG_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.PHOTOSHOP_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.QUICKTIME: FormatKind.MOVIE,
    OutputFormat.RADIANCE_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.SGI_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.TIFF_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.TARGA_SEQUENCE: FormatKind.SEQUENCE,
    OutputFormat.WAV: FormatKind.AUDIO,
}


_FORMAT_ID_TO_OUTPUT_FORMAT: dict[str, OutputFormat] = {
    "AIFF": OutputFormat.AIFF,
    ".AVI": OutputFormat.AVI,
    "sDPX": OutputFormat.DPX_CINEON_SEQUENCE,
    "H264": OutputFormat.H264,
    "IFF ": OutputFormat.IFF_SEQUENCE,
    "JPEG": OutputFormat.JPEG_SEQUENCE,
    "Mp3 ": OutputFormat.MP3,
    "oEXR": OutputFormat.OPENEXR_SEQUENCE,
    "png!": OutputFormat.PNG_SEQUENCE,
    "8BPS": OutputFormat.PHOTOSHOP_SEQUENCE,
    "MooV": OutputFormat.QUICKTIME,
    "RHDR": OutputFormat.RADIANCE_SEQUENCE,
    "SGI ": OutputFormat.SGI_SEQUENCE,
    "TIF ": OutputFormat.TIFF_SEQUENCE,
    "TPIC": OutputFormat.TARGA_SEQUENCE,
    "wao_": OutputFormat.WAV,
}

_OUTPUT_FORMAT_TO_FORMAT_ID: dict[OutputFormat, str] = {
    v: k for k, v in _FORMAT_ID_TO_OUTPUT_FORMAT.items()
}


class AudioBitDepth(IntEnum):
    """Audio bit depth.

    Used in OutputModule Settings > Audio > Format

    Not documented in AE scripting reference.
    """

    EIGHT_BIT = 1
    SIXTEEN_BIT = 2
    TWENTY_FOUR_BIT = 3
    THIRTY_TWO_BIT = 4

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _AUDIO_BIT_DEPTH_LABELS[self.value]

    @classmethod
    def from_binary(cls, value: int) -> AudioBitDepth:
        """Convert binary value to AudioBitDepth."""
        if value in cls._value2member_map_:
            return cls(value)
        return cls.THIRTY_TWO_BIT


_AUDIO_BIT_DEPTH_LABELS: dict[int, str] = {
    1: "8 Bit",
    2: "16 Bit",
    3: "24 Bit",
    4: "32 Bit",
}


class AudioChannels(IntEnum):
    """Audio channels.

    Used in OutputModule Settings > Audio > Channels

    Not documented in AE scripting reference.
    """

    MONO = 1
    STEREO = 2

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _AUDIO_CHANNELS_LABELS[self.value]

    @classmethod
    def from_binary(cls, value: int) -> AudioChannels:
        """Convert binary value to AudioChannels (0 or unknown defaults to STEREO)."""
        if value == 1:
            return cls.MONO
        return cls.STEREO


_AUDIO_CHANNELS_LABELS: dict[int, str] = {
    1: "Mono",
    2: "Stereo",
}


class ResizeQuality(IntEnum):
    """Resize quality setting.

    Used in OutputModule Settings > Stretch > Quality

    Not documented in AE scripting reference.
    """

    LOW = 0
    HIGH = 1

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _RESIZE_QUALITY_LABELS[self.value]


_RESIZE_QUALITY_LABELS: dict[int, str] = {
    0: "Low",
    1: "High",
}


class AudioSampleRate(IntEnum):
    """Audio sample rate in Hz.

    Standard sample rates available in After Effects output module
    audio settings.

    Used in OutputModule Settings > Audio > Sample Rate

    Not documented in AE scripting reference.
    """

    OFF = -1
    RATE_8000 = 8000
    RATE_11025 = 11025
    RATE_12000 = 12000
    """Only reachable through MP3 mono at 18/20 kbps (AE-saved evidence);
    no other format offers it."""
    RATE_16000 = 16000
    RATE_22050 = 22050
    RATE_24000 = 24000
    RATE_32000 = 32000
    RATE_44100 = 44100
    RATE_48000 = 48000
    RATE_88200 = 88200
    RATE_96000 = 96000

    @property
    def label(self) -> str:
        """ExtendScript STRING format label (e.g. `"48.000 kHz"`)."""
        if self.value <= 0:
            return ""
        return f"{self.value / 1000:.3f} kHz"

    @classmethod
    def from_binary(cls, value: float) -> AudioSampleRate:
        """Convert binary audio sample rate value.

        The binary field is stored as `f8` (float).

        Unknown or negative values (e.g. `-1` when audio is disabled)
        are mapped to `OFF`.
        """
        int_value = round(value)
        if int_value in cls._value2member_map_:
            return cls(int_value)
        return cls.OFF

    @staticmethod
    def to_binary(value: AudioSampleRate) -> float:
        """Convert to binary float for the `f8` field."""
        return float(round(value))


class ConvertToLinearLight(IntEnum):
    """Convert to Linear Light output module setting.

    Controls whether the output is converted to linear light color space
    during rendering. When enabled only for 32 bpc, the conversion is
    skipped for projects rendered at lower bit depths.

    Used in OutputModule Settings > Color Management > Convert to Linear Light

    Not documented in AE scripting reference.
    """

    OFF = 0
    ON = 1
    ON_FOR_32_BPC = 2

    @property
    def label(self) -> str:
        """ExtendScript STRING format label."""
        return _CONVERT_TO_LINEAR_LIGHT_LABELS[self.value]


_CONVERT_TO_LINEAR_LIGHT_LABELS: dict[int, str] = {
    0: "Off",
    1: "On",
    2: "On for 32 bpc",
}


class PostRenderAction(IntEnum):
    """Action after rendering completes."""

    NONE = 3612
    IMPORT = 3613
    IMPORT_AND_REPLACE_USAGE = 3614
    SET_PROXY = 3615

    @classmethod
    def from_binary(cls, value: int) -> PostRenderAction:
        """Convert binary value to PostRenderAction."""
        try:
            return cls(value + 3612)
        except ValueError:
            return cls.NONE

    def to_binary(self) -> int:
        """Convert PostRenderAction to binary value."""
        return int(self) - 3612
