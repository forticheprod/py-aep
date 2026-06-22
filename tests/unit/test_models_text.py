"""Tests for TextDocument and FontObject model parsing and roundtrip."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from py_aep.enums import (
    PropertyValueType,
)
from py_aep.parsers import specialized_properties

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"


class TestParseTextDocument:
    """Unit tests for Source Text property parsing fallbacks."""

    def test_ignores_malformed_cos_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Malformed COS data should keep the property but skip the value."""
        prop = SimpleNamespace(
            keyframes=[],
            value=None,
            _property_value_type=None,
        )
        tdbs_chunk = SimpleNamespace(chunks=[])
        btdk_chunk = SimpleNamespace(data=b"bad")
        root_chunk = SimpleNamespace(chunks=[])

        def fake_find_by_list_type(*, chunks: object, list_type: str):
            if list_type == "tdbs":
                return tdbs_chunk
            if list_type == "btdk":
                return btdk_chunk
            raise AssertionError(f"Unexpected list_type: {list_type}")

        class BrokenCosParser:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def parse(self) -> dict[str, object]:
                raise SyntaxError("bad COS")

        monkeypatch.setattr(
            specialized_properties,
            "find_by_list_type",
            fake_find_by_list_type,
        )
        monkeypatch.setattr(
            specialized_properties,
            "parse_property",
            lambda **_kwargs: prop,
        )
        monkeypatch.setattr(
            specialized_properties,
            "CosParser",
            BrokenCosParser,
        )

        result = specialized_properties.parse_text_document(
            btds_chunk=root_chunk,
            match_name="ADBE Text Document",
            property_depth=0,
            composition=SimpleNamespace(),
            tdmn=SimpleNamespace(),
        )

        assert result is prop
        assert prop._property_value_type == PropertyValueType.TEXT_DOCUMENT
        assert prop.value is None

    def test_raises_unexpected_cos_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unexpected bugs in COS conversion should still surface."""
        prop = SimpleNamespace(
            keyframes=[],
            value=None,
            _property_value_type=None,
        )
        tdbs_chunk = SimpleNamespace(chunks=[])
        btdk_chunk = SimpleNamespace(data=b"ok")
        root_chunk = SimpleNamespace(chunks=[])

        def fake_find_by_list_type(*, chunks: object, list_type: str):
            if list_type == "tdbs":
                return tdbs_chunk
            if list_type == "btdk":
                return btdk_chunk
            raise AssertionError(f"Unexpected list_type: {list_type}")

        class ValidCosParser:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def parse(self) -> dict[str, object]:
                return {}

        def raise_runtime_error(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("boom")

        monkeypatch.setattr(
            specialized_properties,
            "find_by_list_type",
            fake_find_by_list_type,
        )
        monkeypatch.setattr(
            specialized_properties,
            "parse_property",
            lambda **_kwargs: prop,
        )
        monkeypatch.setattr(
            specialized_properties,
            "CosParser",
            ValidCosParser,
        )
        monkeypatch.setattr(
            specialized_properties,
            "parse_btdk_cos",
            raise_runtime_error,
        )

        with pytest.raises(RuntimeError, match="boom"):
            specialized_properties.parse_text_document(
                btds_chunk=root_chunk,
                match_name="ADBE Text Document",
                property_depth=0,
                composition=SimpleNamespace(),
                tdmn=SimpleNamespace(),
            )
