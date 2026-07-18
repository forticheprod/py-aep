"""Format options enumerations for After Effects output modules."""

from __future__ import annotations

from enum import IntEnum


class CineonFileFormat(IntEnum):
    """Cineon output file format type.

    Not available in ExtendScript.
    """

    FIDO_CINEON = 0
    DPX = 1


class JpegFormatType(IntEnum):
    """JPEG format option type.

    Not available in ExtendScript.
    """

    BASELINE_STANDARD = 0
    BASELINE_OPTIMIZED = 1
    PROGRESSIVE = 2


class PngCompression(IntEnum):
    """PNG compression / interlace mode.

    Not available in ExtendScript.
    """

    NONE = 0
    INTERLACED = 1


class Hdr10ColorPrimaries(IntEnum):
    """Color primaries for HDR10 metadata embedded in PNG exports.

    Not available in ExtendScript.
    """

    REC709 = 0
    P3_D65 = 1
    REC2020 = 2


class OpenExrCompression(IntEnum):
    """OpenEXR compression method.

    Not available in ExtendScript.
    """

    NONE = 0
    RLE = 1
    ZIP = 2
    ZIP16 = 3
    PIZ = 4
    PXR24 = 5
    B44 = 6
    B44A = 7
    DWAA = 8
    DWAB = 9
    HTJ2K_256 = 10
    HTJ2K_32 = 11


class MPEGProfile(IntEnum):
    """H.264 encoding profile (the `Profile` dropdown).

    Stored in the `ADBEVideoMPEGProfile` XML parameter, except for
    `BASELINE`: After Effects writes NO parameter at all for Baseline, so
    it is represented by the `-1` sentinel (assigning it removes the
    parameter; reading an absent parameter returns it). `-1` is never
    stored in a file.

    The dropdown's `Auto` is resolved at save time and is not a distinct
    stored value - an Auto module was observed storing `1`, so it reads
    back as `MAIN`.

    Values mapped from AE 2026-authored samples. `2` is unobserved (the
    dropdown offers no fifth profile), so it is absent from this enum and
    reads back as a raw `int` if a file ever holds it.

    Not available in ExtendScript.
    """

    BASELINE = -1
    MAIN = 1
    HIGH = 3
    HIGH10 = 4


class DnxResolution(IntEnum):
    """DNxHR / DNxHD resolution preset.

    The `Resolution` dropdown of the DNxHR/DNxHD codec options, stored in
    the `ADBEVideoResolution` XML parameter. Only meaningful when the
    module's `video_codec` is `VideoCodec.DNXHR_DNXHD`; the parameter
    survives a codec change, so it can read back stale under another codec.

    Member names follow the dropdown labels. Ids are a contiguous
    1001-1019 block, mapped one-to-one from AE 2026-authored samples
    (`samples/models/format_options/dnx/`).

    Not available in ExtendScript.
    """

    DNXHD_720P_HQX_10_BIT = 1001
    DNXHD_720P_HQ_8_BIT = 1002
    DNXHD_720P_SQ_8_BIT = 1003
    DNXHD_720P_SQ_THIN_RASTER_8_BIT = 1004
    DNXHD_1080I_HQX_10_BIT = 1005
    DNXHD_1080I_HQ_8_BIT = 1006
    DNXHD_1080I_SQ_8_BIT = 1007
    DNXHD_1080I_SQ_THIN_RASTER_8_BIT = 1008
    DNXHD_1080P_RGB_444_10_BIT = 1009
    DNXHD_1080P_HQX_10_BIT = 1010
    DNXHD_1080P_HQ_8_BIT = 1011
    DNXHD_1080P_SQ_8_BIT = 1012
    DNXHD_1080P_SQ_THIN_RASTER_8_BIT = 1013
    DNXHD_1080P_LB_8_BIT = 1014
    DNXHR_RGB_444_12_BIT = 1015
    DNXHR_HQX_10_BIT = 1016
    DNXHR_HQ_8_BIT = 1017
    DNXHR_SQ_8_BIT = 1018
    DNXHR_LB_8_BIT = 1019


