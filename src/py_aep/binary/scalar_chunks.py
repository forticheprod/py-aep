"""Simple scalar and string chunk types.

Each class wraps a single value (int, float, or str) and is registered
for one or more chunk_type strings via the multi-key `@register` decorator.

Integer and float chunks use `fmt_field()` to declare their binary format
inline - the generic `Chunk.read()` / `write()` handles I/O.
String chunks keep a custom `read()` / `write()` (they use encoding, not struct).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from attrs import define, field

from .bin_utils import read_bytes, write_bytes
from .chunk import Chunk
from .fmt_field import fmt_field
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

    contents: str = ""

    @classmethod
    def read(
        cls, fp: IO[bytes], size: int, *, chunk_type: str = "", **kwargs: Any
    ) -> _StringChunkBase:
        raw = read_bytes(fp, size)
        return cls(chunk_type=chunk_type, contents=raw.decode(cls._ENCODING))

    def write(self, fp: IO[bytes]) -> int:
        return write_bytes(fp, self.contents.encode(self._ENCODING))


# ---------------------------------------------------------------------------
# Integer chunks (fmt_field declarative - no read/write override)
# ---------------------------------------------------------------------------


@register(
    "efdc", "acer", "cdrp", "foac", "fiac", "fiop", "ipws",
    "lnrb", "lnrp", "prgb",
)
@define
class U1Chunk(Chunk):
    """Unsigned 1-byte integer chunk."""

    value: int = fmt_field("B")
    _trailing: bytes = field(default=b"", repr=False)


@register("fivc")
@define
class U2Chunk(Chunk):
    """Unsigned 2-byte integer chunk."""

    value: int = fmt_field("H")
    _trailing: bytes = field(default=b"", repr=False)


@register(
    "CapL", "CcCt", "CCId", "CLId", "CprC", "CsCt", "CTyp", "StVS",
    "parn", "fovi", "fivi", "fcid",
)
@define
class U4Chunk(Chunk):
    """Unsigned 4-byte integer chunk."""

    value: int = fmt_field("I")
    _trailing: bytes = field(default=b"", repr=False)


@register("tdli", "tdpi", "tdps")
@define
class S4Chunk(Chunk):
    """Signed 4-byte integer chunk."""

    value: int = fmt_field("i")
    _trailing: bytes = field(default=b"", repr=False)


# ---------------------------------------------------------------------------
# Float chunks
# ---------------------------------------------------------------------------


@register("Smax", "Smin", "adfr")
@define
class F8Chunk(Chunk):
    """8-byte double-precision float chunk."""

    value: float = fmt_field("d", default=0.0)
    _trailing: bytes = field(default=b"", repr=False)


# ---------------------------------------------------------------------------
# String chunks (concrete)
# ---------------------------------------------------------------------------


@register("alas", "cmta", "pjef", "tdmn", "Utf8")
@define
class Utf8Chunk(_StringChunkBase):
    """Variable-length UTF-8 string chunk."""

    _ENCODING = "UTF-8"


@register("fitt")
@define
class AsciiChunk(_StringChunkBase):
    """Variable-length ASCII string chunk."""

    _ENCODING = "ASCII"
