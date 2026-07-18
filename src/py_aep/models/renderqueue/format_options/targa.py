from __future__ import annotations

from typing import TYPE_CHECKING

from ...descriptors import ChunkField
from ...validators import validate_one_of
from .base import FormatOptionsBase

if TYPE_CHECKING:
    from ....binary.render_chunks import RoptChunk


class TargaFormatOptions(FormatOptionsBase):
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
    """Color depth in bits per pixel (24 or 32). Read / Write.

    Not coupled to the module's `Channels` setting in the binary: AE
    only rewrites this byte when the Targa Options dialog is visited,
    so AE-saved files hold RGB with 32 bpp and RGB+Alpha with 24 bpp
    (stale, like Cineon's FIDO `bit_depth`). The output module's
    `Depth` setting is the authoritative alpha/depth choice.
    """

    rle_compression = ChunkField.bool(
        "_body",
        "rle_compression",
    )
    """Whether RLE compression is enabled. Read / Write."""
