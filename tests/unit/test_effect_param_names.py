"""Effect parameter names in the project's code page.

Projects saved before AE 26 store `pard` names in the system code page: AE
reads Set Channels' "Set Red To Source 1's" from a Windows project with a
U+2019 apostrophe, byte 0x92 in Windows-1252. Characters are written as
code points so the test does not depend on its own encoding.
"""

from __future__ import annotations

import pytest

from py_aep.parsers.effect import _decode_pard_name

_APOSTROPHE = chr(0x2019)


@pytest.mark.parametrize(
    ("raw", "code_page", "expected"),
    [
        (b"Set Red To Source 1\x92s", 1252, f"Set Red To Source 1{_APOSTROPHE}s"),
        (b"Set Red To Source 1\xd5s", 0x0100, f"Set Red To Source 1{_APOSTROPHE}s"),
        # Valid UTF-8 (AE 26 projects) is kept, whatever the code page.
        (b"Caf\xc3\xa9", 1252, "Caf" + chr(0xE9)),
        (b"Blur", 1252, "Blur"),
        # A code page Python has no codec for: kept as read.
        (b"a\x92", 99999, "a" + chr(0xDC92)),
    ],
)
def test_decodes_in_the_project_code_page(
    raw: bytes, code_page: int, expected: str
) -> None:
    # As the pard chunk reads it: UTF-8, other bytes kept as surrogates.
    name = raw.decode("utf-8", "surrogateescape")
    assert _decode_pard_name(name, code_page) == expected
