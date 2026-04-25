"""Low-level binary I/O primitives for AEP chunk parsing.

All functions default to big-endian because AEP files are always RIFX.
The `endian` parameter on `read_fmt` / `write_fmt` exists for Phase 2
typed chunks that have little-endian fields.
"""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import IO, Any

_HEADER_STRUCT = struct.Struct(">4sI")


def read_fmt(fmt: str, fp: IO[bytes], endian: str = ">") -> tuple[Any, ...]:
    """Read and unpack binary data from `fp`.

    Prepends `endian` to `fmt`, reads the required number of bytes, and
    unpacks them.

    Raises:
        IOError: If fewer bytes are available than the format requires.
    """
    full_fmt = endian + fmt
    size = struct.calcsize(full_fmt)
    data = fp.read(size)
    if len(data) < size:
        raise OSError(
            f"Short read: expected {size} bytes, got {len(data)}"
        )
    return struct.unpack(full_fmt, data)


def write_fmt(fp: IO[bytes], fmt: str, *args: Any, endian: str = ">") -> int:
    """Pack and write binary data to `fp`.

    Returns bytes written.
    """
    full_fmt = endian + fmt
    data = struct.pack(full_fmt, *args)
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
