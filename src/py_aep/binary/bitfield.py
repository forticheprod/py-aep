"""BitField descriptor for single-bit flags on raw byte fields.

Usage::

    @define
    class MyChunk(Chunk):
        _flags: int = fmt_field("B", repr=False)

        my_flag = BitField("_flags", 3)  # bit 3 (no annotation)
"""
from __future__ import annotations


class BitField:
    """Descriptor mapping a single bit in a raw-byte attrs field to a bool.

    The descriptor has no type annotation on the class body, so attrs
    ignores it (it stays as a class-level data descriptor, not a slot).
    Unknown bits in the raw byte are preserved implicitly.
    """

    def __init__(self, byte_field: str, bit: int) -> None:
        self.byte_field = byte_field
        self.mask = 1 << bit

    def __get__(self, obj: object, objtype: type | None = None) -> bool:
        return bool(getattr(obj, self.byte_field) & self.mask)

    def __set__(self, obj: object, value: bool) -> None:
        raw = getattr(obj, self.byte_field)
        if value:
            setattr(obj, self.byte_field, raw | self.mask)
        else:
            setattr(obj, self.byte_field, raw & ~self.mask)
