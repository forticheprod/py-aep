"""Parsers for format-specific render options (Ropt chunk)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union, cast

from ..binary.render_chunks import OpenExrRoptChunk, PngRoptChunk, RoptChunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import ChunkNotFoundError, find_by_type
from ..models.renderqueue.format_options import (
    CineonFormatOptions,
    JpegFormatOptions,
    OpenExrFormatOptions,
    PngFormatOptions,
    TargaFormatOptions,
    TiffFormatOptions,
    XmlFormatOptions,
)

if TYPE_CHECKING:
    from ..binary.chunk import Chunk

FormatOptions = Union[
    CineonFormatOptions,
    JpegFormatOptions,
    OpenExrFormatOptions,
    PngFormatOptions,
    TargaFormatOptions,
    TiffFormatOptions,
    XmlFormatOptions,
]

# Format codes that use XML-based PremiereData options
_XML_FORMAT_CODES = {".AVI", "H264", "Mp3 ", "MooV", "wao_"}


def parse_format_options(
    chunks: list[Chunk],
) -> FormatOptions | None:
    """Parse format-specific options from the Ropt chunk, if present.

    Args:
        chunks: List of chunks belonging to an output module.

    Returns:
        A format-specific options object, or `None` when the Ropt chunk
        is absent or the format is not yet supported.
    """
    try:
        ropt_chunk = cast("RoptChunk", find_by_type(chunks=chunks, chunk_type="Ropt"))
    except ChunkNotFoundError:
        return None

    format_code = ropt_chunk.format_code

    if format_code == "sDPX":
        return CineonFormatOptions(_body=ropt_chunk)
    if format_code == "JPEG":
        return JpegFormatOptions(_body=ropt_chunk)
    if format_code == "TPIC":
        return TargaFormatOptions(_body=ropt_chunk)
    if format_code == "TIF ":
        return TiffFormatOptions(_body=ropt_chunk)
    if format_code == "oEXR":
        return OpenExrFormatOptions(_body=cast("OpenExrRoptChunk", ropt_chunk))
    if format_code == "png!":
        try:
            hdr10_utf8 = cast(
                "Utf8Chunk", find_by_type(chunks=chunks, chunk_type="Utf8")
            )
        except ChunkNotFoundError:
            hdr10_utf8 = None
        return PngFormatOptions(
            _body=cast("PngRoptChunk", ropt_chunk), _hdr10_utf8=hdr10_utf8
        )
    if format_code in _XML_FORMAT_CODES:
        return XmlFormatOptions(_body=ropt_chunk)

    return None
