from __future__ import annotations

import typing

from ...descriptors import ChunkField

if typing.TYPE_CHECKING:
    from ....binary.chunk import Chunk


class TiffFormatOptions:
    """TIFF format-specific render options.

    These settings correspond to the TIFF Options dialog in After Effects,
    accessible when the output format is set to TIFF Sequence.

    Example:
        ```python
        from py_aep import TiffFormatOptions, parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        if isinstance(om.format_options, TiffFormatOptions):
            print(om.format_options.lzw_compression)
        ```
    """

    def __init__(self, *, _body: Chunk) -> None:
        self._body = _body

    lzw_compression = ChunkField[bool](
        "_body",
        "lzw_compression",
    )
    """Whether LZW compression is enabled. Read / Write."""

    ibm_pc_byte_order = ChunkField[bool](
        "_body",
        "ibm_pc_byte_order",
    )
    """Whether IBM PC byte order (little-endian) is used. Read / Write."""
