"""Low-level binary I/O primitives for AEP chunk parsing.

All functions default to big-endian because AEP files are always RIFX.
The `endian` parameter on `read_fmt` / `write_fmt` exists for typed chunks
that have little-endian fields.
"""

from __future__ import annotations

import struct
from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import IO, Any

_HEADER_STRUCT = struct.Struct(">4sI")
_STRUCT_CACHE: dict[str, struct.Struct] = {}

_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1

#: Seconds between the Mac epoch (1904-01-01) AE stamps file and item times
#: with and the Unix epoch.
MAC_EPOCH_OFFSET = 2082844800


def to_dividend_divisor(value: float) -> tuple[int, int]:
    """Split `value` into the `(dividend, divisor)` integers AE stores for its
    time / ratio fields.

    AEP encodes many quantities - layer and comp times, durations, pixel
    aspect, render time spans - as a signed-32-bit dividend over an
    unsigned-32-bit divisor. The denominator is capped from the value's
    magnitude so the dividend always fits int32: precision degrades gracefully
    for very large values rather than overflowing `struct.pack` and silently
    truncating the saved file.

    Raises:
        ValueError: If the value's whole part alone cannot fit int32 (about 68
            years for a time field) - which also rejects `nan` / `inf`.
    """
    if not _INT32_MIN <= value <= _INT32_MAX:
        raise ValueError(
            f"ratio value {value} is out of range (must be within +/-{_INT32_MAX})"
        )
    # |dividend| ~= |value| * denominator, so capping the denominator at
    # INT32_MAX // (|value| + 2) keeps the dividend strictly inside int32.
    max_denominator = max(1, _INT32_MAX // (int(abs(value)) + 2))
    frac = Fraction(value).limit_denominator(min(1_000_000, max_denominator))
    return frac.numerator, frac.denominator


def to_float32_ratio(value: float) -> tuple[int, int]:
    """Split `value` into the `(dividend, divisor)` AE stores for a comp's
    display start time or a layer's stretch: the value rounded to float32,
    as an exact ratio, with the divisor held to the signed 32-bit range.

    Measured on AE 2026: 0.51 -> 2139095/4194304, 0.5 -> 1/2, and
    8.33e-7 (whose exact float32 ratio needs a 2^44 divisor) ->
    330/396000001.
    """
    frac = Fraction(to_f4(value)).limit_denominator(_INT32_MAX)
    return frac.numerator, frac.denominator


def to_fixed_16_16(value: float) -> tuple[int, int]:
    """Split `value` into the `(integer, fractional)` parts of a 16.16 fixed
    point number (fraction in 1/65536 units), as AE stores frame rates.

    The whole value is rounded before the split: rounding the fraction alone
    turns 23.99999999 into 23 + 65536/65536, which overflows a u2 fraction.
    """
    return divmod(round(value * 65536), 65536)


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
        raise OSError(f"Short read: expected {s.size} bytes, got {len(data)}")
    return s.unpack(data)


def write_fmt(fp: IO[bytes], fmt: str, *args: Any, endian: str = ">") -> int:
    """Pack and write binary data to `fp`.

    Returns bytes written.
    """
    data = _get_struct(endian + fmt).pack(*args)
    fp.write(data)
    return len(data)


#: The largest finite IEEE-754 single (float32).
FLOAT32_MAX = 3.4028234663852886e38


def to_f4(value: float) -> float:
    """Round a Python float (f8) to float32 (f4) precision."""
    return float(struct.unpack("<f", struct.pack("<f", value))[0])


def read_bytes(fp: IO[bytes], size: int) -> bytes:
    """Read exactly `size` bytes from `fp`.

    Raises:
        IOError: If fewer bytes are available than requested.
    """
    data = fp.read(size)
    if len(data) < size:
        raise OSError(f"Short read: expected {size} bytes, got {len(data)}")
    return data


def write_bytes(fp: IO[bytes], data: bytes) -> int:
    """Write raw bytes to `fp`. Returns bytes written."""
    fp.write(data)
    return len(data)


def truncate_utf8(value: str, max_bytes: int) -> bytes:
    """Encode `value` to UTF-8, truncated to at most `max_bytes` bytes.

    Slicing UTF-8 bytes can split a multibyte character; decoding the slice
    with `errors="ignore"` drops any trailing partial sequence, so the result
    is always valid UTF-8 and never exceeds `max_bytes`. Used for fixed-width
    AEP name fields.
    """
    return value.encode("utf-8")[:max_bytes].decode("utf-8", "ignore").encode("utf-8")


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
