"""After Effects enumerations.

These enums match the values used in After Effects ExtendScript.

Submodules:
- [general][py_aep.enums.general]: Core layer, footage, project, viewer
  and mask enums.
- [property][py_aep.enums.property]: Property system enums
  (control type, value type, keyframe interpolation).
- [renderer_options][py_aep.enums.renderer_options]: 3D renderer option enums
  (shadow map resolution, environment light shadow resolution).
- [render_settings][py_aep.enums.render_settings]: Render settings enums
  (quality, field render, motion blur, effects, etc.).
- [render_queue][py_aep.enums.render_queue]: Render queue item enums
  (status, log type, settings format).
- [output_module][py_aep.enums.output_module]: Output module enums
  (channels, depth, color mode, format, audio settings, post-render action).
- [format_options][py_aep.enums.format_options]: Format-specific option
  enums (Cineon, JPEG, PNG, OpenEXR, audio/video codecs).
- [text_document][py_aep.enums.text_document]: Text document enums
  (justification, baseline, kerning, font caps, etc.).
- [font_object][py_aep.enums.font_object]: Font object enums
  (technology, type, script).
"""

from __future__ import annotations

from .font_object import CTFontTechnology, CTFontType, CTScript
from .format_options import (
    AudioCodec,
    AudioInterleave,
    CineonFileFormat,
    DnxResolution,
    Hdr10ColorPrimaries,
    JpegFormatType,
    MPEGAudioFormat,
    MPEGAudioLayer,
    MPEGMultiplexer,
    MPEGMuxStreamCompatibility,
    MPEGProfile,
    OpenExrCompression,
    PngCompression,
    VideoCodec,
)
from .general import (
    AlphaMode,
    AutoOrientType,
    BitsPerChannel,
    BlendingMode,
    ChannelType,
    CloseOptions,
    ColorManagementSystem,
    FastPreviewType,
    FeetFramesFilmType,
    FieldSeparationType,
    FillLightingCorrectionType,
    FillMethodType,
    FillOutputDepthType,
    FillRangeType,
    FootageTimecodeDisplayStartType,
    FrameBlendingType,
    FramesCountType,
    GpuAccelType,
    GuideOrientationType,
    ImportAsType,
    ItemType,
    Label,
    Language,
    LayerQuality,
    LayerSamplingQuality,
    LayerType,
    LightType,
    LinearLightMode,
    LoopMode,
    LutInterpolationMethod,
    MaskFeatherFalloff,
    MaskMode,
    MaskMotionBlur,
    ParametricMeshType,
    PlayMode,
    PREFType,
    ProjectThread,
    PropertyType,
    PulldownMethod,
    PulldownPhase,
    PurgeTarget,
    ResolveType,
    TimeDisplayType,
    ToolType,
    TrackMatteType,
    ViewerType,
)
from .output_module import (
    AudioBitDepth,
    AudioChannels,
    AudioSampleRate,
    ConvertToLinearLight,
    FormatKind,
    OutputAudio,
    OutputChannels,
    OutputColorDepth,
    OutputColorMode,
    OutputFormat,
    PostRenderAction,
    ResizeQuality,
)
from .property import (
    KeyframeInterpolationType,
    PropertyControlType,
    PropertyValueType,
)
from .render_queue import (
    GetSettingsFormat,
    LogType,
    RQItemStatus,
)
from .render_settings import (
    ColorDepthSetting,
    DiskCacheSetting,
    EffectsSetting,
    FieldRender,
    FrameBlendingSetting,
    FrameRateSetting,
    GuideLayers,
    MotionBlurSetting,
    PostRenderActionSetting,
    ProxyUseSetting,
    PulldownSetting,
    RenderQuality,
    SoloSwitchesSetting,
    TimeSpanSource,
)
from .renderer_options import (
    EnvironmentLightShadowResolution,
    ShadowMapResolution,
)
from .text_document import (
    AutoKernType,
    BaselineDirection,
    BoxAutoFitPolicy,
    BoxFirstBaselineAlignment,
    BoxVerticalAlignment,
    ComposerEngine,
    DigitSet,
    FontBaselineOption,
    FontCapsOption,
    LeadingType,
    LineJoinType,
    LineOrientation,
    ParagraphDirection,
    ParagraphJustification,
    VariableFontSpacing,
)

__all__ = [
    # font_object
    "CTFontTechnology",
    "CTFontType",
    "CTScript",
    # format_options
    "AudioCodec",
    "AudioInterleave",
    "CineonFileFormat",
    "DnxResolution",
    "Hdr10ColorPrimaries",
    "JpegFormatType",
    "MPEGAudioFormat",
    "MPEGAudioLayer",
    "MPEGMultiplexer",
    "MPEGMuxStreamCompatibility",
    "MPEGProfile",
    "OpenExrCompression",
    "PngCompression",
    "VideoCodec",
    # general
    "AlphaMode",
    "AutoOrientType",
    "BitsPerChannel",
    "BlendingMode",
    "ChannelType",
    "CloseOptions",
    "ColorManagementSystem",
    "FastPreviewType",
    "FeetFramesFilmType",
    "FieldSeparationType",
    "FillLightingCorrectionType",
    "FillMethodType",
    "FillOutputDepthType",
    "FillRangeType",
    "FootageTimecodeDisplayStartType",
    "FormatKind",
    "FrameBlendingType",
    "FramesCountType",
    "GpuAccelType",
    "GuideOrientationType",
    "ImportAsType",
    "ItemType",
    "Label",
    "Language",
    "LayerQuality",
    "LayerSamplingQuality",
    "LayerType",
    "LightType",
    "LinearLightMode",
    "LoopMode",
    "LutInterpolationMethod",
    "MaskFeatherFalloff",
    "MaskMode",
    "MaskMotionBlur",
    "ParametricMeshType",
    "PlayMode",
    "PREFType",
    "ProjectThread",
    "PropertyType",
    "PulldownMethod",
    "PulldownPhase",
    "PurgeTarget",
    "ResolveType",
    "TimeDisplayType",
    "ToolType",
    "TrackMatteType",
    "ViewerType",
    # output_module
    "AudioBitDepth",
    "AudioChannels",
    "AudioSampleRate",
    "ConvertToLinearLight",
    "OutputAudio",
    "OutputChannels",
    "OutputColorDepth",
    "OutputColorMode",
    "OutputFormat",
    "ResizeQuality",
    # property
    "KeyframeInterpolationType",
    "PropertyControlType",
    "PropertyValueType",
    # renderer_options
    "EnvironmentLightShadowResolution",
    "ShadowMapResolution",
    # render_queue
    "GetSettingsFormat",
    "LogType",
    "PostRenderAction",
    "RQItemStatus",
    # render_settings
    "ColorDepthSetting",
    "DiskCacheSetting",
    "EffectsSetting",
    "FieldRender",
    "FrameBlendingSetting",
    "FrameRateSetting",
    "GuideLayers",
    "MotionBlurSetting",
    "PostRenderActionSetting",
    "ProxyUseSetting",
    "PulldownSetting",
    "RenderQuality",
    "SoloSwitchesSetting",
    "TimeSpanSource",
    # text_document
    "AutoKernType",
    "BaselineDirection",
    "BoxAutoFitPolicy",
    "BoxFirstBaselineAlignment",
    "BoxVerticalAlignment",
    "ComposerEngine",
    "DigitSet",
    "FontBaselineOption",
    "FontCapsOption",
    "LeadingType",
    "LineJoinType",
    "LineOrientation",
    "ParagraphDirection",
    "ParagraphJustification",
    "VariableFontSpacing",
]
