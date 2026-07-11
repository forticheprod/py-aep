from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, BinaryIO, NoReturn

"""
source: https://gitlab.com/mattbas/python-lottie/-/blob/master/lib/lottie/parsers/aep/cos.py
documentation: https://github.com/hunger-zh/lottie-docs/blob/main/docs/aep.md#list-btdk
"""


def cos_get(data: Any, *keys: str | int) -> Any:
    """Safely traverse parsed COS data by successive keys.

    Each key is tried as a dict string key first and then as a list
    index. Returns `None` when any step along the path is missing.

    Example::

        cos_get(data, "1", "1", 0, "0", "0")  # -> text string
    """
    cur: Any = data
    for key in keys:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(str(key))
        elif isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except (IndexError, ValueError, TypeError):
                return None
        else:
            return None
    return cur


def run_spans(
    doc: dict[str, Any], doc_key: str, style_key: str | None
) -> list[tuple[int, int, dict[str, Any]]]:
    """Decode a text document's COS run array into `(start, end, payload)`.

    Run arrays (`doc["0"]["5"/"6"/"8"]["0"]`) store `{"0": payload,
    "1": count}` entries whose counts are UTF-16 units over the raw
    text. `style_key` picks the style sub-dict for paragraph ("5") and
    character ("6") runs; kerning runs ("8") use their payload directly.
    Runs with a missing or negative count are skipped. Shared by the
    range models (models/text/ranges.py) and the composed-line resolver
    (resolvers/text_composition.py).
    """
    runs = cos_get(doc, "0", doc_key, "0")
    spans: list[tuple[int, int, dict[str, Any]]] = []
    if not isinstance(runs, list):
        return spans
    pos = 0
    for run in runs:
        length = run.get("1") if isinstance(run, dict) else None
        if not isinstance(length, int) or length < 0:
            continue
        if style_key is None:
            payload = cos_get(run, "0")
        else:
            payload = cos_get(run, "0", "0", style_key)
        spans.append((pos, pos + length, payload if isinstance(payload, dict) else {}))
        pos += length
    return spans


class TokenType(Enum):
    Identifier = auto()  # /foo
    Number = auto()  # 123
    String = auto()  # (foo)
    HexString = auto()  # <f000>
    Boolean = auto()  # true
    ObjectStart = auto()  # <<
    ObjectEnd = auto()  # >>
    ArrayStart = auto()  # [
    ArrayEnd = auto()  # ]
    Null = auto()  # null
    Eof = auto()  # end of file
    IndirectObjectStart = auto()  # obj
    IndirectObjectEnd = auto()  # endobj
    IndirectReference = auto()  # R
    Stream = auto()  # stream...endstream


@dataclass
class Token:
    type: TokenType
    value: Any = None


@dataclass
class IndirectObject:
    object_number: int
    generation_number: int
    data: Any


@dataclass
class IndirectReference:
    object_number: int
    generation_number: int


class CosString(str):
    """A COS string literal that remembers its on-disk encoding.

    After Effects writes some string literals as UTF-16 BE (with a BOM,
    e.g. visible text) and others as raw ASCII / UTF-8 (e.g. bit-flag
    strings like `00001000...`). The encoding cannot be inferred from
    the decoded content, so it is preserved here for byte-faithful
    re-serialization. Behaves exactly like `str` otherwise. New strings
    created without this wrapper default to UTF-16 on write.
    """

    cos_utf16: bool

    def __new__(cls, value: str, *, utf16: bool = True) -> CosString:
        obj = super().__new__(cls, value)
        obj.cos_utf16 = utf16
        return obj


@dataclass
class CosName:
    """A COS name object used as a value (e.g. `/CoolTypeFont`).

    Distinct from a dict key identifier: when serialized, a CosName
    writes `/name` while a plain `str` writes `(string)`.
    """

    value: str

    def __str__(self) -> str:
        return self.value


@dataclass
class Stream:
    dictionary: dict[str, Any]
    data: bytes


