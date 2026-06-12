"""Serialize Python objects back to COS (Carousel Object Syntax) binary.

This is the inverse of `CosParser.parse`: it takes a nested Python
structure (dicts, lists, strings, numbers, bools, `None`,
`IndirectObject`, `IndirectReference`, `Stream`) and emits COS-format
bytes suitable for writing back into a btdk chunk's `binary_data`.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from .cos import CosName, IndirectObject, IndirectReference, Stream

if TYPE_CHECKING:
    from typing import Any


def serialize(data: Any) -> bytes:
    """Serialize a parsed COS value tree back to binary.

    Args:
        data: The Python object tree to serialize. May be a dict, list,
            str, int, float, bool, `None`, `bytes`,
            `IndirectObject`, `IndirectReference`, or `Stream`.

    Returns:
        The COS binary representation.
    """
    buf = io.BytesIO()
    # AE's btdk blob begins with a leading space before the first token.
    buf.write(b" ")
    _write_value(buf, data, top_level=True)
    return buf.getvalue()


def _space(buf: io.BytesIO) -> None:
    """Write a space separator unless the buffer already ends with whitespace."""
    pos = buf.tell()
    if pos == 0:
        return
    buf.seek(pos - 1)
    last = buf.read(1)
    if last not in b" \t\n\r":
        buf.write(b" ")


def _write_value(buf: io.BytesIO, value: Any, *, top_level: bool = False) -> None:
    """Dispatch `value` to the appropriate serialization handler."""
    if isinstance(value, dict):
        if top_level:
            _write_dict_content(buf, value)
        else:
            _space(buf)
            _write_dict(buf, value)
    elif isinstance(value, list):
        if top_level:
            _write_array_content(buf, value)
        else:
            _space(buf)
            _write_array(buf, value)
    elif isinstance(value, bool):
        # Must come before int check since bool is a subclass of int
        _space(buf)
        buf.write(b"true" if value else b"false")
    elif isinstance(value, int):
        _space(buf)
        buf.write(str(value).encode("ascii"))
    elif isinstance(value, float):
        _space(buf)
        buf.write(_format_float(value))
    elif isinstance(value, CosName):
        _space(buf)
        _write_identifier(buf, value.value)
    elif isinstance(value, str):
        _space(buf)
        _write_string(buf, value)
    elif isinstance(value, bytes):
        _space(buf)
        _write_hex_string(buf, value)
    elif value is None:
        _space(buf)
        buf.write(b"null")
    elif isinstance(value, IndirectObject):
        _space(buf)
        _write_indirect_object(buf, value)
    elif isinstance(value, IndirectReference):
        _space(buf)
        _write_indirect_reference(buf, value)
    elif isinstance(value, Stream):
        _space(buf)
        _write_stream(buf, value)
    else:
        raise TypeError(f"Cannot serialize COS value of type {type(value).__name__}")


def _format_float(value: float) -> bytes:
    """Format a float matching After Effects' COS conventions.

    Whole-valued floats keep a trailing `.0` (AE writes `0.0` / `9.0`,
    not `0` / `9`), which distinguishes them from COS integers and keeps
    the serialized blob byte-faithful.
    """
    text = f"{value:.10g}"
    if not any(c in text for c in ".eEni"):  # no '.', exponent, 'nan'/'inf'
        text += ".0"
    # AE omits the leading zero for |v| < 1 (".5", "-.5") but keeps "0.0".
    if text.startswith("0.") and text != "0.0":
        text = text[1:]
    elif text.startswith("-0.") and text != "-0.0":
        text = "-" + text[2:]
    return text.encode("ascii")


def _write_dict(buf: io.BytesIO, d: dict[str, Any]) -> None:
    """Write a COS dictionary: `<< /key value /key value >>`."""
    buf.write(b"<<")
    _write_dict_content(buf, d)
    _space(buf)
    buf.write(b">>")


def _write_dict_content(buf: io.BytesIO, d: dict[str, Any]) -> None:
    """Write dict key/value pairs without the `<<`/`>>` delimiters."""
    for key, val in d.items():
        _space(buf)
        _write_identifier(buf, key)
        _write_value(buf, val)


def _write_array(buf: io.BytesIO, lst: list[Any]) -> None:
    """Write a COS array: `[ val val val ]`."""
    buf.write(b"[")
    _write_array_content(buf, lst)
    _space(buf)
    buf.write(b"]")


def _write_array_content(buf: io.BytesIO, lst: list[Any]) -> None:
    """Write array elements without `[`/`]` delimiters."""
    for item in lst:
        _write_value(buf, item)


def _write_identifier(buf: io.BytesIO, name: str) -> None:
    """Write a COS identifier (name object): `/foo`."""
    buf.write(b"/")
    escaped = ""
    for ch in name:
        code = ord(ch)
        if code < 0x21 or code > 0x7E or ch in "()[]<>{}/%#":
            escaped += f"#{code:02x}"
        else:
            escaped += ch
    buf.write(escaped.encode("ascii"))


def _write_string(buf: io.BytesIO, s: str) -> None:
    """Write a COS string literal: `(escaped content)`.

    Strings are encoded as UTF-16 BE with a BOM prefix (AE's convention
    for text data) unless the value is a `CosString` that was parsed as
    raw ASCII / UTF-8 (e.g. bit-flag strings), in which case the original
    single-byte encoding is reproduced for byte fidelity.
    """
    if getattr(s, "cos_utf16", True):
        raw = b"\xfe\xff" + s.encode("utf-16-be")
    else:
        raw = s.encode("utf-8")
    buf.write(b"(")
    buf.write(_escape_string(raw))
    buf.write(b")")


def _escape_string(raw: bytes) -> bytes:
    """Escape bytes for a COS string literal.

    Only the characters that affect COS string parsing are escaped:
    the delimiters `(` / `)` and the escape character `\\`. After
    Effects writes control bytes (newline, CR, backspace, form-feed)
    raw inside string literals, so they are left unescaped to keep the
    serialized blob byte-faithful.
    """
    out = bytearray()
    for byte in raw:
        if byte == ord(b"("):
            out.extend(b"\\(")
        elif byte == ord(b")"):
            out.extend(b"\\)")
        elif byte == ord(b"\\"):
            out.extend(b"\\\\")
        else:
            out.append(byte)
    return bytes(out)


def _write_hex_string(buf: io.BytesIO, data: bytes) -> None:
    """Write a COS hex string: `<hexdata>`."""
    buf.write(b"<")
    buf.write(data.hex().encode("ascii"))
    buf.write(b">")


def _write_indirect_object(buf: io.BytesIO, obj: IndirectObject) -> None:
    """Write `N G obj <data> endobj`."""
    buf.write(str(obj.object_number).encode("ascii"))
    buf.write(b" ")
    buf.write(str(obj.generation_number).encode("ascii"))
    buf.write(b" obj")
    _write_value(buf, obj.data)
    buf.write(b" endobj")


def _write_indirect_reference(buf: io.BytesIO, ref: IndirectReference) -> None:
    """Write `N G R`."""
    buf.write(str(ref.object_number).encode("ascii"))
    buf.write(b" ")
    buf.write(str(ref.generation_number).encode("ascii"))
    buf.write(b" R")


def _write_stream(buf: io.BytesIO, stream: Stream) -> None:
    """Write `<< dict >> stream\\n<bytes>endstream`."""
    _write_dict(buf, stream.dictionary)
    buf.write(b"stream\n")
    buf.write(stream.data)
    buf.write(b"endstream")
