"""Simple scalar and string chunk types.

Each class wraps a single value (int, float, or str) and is registered
for one or more chunk_type strings via the multi-key `@register` decorator.

Integer and float chunks use `fmt_field()` to declare their binary format
inline - the generic `Chunk.read()` / `write()` handles I/O.
String chunks keep a custom `read()` / `write()` (they use encoding, not struct).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from attrs import define

from .bin_utils import read_bytes, write_bytes
from .chunk import Chunk
from .fmt_field import f8_field, s4_field, u1_field, u2_field, u4_field
from .registry import register

if TYPE_CHECKING:
    from typing import IO, Any


# ---------------------------------------------------------------------------
# String base (encoding-based, custom read/write)
# ---------------------------------------------------------------------------


@define
class _StringChunkBase(Chunk):
    """Base for variable-length string chunks."""

    _ENCODING = ""

    value: str = ""

    @classmethod
    def read(
        cls, fp: IO[bytes], size: int, *, chunk_type: str = "", **kwargs: Any
    ) -> _StringChunkBase:
        raw = read_bytes(fp, size)
        return cls(chunk_type=chunk_type, value=raw.decode(cls._ENCODING))

    def write(self, fp: IO[bytes]) -> int:
        return write_bytes(fp, self.value.encode(self._ENCODING))


# ---------------------------------------------------------------------------
# Integer chunks (fmt_field declarative - no read/write override)
# ---------------------------------------------------------------------------


@register(
    "efdc",
    "acer",
    "cdrp",
    "foac",
    "fiac",
    "fiop",
    "lnrb",
    "lnrp",
    "qtlg",
    "pcms",
    "PwCs",
    "pdvc",
)
@define
class U1Chunk(Chunk):
    """Unsigned 1-byte integer chunk."""

    value: int = u1_field()


@register("fivc", "fipc", "oacc")
@define
class U2Chunk(Chunk):
    """Unsigned 2-byte integer chunk."""

    value: int = u2_field()


@register(
    "CapL",
    "CcCt",
    "CCId",
    "CLId",
    "CprC",
    "CSMd",
    "CSMe",
    "CSMh",
    "CSMs",
    "CSMt",
    "CSMw",
    "CTyp",
    "StVS",
    "blsi",
    "blsv",
    "parn",
    "fovi",
    "fivi",
    "fcid",
    "fvdv",
    "ftts",
    "fifl",
    "mrid",
    "sfid",
)
@define
class U4Chunk(Chunk):
    """Unsigned 4-byte integer chunk."""

    value: int = u4_field()


@register("tdli", "tdpi", "tdps")
@define
class S4Chunk(Chunk):
    """Signed 4-byte integer chunk."""

    value: int = s4_field()


# ---------------------------------------------------------------------------
# Float chunks
# ---------------------------------------------------------------------------


@register("Smax", "Smin", "adfr", "ppSn")
@define
class F8Chunk(Chunk):
    """8-byte double-precision float chunk."""

    value: float = f8_field(default=0.0)


# ---------------------------------------------------------------------------
# String chunks (concrete)
# ---------------------------------------------------------------------------


@register("alas", "pjef", "Utf8")
@define
class Utf8Chunk(_StringChunkBase):
    """Variable-length UTF-8 string chunk."""

    chunk_type: str = "Utf8"
    _ENCODING = "UTF-8"


@register("fitt")
@define
class AsciiChunk(_StringChunkBase):
    """Variable-length ASCII string chunk."""

    _ENCODING = "ASCII"
