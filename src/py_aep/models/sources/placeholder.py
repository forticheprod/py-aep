from __future__ import annotations

import typing

from .footage import FootageSource

if typing.TYPE_CHECKING:
    from ...binary.chunk import Chunk, ListChunk


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
        _sspc: Chunk,
        _linl: Chunk | None = None,
        _clrs: ListChunk | None = None,
    ) -> None:
        super().__init__(_sspc=_sspc, _linl=_linl, _clrs=_clrs)
