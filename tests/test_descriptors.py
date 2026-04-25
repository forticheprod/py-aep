"""Tests for ChunkField and CosField descriptor contracts."""

from __future__ import annotations

import pytest

from py_aep.cos.descriptors import CosField
from py_aep.kaitai.descriptors import ChunkField
from py_aep.kaitai.proxy import _materialization_allowed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeBody:
    """Minimal stub for a chunk body that tracks setattr calls."""

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)

    def _check(self) -> None:
        pass


class _FakeParent:
    """Minimal stub for a parent chunk with _check and len_body."""

    _parent: _FakeParent | None = None
    len_body = 100

    def __init__(self, child: _FakeBody) -> None:
        self.body = child
        child._parent = self  # type: ignore[attr-defined]

    def _check(self) -> None:
        pass


# ---------------------------------------------------------------------------
# ChunkField contract tests
# ---------------------------------------------------------------------------


class _ScalarModel:
    """Model using a scalar reverse."""

    _body: _FakeBody | None

    quality = ChunkField[int]("_body", "quality", reverse_seq_field=int)

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _MultiModel:
    """Model using reverse_instance_field."""

    _body: _FakeBody | None

    frame_rate = ChunkField[float](
        "_body",
        "frame_rate",
        reverse_instance_field=lambda v, body: {
            "frame_rate_dividend": int(v * 1000),
            "frame_rate_divisor": 1000,
        },
        invalidates=["frame_rate"],
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _DirectModel:
    """Model with no reverse (direct write)."""

    _body: _FakeBody | None

    name = ChunkField[str]("_body", "name")

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class TestChunkFieldMutualExclusion:
    def test_both_reverse_seq_and_instance_raises(self) -> None:
        with pytest.raises(TypeError, match="Cannot set both"):
            ChunkField(
                "_body",
                "field",
                reverse_seq_field=int,
                reverse_instance_field=lambda v, b: {"field": v},
            )

    def test_reverse_seq_field_only_accepted(self) -> None:
        cf = ChunkField[int]("_body", "field", reverse_seq_field=int)
        assert cf.reverse_seq_field is int
        assert cf.reverse_instance_field is None

    def test_reverse_instance_field_only_accepted(self) -> None:
        fn = lambda v, b: {"field": v}  # noqa: E731
        cf = ChunkField[int]("_body", "field", reverse_instance_field=fn)
        assert cf.reverse_seq_field is None
        assert cf.reverse_instance_field is fn

    def test_neither_accepted(self) -> None:
        cf = ChunkField[int]("_body", "field")
        assert cf.reverse_seq_field is None
        assert cf.reverse_instance_field is None


class TestChunkFieldScalarReverse:
    def test_scalar_reverse_writes_one_field(self) -> None:
        body = _FakeBody(quality=0)
        _FakeParent(body)
        model = _ScalarModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.quality = 5
        finally:
            _materialization_allowed.reset(token)
        assert body.quality == 5

    def test_scalar_reverse_does_not_touch_other_fields(self) -> None:
        body = _FakeBody(quality=0, other=99)
        _FakeParent(body)
        model = _ScalarModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.quality = 10
        finally:
            _materialization_allowed.reset(token)
        assert body.other == 99


class TestChunkFieldReverseInstanceField:
    def test_reverse_instance_field_writes_multiple_fields(self) -> None:
        body = _FakeBody(
            frame_rate=0,
            frame_rate_dividend=0,
            frame_rate_divisor=1,
        )
        _FakeParent(body)
        model = _MultiModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.frame_rate = 24.0
        finally:
            _materialization_allowed.reset(token)
        assert body.frame_rate_dividend == 24000
        assert body.frame_rate_divisor == 1000

    def test_reverse_instance_field_invalidates_field_name(self) -> None:
        """The descriptor's own field is auto-invalidated for instance writes."""
        invalidated: list[str] = []
        body = _FakeBody(
            frame_rate=0,
            frame_rate_dividend=0,
            frame_rate_divisor=1,
        )
        _FakeParent(body)

        def fake_invalidate() -> None:
            invalidated.append("frame_rate")

        body._invalidate_frame_rate = fake_invalidate  # type: ignore[attr-defined]
        model = _MultiModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.frame_rate = 30.0
        finally:
            _materialization_allowed.reset(token)
        assert "frame_rate" in invalidated


class TestChunkFieldDirectWrite:
    def test_direct_write_without_reverse(self) -> None:
        body = _FakeBody(name="old")
        _FakeParent(body)
        model = _DirectModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.name = "new"
        finally:
            _materialization_allowed.reset(token)
        assert body.name == "new"


# ---------------------------------------------------------------------------
# CosField contract tests
# ---------------------------------------------------------------------------


class _CosModel:
    """Model using CosField with scalar reverse."""

    _style: dict[str, object] | None

    font_size = CosField[float]("_style", "1", transform=float, reverse=float)

    def __init__(self, style: dict[str, object] | None) -> None:
        self._style = style
        self._propagate_called = False

    def _propagate_cos(self) -> None:
        self._propagate_called = True


class TestCosFieldScalarReverse:
    def test_scalar_reverse_writes_to_dict(self) -> None:
        style: dict[str, object] = {"1": 12}
        model = _CosModel(style)
        model.font_size = 24.0
        assert style["1"] == 24.0

    def test_propagate_cos_called(self) -> None:
        style: dict[str, object] = {"1": 12}
        model = _CosModel(style)
        model.font_size = 18.0
        assert model._propagate_called is True

    def test_none_value_removes_key(self) -> None:
        style: dict[str, object] = {"1": 12}
        model = _CosModel(style)
        model.font_size = None  # type: ignore[assignment]
        assert "1" not in style
