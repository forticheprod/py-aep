from __future__ import annotations

from typing import TYPE_CHECKING

from ....enums import OpenExrCompression
from ...descriptors import ChunkField
from ...validators import validate_positive_number
from .base import FormatOptionsBase

if TYPE_CHECKING:
    from ....binary.render_chunks import OpenExrRoptChunk


class OpenExrFormatOptions(FormatOptionsBase):
    """OpenEXR format-specific render options.

    These settings correspond to the OpenEXR Options dialog in After Effects,
    accessible when the output format is set to OpenEXR or OpenEXR Sequence.

    Example:
        ```python
        from py_aep import OpenExrFormatOptions, parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        if isinstance(om.format_options, OpenExrFormatOptions):
            print(om.format_options.compression)
        ```
    """

    def __init__(self, *, _body: OpenExrRoptChunk) -> None:
        self._body = _body

    compression = ChunkField.enum(
        OpenExrCompression,
        "_body",
        "compression",
        allow_out_of_enum_values=True,
    )
    """
    The compression method. Corresponds to the `Compression` dropdown
    in the OpenEXR Options dialog. An out-of-enum stored value reads
    back as a raw `int` (the binary is trusted). Read / Write.
    """

    luminance_chroma = ChunkField.bool(
        "_body",
        "luminance_chroma",
    )
    """
    Whether Luminance/Chroma encoding is enabled. Corresponds to the
    `Luminance/Chroma` checkbox in the OpenEXR Options dialog.
    Not applicable when compression is DWAA or DWAB. Read / Write.
    """

    thirty_two_bit_float = ChunkField.bool(
        "_body",
        "thirty_two_bit_float",
    )
    """
    Whether 32-bit float output is used instead of the default 16-bit
    half float. Corresponds to the `32-bit float (not recommended)`
    checkbox in the OpenEXR Options dialog. Read / Write.
    """

    @property
    def dwa_compression_level(self) -> float | None:
        """
        The DWA compression level. Only meaningful when `compression` is
        `OpenExrCompression.DWAA` or `OpenExrCompression.DWAB`.
        Stored as a little-endian `f4` in the Ropt body. Defaults to
        `45.0`. Read / Write.
        """
        if self.compression in (OpenExrCompression.DWAA, OpenExrCompression.DWAB):
            return self._body.dwa_compression_level
        return None

    @dwa_compression_level.setter
    def dwa_compression_level(self, value: float) -> None:
        validate_positive_number(value)
        self._body.dwa_compression_level = value
