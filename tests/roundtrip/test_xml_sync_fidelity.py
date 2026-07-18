"""The XML `Ropt` body must stay byte-faithful to what AE writes.

The `Ropt` header restates the body's own sizes and **After Effects honours
them**: it reads exactly `len(body)` bytes from offset 6 and discards the
rest. `_sync_xml` used to copy the header verbatim while re-serializing a
longer XML, so AE silently truncated the block mid-element on open and
re-saved the corruption - no error, no exception (probed on AE 26.3: an
87-byte-longer body was cut back to the stale length, losing the closing
`</PremiereData>`).

py->py round-trips cannot catch any of this, which is how it survived: py
re-reads its own XML happily. These tests compare against AE's own bytes.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from py_aep import parse
from py_aep.models.renderqueue.format_options import XmlFormatOptions
from py_aep.models.renderqueue.format_options.xml import (
    _LEN_BODY_OFFSET,
    _LEN_XML_OFFSET,
    _XML_TERMINATOR,
)

FORMAT_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "format_options"
)

#: One AE-authored module per XML-backed format code.
PER_FORMAT = [
    pytest.param(FORMAT_DIR / "h.264" / "base.aep", "H264", id="h264"),
    pytest.param(FORMAT_DIR / "avi" / "base.aep", ".AVI", id="avi"),
    pytest.param(FORMAT_DIR / "mp3" / "mp3_mono_320.aep", "Mp3 ", id="mp3"),
    pytest.param(FORMAT_DIR / "quicktime" / "base.aep", "MooV", id="quicktime"),
    pytest.param(FORMAT_DIR / "wav" / "base.aep", "wao_", id="wav"),
]


def _options(path: Path) -> tuple:
    project = parse(path).project
    opts = project.render_queue.items[0].output_modules[0].format_options
    return project, opts


def _header_lengths(body: bytes) -> tuple[int, int]:
    return (
        struct.unpack_from(">I", body, _LEN_BODY_OFFSET)[0],
        struct.unpack_from(">I", body, _LEN_XML_OFFSET)[0],
    )


#: Python 3.7's `ET.tostring` sorts each element's attributes alphabetically;
#: 3.8+ keeps document order, which is what AE writes. A 3.7 write therefore
#: reorders attributes - same length, same semantics, different bytes - so
#: only the byte-identity assertions are version-gated. The length/terminator
#: invariants below (the ones AE actually honours) run everywhere.
_ATTR_ORDER_PRESERVED = sys.version_info >= (3, 8)


class TestNoOpSyncIsIdentity:
    """Re-serializing an untouched tree must reproduce AE's bytes exactly."""

    @pytest.mark.skipif(
        not _ATTR_ORDER_PRESERVED,
        reason="py3.7 ET.tostring sorts attributes; bytes differ, semantics do not",
    )
    @pytest.mark.parametrize(("sample", "format_code"), PER_FORMAT)
    def test_no_op_sync_is_byte_identical(self, sample: Path, format_code: str) -> None:
        _, opts = _options(sample)
        assert isinstance(opts, XmlFormatOptions)
        assert opts.format_code == format_code
        before = opts._body.data
        opts._sync_xml()  # no semantic change whatsoever
        assert opts._body.data == before

    @pytest.mark.parametrize(("sample", "format_code"), PER_FORMAT)
    def test_no_op_sync_preserves_length_on_every_python(
        self, sample: Path, format_code: str
    ) -> None:
        # The part AE honours holds even on 3.7, where attribute reordering
        # costs byte-identity: same length, still self-consistent.
        _, opts = _options(sample)
        assert isinstance(opts, XmlFormatOptions)
        before = len(opts._body.data)
        opts._sync_xml()
        body = opts._body.data
        assert len(body) == before
        assert _header_lengths(body)[0] == len(body)
        assert body.endswith(_XML_TERMINATOR)

    @pytest.mark.parametrize(("sample", "format_code"), PER_FORMAT)
    def test_ae_body_is_self_consistent(self, sample: Path, format_code: str) -> None:
        # The invariant the fix maintains, as AE itself writes it.
        _, opts = _options(sample)
        assert isinstance(opts, XmlFormatOptions)
        body = opts._body.data
        assert opts._xml_header is not None
        xml_len = len(body) - len(opts._xml_header)
        body_len_field, xml_len_field = _header_lengths(body)
        assert body_len_field == len(body)
        assert xml_len_field == xml_len - 2
        assert body.endswith(_XML_TERMINATOR)


class TestWriteKeepsHeaderConsistent:
    """A real param write must repatch the lengths, or AE truncates."""

    @pytest.mark.parametrize(("sample", "format_code"), PER_FORMAT)
    def test_param_write_updates_length_fields(
        self, sample: Path, format_code: str
    ) -> None:
        _, opts = _options(sample)
        assert isinstance(opts, XmlFormatOptions)
        # A param that exists on every XML format and changes the length.
        opts.params["ADBEPyAepFidelityProbe"] = "1234567890"
        body = opts._body.data
        assert opts._xml_header is not None
        xml_len = len(body) - len(opts._xml_header)
        body_len_field, xml_len_field = _header_lengths(body)
        assert body_len_field == len(body)
        assert xml_len_field == xml_len - 2
        assert body.endswith(_XML_TERMINATOR)

    def test_growing_write_updates_length(self, tmp_path: Path) -> None:
        project, opts = _options(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        original = len(opts._body.data)
        opts.params["ADBEPyAepFidelityProbe"] = "x" * 400
        assert len(opts._body.data) > original
        assert _header_lengths(opts._body.data)[0] == len(opts._body.data)
        project.save(tmp_path / "out.aep")
        _, reparsed = _options(tmp_path / "out.aep")
        assert isinstance(reparsed, XmlFormatOptions)
        assert _header_lengths(reparsed._body.data)[0] == len(reparsed._body.data)

    def test_shrinking_write_updates_length(self) -> None:
        # A stale field that is too LARGE would make AE read past the block.
        _, opts = _options(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts.params["ADBEPyAepFidelityProbe"] = "x" * 400
        grown = len(opts._body.data)
        del opts.params["ADBEPyAepFidelityProbe"]
        assert len(opts._body.data) < grown
        assert _header_lengths(opts._body.data)[0] == len(opts._body.data)


class TestSerializerMatchesAeStyle:
    """The specific divergences that made a no-op sync lossy."""

    def test_declaration_is_double_quoted(self) -> None:
        _, opts = _options(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts._sync_xml()
        assert b'<?xml version="1.0" encoding="UTF-8"?>' in opts._body.data

    def test_self_closing_tags_have_no_space(self) -> None:
        _, opts = _options(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts._sync_xml()
        assert b" />" not in opts._body.data
        assert b"/>" in opts._body.data

    def test_attributeless_empty_elements_are_expanded(self) -> None:
        # AE self-closes `<Foo ObjectRef="1"/>` but expands `<ParamName></ParamName>`.
        _, opts = _options(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts._sync_xml()
        assert b"<ParamName></ParamName>" in opts._body.data
        assert b"<ParamName/>" not in opts._body.data

    def test_terminator_survives_a_write(self) -> None:
        _, opts = _options(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts.params["ADBEPyAepFidelityProbe"] = "1"
        assert opts._body.data.endswith(b">\n\x00\x00")
