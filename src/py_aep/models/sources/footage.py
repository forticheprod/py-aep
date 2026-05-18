from __future__ import annotations

from typing import TYPE_CHECKING, List, cast

from ...binary.utils import find_by_type, toggle_flag_chunk
from ...enums import (
    AlphaMode,
    FieldSeparationType,
    LinearLightMode,
    PulldownPhase,
)
from ...enums.mappings import map_media_color_space
from ..descriptors import ChunkField
from ..validators import validate_number, validate_sequence

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import SspcChunk
    from ...binary.scalar_chunks import U1Chunk


class FootageSource:
    """
    The `FootageSource` object holds information describing the source of some
    footage. It is used as the `main_source` of a `FootageItem` object, or the
    `proxy_source` of a `CompItem` object or `FootageItem`.

    See: https://ae-scripting.docsforadobe.dev/sources/footagesource/
    """

    alpha_mode = ChunkField.enum(
        AlphaMode,
        "_sspc",
        "alpha_mode_raw",
    )
    """Defines how the alpha information in the footage is interpreted.
    If `has_alpha` is `False`, this attribute has no relevant meaning.
    Read / Write."""

    field_separation_type = ChunkField.enum(
        FieldSeparationType,
        "_sspc",
        "field_separation_type",
    )
    """How the fields are to be separated in non-still footage.
    Read / Write."""

    has_alpha = ChunkField[bool]("_sspc", "has_alpha", read_only=True)
    """When `True`, the footage has an alpha component. In this case, the
    attributes `alpha_mode`, `invert_alpha`, and `premultiplied` have valid
    values. When `False`, those attributes have no relevant meaning for the
    footage. Read-only."""

    high_quality_field_separation = ChunkField[bool](
        "_sspc",
        "high_quality_field_separation",
        transform=lambda v: v % 2 != 0,
        reverse=int,
    )
    """When `True`, After Effects uses special algorithms to determine how to
    perform high-quality field separation. Read / Write."""

    invert_alpha = ChunkField[bool]("_sspc", "invert_alpha")
    """When `True`, an alpha channel in a footage clip or proxy should be
    inverted. This attribute is valid only if an alpha is present. If
    `has_alpha` is `False`, or if `alpha_mode` is
    [AlphaMode.IGNORE][py_aep.enums.AlphaMode], this attribute is
    ignored. Read / Write."""

    loop = ChunkField[int](
        "_sspc",
        "loop",
        validate=validate_number(min=1, max=9999, integer=True),
    )
    """The number of times that the footage is to be played consecutively
    when used in a composition. Read / Write."""

    premul_color = ChunkField[List[float]](
        "_sspc",
        "premul_color",
        validate=validate_sequence(length=3, min=0.0, max=1.0),
    )
    """The color to be premultiplied. This attribute is valid only if
    the `alpha_mode` is
    [AlphaMode.PREMULTIPLIED][py_aep.enums.AlphaMode].
    Read / Write."""

    interpret_as_linear_light = ChunkField.enum(
        LinearLightMode,
        "_linl",
        "value",
        default=LinearLightMode.OFF,
    )
    """The Interpret As Linear Light setting from the Interpret Footage >
    Color Management tab. Read / Write.

    Note:
        Not exposed in ExtendScript."""

    conform_frame_rate = ChunkField[float](
        "_sspc",
        "conform_frame_rate",
        validate=validate_number(min=0.0, max=999.0),
    )
    """A frame rate to use instead of the `native_frame_rate` value. If
    set to 0, the `native_frame_rate` is used instead. Read / Write."""

    display_frame_rate = ChunkField[float](
        "_sspc",
        "display_frame_rate",
        read_only=True,
    )
    """The effective frame rate as displayed and rendered in compositions.
    If `remove_pulldown` is active, the rate is multiplied by 0.8.
    Read-only."""

    remove_pulldown = ChunkField.enum(
        PulldownPhase,
        "_sspc",
        "remove_pulldown",
    )
    """Controls which pulldown phase to remove from the source footage.
    [PulldownPhase.OFF][py_aep.enums.PulldownPhase] by default.
    Read / Write."""

    native_frame_rate = ChunkField[float](
        "_sspc", "native_frame_rate", read_only=True
    )
    """The native frame rate of the footage. Read-only."""

    _width = ChunkField[int]("_sspc", "width", read_only=True)
    _height = ChunkField[int]("_sspc", "height", read_only=True)
    _pixel_aspect = ChunkField[float]("_sspc", "pixel_aspect", read_only=True)
    _footage_missing = ChunkField[bool](
        "_sspc",
        "footage_missing_at_save",
        read_only=True,
    )
    _start_frame = ChunkField[int]("_sspc", "start_frame", read_only=True)
    _end_frame = ChunkField[int]("_sspc", "end_frame", read_only=True)

    @property
    def _has_audio(self) -> bool:
        return self._sspc.audio_sample_rate > 0

    @property
    def _duration(self) -> float:
        """Total duration in seconds (with conform and loop)."""
        sspc = self._sspc
        source_duration = sspc.duration
        conform = sspc.conform_frame_rate
        if conform != 0:
            conform_factor = sspc.native_frame_rate / conform
        else:
            conform_factor = 1.0
        return source_duration * conform_factor * sspc.loop

    @property
    def _frame_duration(self) -> int:
        return int(self._duration * self.display_frame_rate)

    def __init__(
        self,
        *,
        _sspc: SspcChunk,
        _linl: U1Chunk | None = None,
        _clrs: ListChunk | None = None,
    ) -> None:
        self._sspc = _sspc
        self._linl = _linl
        self._clrs = _clrs

    @property
    def preserve_rgb(self) -> bool:
        """When `True`, the footage Preserve RGB setting is enabled.
        From the Interpret Footage > Color Management tab. Read / Write.

        Note:
            Not exposed in ExtendScript."""
        if self._clrs is None:
            return False
        return any(c.chunk_type == "prgb" for c in self._clrs.chunks)

    @preserve_rgb.setter
    def preserve_rgb(self, value: bool) -> None:
        if self._clrs is None:
            raise AttributeError(
                "Cannot set preserve_rgb: no CLRS container. Update the value in After Effects then re-parse the project to modify this footage source."
            )
        toggle_flag_chunk(self._clrs, "prgb", bool(value))

    @property
    def media_color_space(self) -> str:
        """The media color space from the Interpret Footage >
        Color Management tab.

        Returns `"Embedded"` (default), `"Working Color Space"`, or
        the name of the selected ICC profile (e.g. `"Apple RGB"`).
        Read-only.

        Note:
            Not exposed in ExtendScript."""
        if self._clrs is None:
            return "Embedded"
        ipws_chunk = cast(
            "U1Chunk", find_by_type(chunks=self._clrs.chunks, chunk_type="ipws")
        )
        apid_chunk = find_by_type(chunks=self._clrs.chunks, chunk_type="apid")
        return map_media_color_space(
            bool(ipws_chunk.value),
            apid_chunk.data,
        )

    @property
    def is_still(self) -> bool:
        """When `True` the footage is still; When `False`, it has a
        time-based component. Read-only."""
        return self._sspc.duration == 0
