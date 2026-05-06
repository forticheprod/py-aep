from __future__ import annotations

from typing import TYPE_CHECKING

from ...descriptors import ChunkField
from ...validators import validate_one_of

if TYPE_CHECKING:
    from ....binary.render_chunks import RoptChunk


class TargaFormatOptions:
    """Targa (TGA) format-specific render options.

    These settings correspond to the Targa Options dialog in After Effects,
    accessible when the output format is set to Targa Sequence.

    Example:
        ```python
        from py_aep import TargaFormatOptions, parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        if isinstance(om.format_options, TargaFormatOptions):
            print(om.format_options.bits_per_pixel)
        ```
    """

    def __init__(self, *, _body: RoptChunk) -> None:
        self._body = _body

    bits_per_pixel = ChunkField[int](
        "_body",
        "bits_per_pixel",
        validate=validate_one_of([24, 32]),
    )
    """Color depth in bits per pixel (24 or 32). Read / Write."""

    rle_compression = ChunkField[bool](
        "_body",
        "rle_compression",
    )
    """Whether RLE compression is enabled. Read / Write."""
