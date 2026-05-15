"""Low-level binary I/O primitives for AEP chunk parsing.

All functions default to big-endian because AEP files are always RIFX.
The `endian` parameter on `read_fmt` / `write_fmt` exists for typed chunks
that have little-endian fields.
"""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import IO, Any

_HEADER_STRUCT = struct.Struct(">4sI")
_STRUCT_CACHE: dict[str, struct.Struct] = {}


def _get_struct(full_fmt: str) -> struct.Struct:
    """Return a cached `struct.Struct` for `full_fmt`."""
    s = _STRUCT_CACHE.get(full_fmt)
    if s is None:
        s = _STRUCT_CACHE[full_fmt] = struct.Struct(full_fmt)
    return s


def read_fmt(fmt: str, fp: IO[bytes], endian: str = ">") -> tuple[Any, ...]:
    """Read and unpack binary data from `fp`.

    Prepends `endian` to `fmt`, reads the required number of bytes, and
    unpacks them.

    Raises:
        IOError: If fewer bytes are available than the format requires.
    """
    s = _get_struct(endian + fmt)
    data = fp.read(s.size)
    if len(data) < s.size:
        raise OSError(
            f"Short read: expected {s.size} bytes, got {len(data)}"
        )
    return s.unpack(data)


def write_fmt(fp: IO[bytes], fmt: str, *args: Any, endian: str = ">") -> int:
    """Pack and write binary data to `fp`.

    Returns bytes written.
    """
    data = _get_struct(endian + fmt).pack(*args)
    fp.write(data)
    return len(data)


def read_bytes(fp: IO[bytes], size: int) -> bytes:
    """Read exactly `size` bytes from `fp`.

    Raises:
        IOError: If fewer bytes are available than requested.
    """
    data = fp.read(size)
    if len(data) < size:
        raise OSError(
            f"Short read: expected {size} bytes, got {len(data)}"
        )
    return data


def write_bytes(fp: IO[bytes], data: bytes) -> int:
    """Write raw bytes to `fp`. Returns bytes written."""
    fp.write(data)
    return len(data)


def is_readable(fp: IO[bytes], size: int = 1) -> bool:
    """Check if `size` bytes can be read without consuming them."""
    pos = fp.tell()
    data = fp.read(size)
    fp.seek(pos)
    return len(data) >= size


def write_pad(fp: IO[bytes], size: int) -> int:
    """Write a pad byte if `size` is odd. Returns bytes written (0 or 1)."""
    if size % 2 != 0:
        fp.write(b"\x00")
        return 1
    return 0


def read_pad(fp: IO[bytes], size: int) -> None:
    """Consume a pad byte if `size` is odd."""
    if size % 2 != 0:
        fp.read(1)