class AudioCodec(IntEnum):
    """Audio codec identifier stored as a 32-bit integer.

    These values are extracted from the `ADBEAudioCodec` parameter in the
    XML-based format options of output modules (AVI, H.264, MP3, QuickTime,
    WAV).

    Not available in ExtendScript.
    """

    UNCOMPRESSED = 1380013856
    """Uncompressed / PCM audio."""

    IMA_ADPCM = 1
    """IMA ADPCM."""

    MICROSOFT_ADPCM = 2
    """Microsoft ADPCM."""

    CCITT_A_LAW = 3
    """CCITT A-Law."""

    CCITT_U_LAW = 4
    """CCITT u-Law."""

    GSM_6_10 = 5
    """GSM 6.10."""

    AAC = 1094796064
    """AAC (Advanced Audio Coding) (FourCC `'AAC '`)."""

    AAC_PLUS_V1 = 1094796081
    """HE-AAC / AAC+ Version 1 (FourCC `'AAC1'`)."""

    AAC_PLUS_V2 = 1094796082
    """HE-AACv2 / AAC+ Version 2 (FourCC `'AAC2'`)."""


class VideoCodec(IntEnum):
    """Video codec FourCC identifier stored.

    These values are extracted from the `ADBEVideoCodec` parameter in the
    XML-based format options of output modules (AVI, H.264, QuickTime).

    Not available in ExtendScript.
    """

    NONE = 541215044
    """No codec / uncompressed DIB (FourCC `' BID'`)."""

    V210 = 808530550
    """V210 10-bit YUV (FourCC `'012v'`). AVI variant."""

    UNCOMPRESSED_YUV_8_BIT_422 = 846624121
    """Uncompressed YUV 8 bit 4:2:2 (FourCC `'2vuy'`)."""

    DNXHR_DNXHD = 1096180846
    """DNxHR/DNxHD (FourCC `'AVdn'`)."""

    GOPRO_CINEFORM = 1128679492
    """GoPro CineForm (FourCC `'CFHD'`)."""

    INTEL_IYUV = 1448433993
    """Intel IYUV codec (FourCC `'VUYI'`)."""

    UYVY = 1498831189
    """Uncompressed UYVY 422 8-bit (FourCC `'YVYU'`). AVI variant."""

    APPLE_PRORES_422 = 1634755438
    """Apple ProRes 422 (FourCC `'apcn'`)."""

    APPLE_PRORES_422_HQ = 1634755432
    """Apple ProRes 422 HQ (FourCC `'apch'`)."""

    APPLE_PRORES_422_LT = 1634755443
    """Apple ProRes 422 LT (FourCC `'apcs'`)."""

    APPLE_PRORES_422_PROXY = 1634755439
    """Apple ProRes 422 Proxy (FourCC `'apco'`)."""

    APPLE_PRORES_4444 = 1634743400
    """Apple ProRes 4444 (FourCC `'ap4h'`)."""

    APPLE_PRORES_4444_XQ = 1634743416
    """Apple ProRes 4444 XQ (FourCC `'ap4x'`)."""

    AVC1 = 1635148593
    """H.264 / AVC (FourCC `'avc1'`)."""

    DV25_NTSC = 1685480224
    """DV25 NTSC (FourCC `'dvc '`)."""

    DV25_PAL = 1685480304
    """DV25 PAL (FourCC `'dvcp'`)."""

    DV50_NTSC = 1685468526
    """DV50 NTSC (FourCC `'dv5n'`)."""

    DV50_PAL = 1685468528
    """DV50 PAL (FourCC `'dv5p'`)."""

    DV_24P = 1685288498
    """DV 24p Advanced (FourCC `'dsv2'`). AVI variant."""

    DV_NTSC = 1685288558
    """DV NTSC (FourCC `'dsvn'`). AVI variant."""

    DV_PAL = 1685288560
    """DV PAL (FourCC `'dsvp'`). AVI variant."""

    DVCPRO_HD_1080I50 = 1685481525
    """DVCPRO HD 1080i50 (FourCC `'dvh5'`)."""

    DVCPRO_HD_1080I60 = 1685481526
    """DVCPRO HD 1080i60 (FourCC `'dvh6'`)."""

    DVCPRO_HD_1080P25 = 1685481522
    """DVCPRO HD 1080p25 (FourCC `'dvh2'`)."""

    DVCPRO_HD_1080P30 = 1685481523
    """DVCPRO HD 1080p30 (FourCC `'dvh3'`)."""

    DVCPRO_HD_720P50 = 1685481585
    """DVCPRO HD 720p50 (FourCC `'dvhq'`)."""

    DVCPRO_HD_720P60 = 1685481584
    """DVCPRO HD 720p60 (FourCC `'dvhp'`)."""

    DV25_NTSC_24P = 1886532148
    """DV25 NTSC 24p (FourCC `'pr24'`)."""

    UNCOMPRESSED_RGB_8_BIT = 1918990112
    """None (Uncompressed RGB 8-bit) (FourCC `'raw '`)."""

    ANIMATION = 1919706400
    """Animation / RLE (FourCC `'rle '`)."""

    UNCOMPRESSED_YUV_10_BIT_422 = 1983000880
    """Uncompressed YUV 10 bit 4:2:2 (FourCC `'v210'`)."""


