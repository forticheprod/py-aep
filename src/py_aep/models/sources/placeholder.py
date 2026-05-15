from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...binary.footage_chunks import PlaceholderOptiChunk
from .footage import FootageSource

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import OptiChunk, SspcChunk
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

    def _resolve_name(self, raw_name: str) -> str:
        return cast("PlaceholderOptiChunk", self._opti).placeholder_name