class CosParser:
    def __init__(self, file: BinaryIO, max_pos: int | None = None) -> None:
        self.file = file
        self.max_pos = max_pos
        self.lookahead: Token = Token(TokenType.Eof)  # Will be set by lex()

    def parse(self) -> dict[str, Any] | list[Any] | Any:
        self.lex()
        if self.lookahead.type == TokenType.Identifier:
            return self.parse_dict_content()

        val = self.parse_value()
        if self.lookahead.type == TokenType.Eof:
            return val

        return [val] + self.parse_array_content()

    def parse_value(self) -> Any:
        if self.lookahead.type == TokenType.Identifier:
            val = CosName(self.lookahead.value)
            self.lex()
            return val

        if (
            self.lookahead.type == TokenType.String
            or self.lookahead.type == TokenType.HexString
            or self.lookahead.type == TokenType.Null
            or self.lookahead.type == TokenType.Boolean
            or self.lookahead.type == TokenType.Stream
        ):
            val = self.lookahead.value
            self.lex()
            return val

        if self.lookahead.type == TokenType.Number:
            val = self.lookahead.value
            self.lex()
            if self.lookahead.type == TokenType.Number:
                gen = self.lookahead.value
                state = self.save_state()
                self.lex()
                if self.lookahead.type == TokenType.IndirectObjectStart:
                    self.lex()
                    data = self.parse_value()
                    self.expect(TokenType.IndirectObjectEnd)
                    self.lex()
                    return IndirectObject(val, gen, data)
                elif self.lookahead.type == TokenType.IndirectReference:
                    self.lex()
                    return IndirectReference(val, gen)
                else:
                    self.restore_state(state)
            return val

        if self.lookahead.type == TokenType.ObjectStart:
            self.lex()
            val = self.parse_dict_content()
            self.expect(TokenType.ObjectEnd)
            self.lex()
            if self.lookahead.type == TokenType.Stream:
                val = Stream(val, self.lookahead.value)
                self.lex()
            return val

        if self.lookahead.type == TokenType.ArrayStart:
            self.lex()
            val = self.parse_array_content()
            self.expect(TokenType.ArrayEnd)
            self.lex()
            return val

        raise SyntaxError(f"Expected COS value, got {self.lookahead}")

    def save_state(self) -> tuple[int | None, int, Token]:
        return (self.max_pos, self.file.tell(), self.lookahead)

    def restore_state(self, state: tuple[int | None, int, Token]) -> None:
        self.max_pos, pos, self.lookahead = state
        self.file.seek(pos)

    def parse_dict_content(self) -> dict[str, Any]:
        value = {}
        while True:
            if (
                self.lookahead.type == TokenType.Eof
                or self.lookahead.type == TokenType.ObjectEnd
            ):
                break

            self.expect(TokenType.Identifier)
            key = self.lookahead.value
            self.lex()
            val = self.parse_value()
            value[key] = val

        return value

    def parse_array_content(self) -> list[Any]:
        value: list[Any] = []
        while True:
            if (
                self.lookahead.type == TokenType.Eof
                or self.lookahead.type == TokenType.ArrayEnd
            ):
                break
            value.append(self.parse_value())
        return value

    def expect(self, token_type: TokenType) -> None:
        if self.lookahead.type != token_type:
            raise SyntaxError(f"Expected {token_type}, got {self.lookahead}")

    def lex(self) -> None:
        self.lookahead = self.lex_token()

    def lex_token(self) -> Token:
        char: bytes | None = None
        while True:
            char = self.get_char()
            if char is None:
                return Token(TokenType.Eof)
            elif char == b"%":
                self.lex_comment()
            elif not char.isspace():
                break

        # At this point char is guaranteed to be bytes (not None)
        assert char is not None

        # <<
        if char == b"<":
            next_char = self.get_char()
            if next_char == b"<":
                return Token(TokenType.ObjectStart)
            elif next_char is None:
                self.raise_lex(b"<")
            elif self.is_hex(next_char):
                return self.lex_hex_string(next_char)
            else:
                self.raise_lex(b"<" + next_char)

        # >>
        if char == b">":
            self.expect_char(b">", char)
            return Token(TokenType.ObjectEnd)

        # [
        if char == b"[":
            return Token(TokenType.ArrayStart)

        # ]
        if char == b"]":
            return Token(TokenType.ArrayEnd)

        # /foo
        if char == b"/":
            return self.lex_identifier()

        # (foo)
        if char == b"(":
            return self.lex_string()

        # Keyword
        if char.isalpha():
            return self.lex_keyword(char)

        # Number
        if char.isdigit() or char in b".+-":
            return self.lex_number(char)

        self.raise_lex(char)

    def expect_char(self, exp: bytes, head: bytes) -> None:
        char = self.get_char()
        if char is None or char != exp:
            self.raise_lex(head + (char or b""), head + exp)

    def raise_lex(self, token: bytes, exp: bytes | None = None) -> NoReturn:
        msg = f"Unknown COS token {token!r}"
        if exp is not None:
            msg += f", expected {exp!r}"
        raise SyntaxError(msg)

    def get_char(self) -> bytes | None:
        if self.max_pos is None:
            return self.file.read(1)

        if self.max_pos <= 0:
            return None

        char = self.file.read(1)
        self.max_pos -= 1
        return char

    def unget(self) -> None:
        self.file.seek(-1, io.SEEK_CUR)
        if self.max_pos is not None:
            self.max_pos += 1

    # Skip until newline
    def lex_comment(self) -> None:
        while True:
            char = self.get_char()
            if char == b"\n":
                break
            elif char is None:
                break

    def lex_number(self, char: bytes) -> Token:
        if char == b".":
            return self.lex_num_fract(self.get_char(), char)
        elif char == b"+" or char == b"-":
            return self.lex_num_int(self.get_char(), char)
        else:
            return self.lex_num_int(char, b"")

    def lex_num_int(self, char: bytes | None, head: bytes) -> Token:
        while True:
            if char is None:
                break
            elif char == b".":
                return self.lex_num_fract(self.get_char(), head + char)
            elif char.isdigit():
                head += char
                char = self.get_char()
            else:
                self.unget()
                break
        return Token(TokenType.Number, int(head))

    def lex_num_fract(self, char: bytes | None, head: bytes) -> Token:
        while True:
            if char is None:
                break
            elif char.isdigit():
                head += char
                char = self.get_char()
            else:
                self.unget()
                break
        return Token(TokenType.Number, float(head))

    def lex_keyword(self, char: bytes) -> Token:
        kw = char
        while True:
            next_char = self.get_char()
            if next_char is None:
                break
            elif next_char.isalpha():
                kw += next_char
            else:
                self.unget()
                break

        if kw == b"true":
            return Token(TokenType.Boolean, True)
        elif kw == b"false":
            return Token(TokenType.Boolean, False)
        elif kw == b"null":
            return Token(TokenType.Null, None)
        elif kw == b"obj":
            return Token(TokenType.IndirectObjectStart)
        elif kw == b"endobj":
            return Token(TokenType.IndirectObjectEnd)
        elif kw == b"R":
            return Token(TokenType.IndirectReference)
        elif kw == b"stream":
            return self.lex_stream()
        elif kw == b"xref":
            return Token(TokenType.Eof)
        else:
            raise SyntaxError(f"Unknown keyword {kw!r}")

    def lex_stream(self) -> Token:
        char = self.get_char()
        if char == b"\r":
            if self.get_char() != b"\n":
                raise SyntaxError("Invalid newline")
        elif char != b"\n":
            raise SyntaxError("Expected newline after `stream`")

        stream = b""
        marker = b"endstream"
        while True:
            char = self.get_char()
            if char is None:
                raise SyntaxError("Unterminated stream")
            stream += char
            if stream.endswith(marker):
                break

        return Token(TokenType.Stream, stream[: -len(marker)])

    def lex_string(self) -> Token:
        # Read the entire string content first
        string = b""
        while True:
            char = self.lex_string_char()
            if char is None:
                break
            string += char

        # Default to UTF-8 encoding
        encoding = "utf-8"

        # Check for BOM at the start of the string and remove it
        if string.startswith(b"\xef\xbb\xbf"):
            # UTF-8 BOM - remove it (3 bytes)
            string = string[3:]
        elif string.startswith(b"\xfe\xff"):
            # UTF-16 BE BOM - remove it (2 bytes)
            string = string[2:]
            encoding = "utf-16-be"
        elif string.startswith(b"\xff\xfe"):
            # UTF-16 LE BOM - remove it (2 bytes)
            string = string[2:]
            encoding = "utf-16-le"

        try:
            decoded = string.decode(encoding)
        except UnicodeDecodeError:
            return Token(TokenType.String, string)
        return Token(
            TokenType.String, CosString(decoded, utf16=encoding == "utf-16-be")
        )

    def lex_string_char(self) -> bytes | None:
        char = self.get_char()
        if char is None:
            raise SyntaxError("Unterminated string")
        elif char == b")":
            return None
        elif char == b"\\":
            return self.lex_string_escape()
        else:
            # AE's COS strings hold binary UTF-16 data, so a raw 0x0d / 0x0a
            # byte is part of a character (e.g. U+300D), not a line ending.
            # Preserve it verbatim - normalizing CR/CRLF to LF (per the COS
            # spec for text) would corrupt the data and break round-trip.
            return char

    def lex_string_escape(self) -> bytes:
        char = self.get_char()
        if char is None:
            raise SyntaxError("Unterminated string")

        if char == b"n":
            return b"\n"
        elif char == b"r":
            return b"\r"
        elif char == b"b":
            return b"\b"
        elif char == b"f":
            return b"\f"
        elif char == b"(":
            return b"("
        elif char == b")":
            return b")"
        elif char == b"\\":
            return b"\\"
        elif self.is_octal(char):
            octal = char[0] - ord(b"0")
            for _ in range(2):
                next_char = self.get_char()
                if next_char is None:
                    break
                elif not self.is_octal(next_char):
                    self.unget()
                    break
                octal = octal * 8 + next_char[0] - ord(b"0")
            return octal.to_bytes(1, "big")

        raise SyntaxError("Invalid escape sequence")

    def is_octal(self, char: bytes) -> bool:
        return b"0" <= char <= b"7"

    def is_hex(self, char: bytes) -> bool:
        return char.isdigit() or b"a" <= char <= b"f" or b"A" <= char <= b"F"

    def lex_hex_string(self, hstr: bytes) -> Token:
        while True:
            char = self.get_char()
            if char is None:
                raise SyntaxError("Unterminated hex string")
            elif self.is_hex(char):
                hstr += char
            elif char == b">":
                break
            elif not char.isspace():
                raise SyntaxError(f"Invalid character in hex string: {char!r}")

        if len(hstr) % 2:
            hstr += b"0"

        data = b""
        for i in range(0, len(hstr), 2):
            data += int(hstr[i : i + 2], 16).to_bytes(1, "big")

        return Token(TokenType.HexString, data)

    def lex_identifier(self) -> Token:
        ident = ""
        special = b"()[]<>{}/%"
        while True:
            char = self.get_char()
            if char is None:
                break
            elif char < b"!" or char > b"~":
                self.unget()
                break
            elif char == b"#":
                hexstr = b""
                for _ in range(2):
                    char = self.get_char()
                    if char is None or not self.is_hex(char):
                        raise SyntaxError("Invalid identifier")
                    hexstr += char
                ident += chr(int(hexstr, 16))
            elif char in special:
                self.unget()
                break
            else:
                ident += chr(char[0])

        return Token(TokenType.Identifier, ident)
