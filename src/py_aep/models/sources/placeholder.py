from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...binary.footage_chunks import PlaceholderOptiChunk, SspcChunk
from ..validators import (
    validate_duration,
    validate_footage_dimension,
    validate_frame_rate,
    validate_name,
)
from .footage import FootageSource

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import OptiChunk
    from ...binary.scalar_chunks import U1Chunk


class PlaceholderSource(FootageSource):
    """
    The `PlaceholderSource` object describes the footage source of a
    placeholder.

    Example:
        ```python
        from py_aep import PlaceholderSource, parse

        app = parse("project.aep")
        footage = app.project.footages[0]
        if isinstance(footage.main_source, PlaceholderSource):
            print(footage.main_source.width)
        ```

    Info:
        `PlaceholderSource` is a subclass of [FootageSource][] object. All
        methods and attributes of [FootageSource][] are available when working
        with `PlaceholderSource`. `PlaceholderSource` does not define any
        additional methods or attributes.

    See: https://ae-scripting.docsforadobe.dev/sources/placeholdersource/
    """

    def __init__(
        self,
        *,
        _sspc: SspcChunk,
        _opti: OptiChunk,
        _linl: U1Chunk | None = None,
        _clrs: ListChunk | None = None,
    ) -> None:
        super().__init__(_sspc=_sspc, _linl=_linl, _clrs=_clrs)
        self._opti = _opti

    @classmethod
    def _new(
        cls,
        name: str,
        width: int,
        height: int,
        frame_rate: float,
        duration: float,
    ) -> PlaceholderSource:
        """Create a new placeholder source with backing chunks.

        Args:
            name: The placeholder name.
            width: Width in pixels (4-30000).
            height: Height in pixels (4-30000).
            frame_rate: Frame rate in fps (1.0-99.0).
            duration: Duration in seconds (> 0, <= 10800).
        """
        validate_name(name)
        validate_footage_dimension(width)
        validate_footage_dimension(height)
        validate_frame_rate(frame_rate)
        validate_duration(duration)
        if duration <= 0.0:
            raise ValueError(f"duration must be > 0, got {duration}")

        sspc = SspcChunk(
            width=width,
            height=height,
            alpha_mode_raw=3,
            footage_missing_at_save=True,
            layer_index=0xFFFFFFFE,
        )
        sspc.native_frame_rate = frame_rate
        sspc.duration = duration

        opti = PlaceholderOptiChunk(placeholder_name=name)

        return cls(_sspc=sspc, _opti=opti)

    def _resolve_name(self, raw_name: str) -> str:
        return cast("PlaceholderOptiChunk", self._opti).placeholder_name