class AudioInterleave(IntEnum):
    """AVI audio interleave interval.

    These values are extracted from the `ADBEAudioInterleave` parameter in
    the XML-based format options of AVI output modules. The dialog's
    `None` choice stores no parameter at all (the accessor reads `None`).

    Not available in ExtendScript.
    """

    ONE_FRAME = 1
    HALF_SECOND = 2
    ONE_SECOND = 3
    TWO_SECONDS = 4


class MPEGAudioLayer(IntEnum):
    """MPEG-1 audio layer.

    These values are extracted from the `ADBEMPEGAudioLayer` parameter in
    the XML-based format options of H.264 output modules (only meaningful
    when the audio format is MPEG).

    Not available in ExtendScript.
    """

    LAYER_I = 1
    LAYER_II = 2


class MPEGAudioFormat(IntEnum):
    """MPEG audio format identifier.

    The dialog's top-level `Audio Format` dropdown (AAC / MPEG / PCM) for
    H.264 output modules; despite the `MPEG` prefix in the parameter name
    it selects among all three families (AE-sample verified).

    These values are extracted from the `ADBEMPEGAudioFormat` parameter in
    the XML-based format options of output modules (H.264, QuickTime).

    Not available in ExtendScript.
    """

    AAC = 1094796064
    """AAC (Advanced Audio Coding) (FourCC `'AAC '`)."""

    MPEG = 1297106247
    """MPEG audio (FourCC `'MPEG'`)."""

    PCM = 1346587936
    """PCM / uncompressed audio (FourCC `'PCM '`)."""


class MPEGMultiplexer(IntEnum):
    """MPEG multiplexer identifier.

    These values are extracted from the `ADBEMPEGMultiplexer` parameter in
    the XML-based format options of output modules (H.264, QuickTime).

    Not available in ExtendScript.
    """

    THREEGPP = 860311632
    """3GPP container (FourCC `'3GPP'`)."""

    MP4 = 1297101856
    """MP4 container (FourCC `'MP4 '`)."""

    NONE = 1313820229
    """No multiplexer (FourCC `'NONE'`)."""


class MPEGMuxStreamCompatibility(IntEnum):
    """MPEG mux stream compatibility identifier.

    These values are extracted from the `ADBEMPEGMuxStreamCompatibility`
    parameter in the XML-based format options of output modules (H.264, QuickTime).

    Not available in ExtendScript.
    """

    IPOD = 1229999940
    """iPod compatibility (FourCC `'IPOD'`)."""

    PSP = 1347637280
    """PSP compatibility (FourCC `'PSP '`)."""

    STD = 1398031392
    """Standard compatibility (FourCC `'STD '`)."""
