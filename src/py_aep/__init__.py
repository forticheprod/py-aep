"""py_aep - A .aep (After Effects Project) parser."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata  # type: ignore[import,no-redef]  # Python 3.7

from .enums import (
    AlphaMode,
    AudioBitDepth,
    AudioChannels,
    AudioSampleRate,
    AutoKernType,
    AutoOrientType,
    BaselineDirection,
    BitsPerChannel,
    BlendingMode,
    BoxAutoFitPolicy,
    BoxFirstBaselineAlignment,
    BoxVerticalAlignment,
    ChannelType,
    CloseOptions,
    ColorDepthSetting,
    ColorManagementSystem,
    ComposerEngine,
    CTFontTechnology,
    CTFontType,
    CTScript,
    DigitSet,
    DiskCacheSetting,
    EffectsSetting,
    EnvironmentLightShadowResolution,
    FastPreviewType,
    FeetFramesFilmType,
    FieldRender,
    FieldSeparationType,
    FillLightingCorrectionType,
    FillMethodType,
    FillOutputDepthType,
    FillRangeType,
    FontBaselineOption,
    FontCapsOption,
    FootageTimecodeDisplayStartType,
    FrameBlendingSetting,
    FrameBlendingType,
    FrameRateSetting,
    FramesCountType,
    GetSettingsFormat,
    GpuAccelType,
    GuideLayers,
    GuideOrientationType,
    ImportAsType,
    KeyframeInterpolationType,
    Label,
    Language,
    LayerQuality,
    LayerSamplingQuality,
    LeadingType,
    LightType,
    LinearLightMode,
    LineJoinType,
    LineOrientation,
    LogType,
    LoopMode,
    LutInterpolationMethod,
    MaskFeatherFalloff,
    MaskMode,
    MaskMotionBlur,
    MotionBlurSetting,
    OutputAudio,
    OutputChannels,
    OutputColorDepth,
    OutputColorMode,
    OutputFormat,
    ParagraphDirection,
    ParagraphJustification,
    ParametricMeshType,
    PlayMode,
    PostRenderAction,
    PREFType,
    ProjectThread,
    PropertyControlType,
    PropertyType,
    PropertyValueType,
    ProxyUseSetting,
    PulldownMethod,
    PulldownPhase,
    PulldownSetting,
    PurgeTarget,
    RenderQuality,
    ResizeQuality,
    ResolveType,
    RQItemStatus,
    ShadowMapResolution,
    SoloSwitchesSetting,
    TimeDisplayType,
    TimeSpanSource,
    ToolType,
    TrackMatteType,
    ViewerType,
)
from .models import (
    CURRENT_VALUE,
    AdvancedRendererOptions,
    Application,
    AVItem,
    AVLayer,
    CameraLayer,
    Cinema4DRendererOptions,
    CineonFormatOptions,
    ClassicRendererOptions,
    CompItem,
    FeatherPoint,
    FileSource,
    FolderItem,
    FontObject,
    FootageItem,
    FootageSource,
    Guide,
    ImportOptions,
    Item,
    JpegFormatOptions,
    Keyframe,
    KeyframeEase,
    Layer,
    LightLayer,
    MarkerValue,
    MaskPropertyGroup,
    OpenExrFormatOptions,
    OutputModule,
    ParametricMeshLayer,
    PlaceholderSource,
    PngFormatOptions,
    Preferences,
    Project,
    Property,
    PropertyBase,
    PropertyGroup,
    RayTracedRendererOptions,
    RendererOptionsBase,
    RenderQueue,
    RenderQueueItem,
    SettingsView,
    Shape,
    ShapeLayer,
    SolidSource,
    TargaFormatOptions,
    TextDocument,
    TextLayer,
    ThreeDModelLayer,
    TiffFormatOptions,
    View,
    Viewer,
    ViewOptions,
    XmlFormatOptions,
)
from .parsers.comp_presets import CompPreset
from .resolvers.source_layers import list_layers

try:
    __version__ = importlib_metadata.version("py_aep")
except importlib_metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "AdvancedRendererOptions",
    "AlphaMode",
    "Application",
    "AudioBitDepth",
    "AudioChannels",
    "AudioSampleRate",
    "AutoKernType",
    "AutoOrientType",
    "AVItem",
    "AVLayer",
    "BaselineDirection",
    "BitsPerChannel",
    "BlendingMode",
    "BoxAutoFitPolicy",
    "BoxFirstBaselineAlignment",
    "BoxVerticalAlignment",
    "CameraLayer",
    "ChannelType",
    "Cinema4DRendererOptions",
    "CineonFormatOptions",
    "ClassicRendererOptions",
    "CloseOptions",
    "ColorDepthSetting",
    "ColorManagementSystem",
    "CompPreset",
    "CompItem",
    "ComposerEngine",
    "CTFontTechnology",
    "CTFontType",
    "CTScript",
    "DigitSet",
    "DiskCacheSetting",
    "EffectsSetting",
    "EnvironmentLightShadowResolution",
    "FastPreviewType",
    "FeatherPoint",
    "FeetFramesFilmType",
    "FieldRender",
    "FieldSeparationType",
    "FileSource",
    "FillLightingCorrectionType",
    "FillMethodType",
    "FillOutputDepthType",
    "FillRangeType",
    "FolderItem",
    "FontBaselineOption",
    "FontCapsOption",
    "FontObject",
    "FootageItem",
    "FootageSource",
    "FootageTimecodeDisplayStartType",
    "FrameBlendingSetting",
    "FrameBlendingType",
    "FrameRateSetting",
    "FramesCountType",
    "GetSettingsFormat",
    "GpuAccelType",
    "GuideOrientationType",
    "GuideLayers",
    "Guide",
    "ImportAsType",
    "ImportOptions",
    "Item",
    "CURRENT_VALUE",
    "JpegFormatOptions",
    "Keyframe",
    "KeyframeEase",
    "KeyframeInterpolationType",
    "Label",
    "Language",
    "Layer",
    "LayerQuality",
    "LayerSamplingQuality",
    "LeadingType",
    "LightLayer",
    "LightType",
    "LinearLightMode",
    "LineJoinType",
    "LineOrientation",
    "list_layers",
    "LogType",
    "LoopMode",
    "LutInterpolationMethod",
    "MarkerValue",
    "MaskFeatherFalloff",
    "MaskMode",
    "MaskMotionBlur",
    "MaskPropertyGroup",
    "MotionBlurSetting",
    "new",
    "OpenExrFormatOptions",
    "OutputAudio",
    "OutputChannels",
    "OutputColorDepth",
    "OutputColorMode",
    "OutputFormat",
    "OutputModule",
    "ParametricMeshLayer",
    "ParametricMeshType",
    "ParagraphDirection",
    "ParagraphJustification",
    "parse",
    "PlaceholderSource",
    "PlayMode",
    "PngFormatOptions",
    "PostRenderAction",
    "Preferences",
    "PREFType",
    "Project",
    "ProjectThread",
    "Property",
    "PropertyBase",
    "PropertyControlType",
    "PropertyGroup",
    "PropertyType",
    "PropertyValueType",
    "ProxyUseSetting",
    "PulldownMethod",
    "PulldownPhase",
    "PulldownSetting",
    "PurgeTarget",
    "RayTracedRendererOptions",
    "RendererOptionsBase",
    "RenderQuality",
    "RenderQueue",
    "RenderQueueItem",
    "ResizeQuality",
    "ResolveType",
    "RQItemStatus",
    "SettingsView",
    "ShadowMapResolution",
    "Shape",
    "ShapeLayer",
    "SolidSource",
    "SoloSwitchesSetting",
    "TargaFormatOptions",
    "TextDocument",
    "TextLayer",
    "ThreeDModelLayer",
    "TiffFormatOptions",
    "TimeDisplayType",
    "TimeSpanSource",
    "ToolType",
    "TrackMatteType",
    "View",
    "Viewer",
    "ViewerType",
    "ViewOptions",
    "XmlFormatOptions",
]


def parse(
    aep_file_path: str | os.PathLike[str],
    *,
    ae_preferences_dir: str | os.PathLike[str] | None = None,
) -> Application:
    """Parse an After Effects (.aep) project file and return an [Application][] instance.

    This is the main entry point for the library. It parses the binary
    RIFX data and returns an [Application][] object whose
    [project][py_aep.models.application.Application.project] attribute
    holds the full project tree.

    Args:
        aep_file_path: Path to the `.aep` file.
        ae_preferences_dir: Optional path to the AE preferences directory
            (e.g. `C:/Users/<user>/AppData/Roaming/Adobe/After Effects/25.6`).
            When provided, render settings and output module templates are
            parsed lazily when needed.

    Example:
        ```python
        import py_aep

        app = py_aep.parse("project.aep")
        project = app.project
        print(app.version)
        ```
    """
    from .binary.chunk import read_aep
    from .parsers.application import parse_app
    from .parsers.project import parse_project

    _DEFERRED_LIST_TYPES = frozenset({"Layr"})

    file_path = os.fspath(aep_file_path)
    prefs_path = Path(ae_preferences_dir) if ae_preferences_dir else None
    with open(file_path, "rb") as f:
        rifx, xmp = read_aep(f, defer_list_types=_DEFERRED_LIST_TYPES)
    project = parse_project(rifx, xmp, file_path, ae_preferences_dir=prefs_path)
    return parse_app(rifx, project)


# Default target version: the AE build the empty-project skeleton was
# captured from (AE 2026).
_DEFAULT_NEW_VERSION = "26.0x67"


def new(
    version: str = _DEFAULT_NEW_VERSION,
    *,
    ae_preferences_dir: str | os.PathLike[str] | None = None,
) -> Application:
    """Creates a new project in After Effects, replicating the File > New > New Project
    menu command.

    Returns an [Application][] wrapping an empty [Project][] (containing
    only the root folder and an empty render queue).

    Args:
        version: The After Effects version to stamp into the file,
            formatted as `"{major}.{minor}x{build}"` (e.g. `"26.0x67"`).
            A file stamped at version N opens in After Effects N and later.
        ae_preferences_dir: Optional path to the AE preferences directory
            (e.g. `C:/Users/<user>/AppData/Roaming/Adobe/After Effects/26.0`),
            required only for adding items to the render queue.

    Example:
        ```python
        import py_aep

        app = py_aep.new()
        comp = app.project.root_folder.add_comp("Comp 1", 1920, 1080, 1.0, 10.0, 30.0)
        app.project.save("new_project.aep")
        ```
    """
    prefs_path = Path(ae_preferences_dir) if ae_preferences_dir else None
    return Application._new(version, ae_preferences_dir=prefs_path)
