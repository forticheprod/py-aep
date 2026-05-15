"""Tests for ChunkField, ComputedField and CosField descriptor contracts."""

from __future__ import annotations

from enum import IntEnum

import pytest

from py_aep.cos.descriptors import CosField
from py_aep.models.descriptors import (
    ChunkField,
    ComputedField,
    _materialization_allowed,
    _suppress_materialization,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeBody:
    """Minimal stub for a chunk body that tracks setattr calls."""

    synthetic: bool

    def __init__(self, *, synthetic: bool = False, **kwargs: object) -> None:
        object.__setattr__(self, "synthetic", synthetic)
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)


class _FakeParent:
    """Minimal stub for a parent chunk with len_body."""

    _parent: _FakeParent | None = None

    def __init__(self, child: _FakeBody) -> None:
        self.body = child
        child._parent = self  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ChunkField contract tests
# ---------------------------------------------------------------------------


class _ScalarModel:
    """Model using a scalar reverse."""

    _body: _FakeBody | None

    quality = ChunkField[int]("_body", "quality", reverse=int)

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _MultiModel:
    """Model using reverse_multi."""

    _body: _FakeBody | None

    frame_rate = ChunkField[float](
        "_body",
        "frame_rate",
        reverse_multi=lambda v, body: {
            "frame_rate_dividend": int(v * 1000),
            "frame_rate_divisor": 1000,
        },
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
                reverse=int,
                reverse_multi=lambda v, b: {"field": v},
            )

    def test_reverse_only_accepted(self) -> None:
        cf = ChunkField[int]("_body", "field", reverse=int)
        assert cf.reverse is int
        assert cf.reverse_multi is None

    def test_reverse_multi_only_accepted(self) -> None:
        fn = lambda v, b: {"field": v}  # noqa: E731
        cf = ChunkField[int]("_body", "field", reverse_multi=fn)
        assert cf.reverse is None
        assert cf.reverse_multi is fn

    def test_neither_accepted(self) -> None:
        cf = ChunkField[int]("_body", "field")
        assert cf.reverse is None
        assert cf.reverse_multi is None


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
    def test_reverse_multi_writes_multiple_fields(self) -> None:
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
# ChunkField contract
# ---------------------------------------------------------------------------


class _ReadOnlyModel:
    """Model with a read-only ChunkField."""

    _body: _FakeBody | None

    width = ChunkField[int]("_body", "width", read_only=True)

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _DefaultModel:
    """Model with a ChunkField that has a default."""

    _body: _FakeBody | None

    tag = ChunkField[str]("_body", "tag", default="none")

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _ValidateModel:
    """Model with a validated ChunkField."""

    _body: _FakeBody | None

    def _check_positive(value: int, obj: object) -> None:  # type: ignore[misc]
        if value < 0:
            raise ValueError("must be positive")

    count = ChunkField[int]("_body", "count", validate=_check_positive)

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _PostSetModel:
    """Model with a post_set callback."""

    _body: _FakeBody | None
    post_called: bool

    mode = ChunkField[int]("_body", "mode", post_set="_on_mode_change")

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body
        self.post_called = False

    def _on_mode_change(self) -> None:
        self.post_called = True


class _SyntheticModel:
    """Model with synthetic body that tracks materialization."""

    _body: _FakeBody | None
    materialized: bool

    value = ChunkField[int]("_body", "value")

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body
        self.materialized = False

    def _ensure_materialized(self) -> None:
        self.materialized = True
        assert self._body is not None
        object.__setattr__(self._body, "synthetic", False)


class _MyEnum(IntEnum):
    OFF = 0
    ON = 1
    AUTO = 2

    @classmethod
    def from_binary(cls, value: int) -> _MyEnum:
        return cls(value)


class _EnumModel:
    """Model with an enum ChunkField."""

    _body: _FakeBody | None

    mode = ChunkField.enum(_MyEnum, "_body", "mode")

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class TestChunkFieldDictOverride:
    """Parse-time __dict__ overrides take priority over chunk body."""

    def test_dict_override_beats_body(self) -> None:
        body = _FakeBody(width=100)
        model = _ReadOnlyModel(body)
        model.__dict__["width"] = 999
        assert model.width == 999

    def test_set_clears_dict_override(self) -> None:
        body = _FakeBody(name="from_body")
        _FakeParent(body)
        model = _DirectModel(body)
        model.__dict__["name"] = "override"
        assert model.name == "override"
        token = _materialization_allowed.set(True)
        try:
            model.name = "written"
        finally:
            _materialization_allowed.reset(token)
        assert "name" not in model.__dict__
        assert model.name == "written"


class TestChunkFieldDefault:
    def test_default_when_body_is_none(self) -> None:
        model = _DefaultModel(None)
        assert model.tag == "none"

    def test_no_default_raises_attribute_error(self) -> None:
        model = _DirectModel(None)
        with pytest.raises(AttributeError, match="is None"):
            _ = model.name

    def test_write_to_none_body_stores_in_dict(self) -> None:
        model = _DirectModel(None)
        token = _materialization_allowed.set(True)
        try:
            model.name = "stored"
        finally:
            _materialization_allowed.reset(token)
        assert model.name == "stored"
        assert model.__dict__["name"] == "stored"


class TestChunkFieldReadOnly:
    def test_read_only_rejects_writes(self) -> None:
        body = _FakeBody(width=100)
        model = _ReadOnlyModel(body)
        with pytest.raises(AttributeError, match="read-only"):
            model.width = 200  # type: ignore[misc]

    def test_read_only_reads_normally(self) -> None:
        body = _FakeBody(width=42)
        model = _ReadOnlyModel(body)
        assert model.width == 42


class TestChunkFieldSuppressMaterialization:
    def test_write_blocked_during_suppress(self) -> None:
        body = _FakeBody(name="old")
        _FakeParent(body)
        model = _DirectModel(body)
        with _suppress_materialization():
            with pytest.raises(RuntimeError, match="during parsing"):
                model.name = "new"
        assert body.name == "old"


class TestChunkFieldSyntheticMaterialization:
    def test_synthetic_body_triggers_ensure_materialized(self) -> None:
        body = _FakeBody(synthetic=True, value=0)
        _FakeParent(body)
        model = _SyntheticModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.value = 42
        finally:
            _materialization_allowed.reset(token)
        assert model.materialized is True
        assert body.synthetic is False
        assert body.value == 42

    def test_non_synthetic_body_skips_materialization(self) -> None:
        body = _FakeBody(synthetic=False, value=0)
        _FakeParent(body)
        model = _SyntheticModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.value = 7
        finally:
            _materialization_allowed.reset(token)
        assert model.materialized is False
        assert body.value == 7


class TestChunkFieldPostSet:
    def test_post_set_fires_after_write(self) -> None:
        body = _FakeBody(mode=0)
        _FakeParent(body)
        model = _PostSetModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.mode = 3
        finally:
            _materialization_allowed.reset(token)
        assert model.post_called is True
        assert body.mode == 3


class TestChunkFieldValidation:
    def test_validate_rejects_invalid_value(self) -> None:
        body = _FakeBody(count=0)
        _FakeParent(body)
        model = _ValidateModel(body)
        token = _materialization_allowed.set(True)
        try:
            with pytest.raises(ValueError, match="must be positive"):
                model.count = -1
        finally:
            _materialization_allowed.reset(token)

    def test_validate_accepts_valid_value(self) -> None:
        body = _FakeBody(count=0)
        _FakeParent(body)
        model = _ValidateModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.count = 5
        finally:
            _materialization_allowed.reset(token)
        assert body.count == 5


class TestChunkFieldEnumValidation:
    def test_invalid_int_rejected(self) -> None:
        body = _FakeBody(mode=0)
        _FakeParent(body)
        model = _EnumModel(body)
        token = _materialization_allowed.set(True)
        try:
            with pytest.raises(ValueError, match="Invalid value 99"):
                model.mode = 99  # type: ignore[assignment]
        finally:
            _materialization_allowed.reset(token)

    def test_valid_enum_member_accepted(self) -> None:
        body = _FakeBody(mode=0)
        _FakeParent(body)
        model = _EnumModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.mode = _MyEnum.ON
        finally:
            _materialization_allowed.reset(token)
        assert body.mode == 1

    def test_valid_int_accepted(self) -> None:
        body = _FakeBody(mode=0)
        _FakeParent(body)
        model = _EnumModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.mode = 2  # type: ignore[assignment]
        finally:
            _materialization_allowed.reset(token)
        assert body.mode == 2


class TestChunkFieldTransform:
    def test_transform_applied_on_get(self) -> None:
        body = _FakeBody(quality=1)
        model = _ScalarModel(body)
        # _ScalarModel has reverse=int but no transform,
        # so we test with a model that does have transform.
        cf = ChunkField[bool]("_body", "flag", transform=bool, reverse=int)
        cf.__set_name__(type(model), "flag")
        model._body = _FakeBody(flag=0)
        assert cf.__get__(model, type(model)) is False
        model._body = _FakeBody(flag=1)
        assert cf.__get__(model, type(model)) is True


# ---------------------------------------------------------------------------
# ComputedField contract tests
# ---------------------------------------------------------------------------


class _ComputedModel:
    """Model with a writable ComputedField."""

    _body: _FakeBody | None

    frame_rate = ComputedField[float](
        "_body",
        compute=lambda b: b.integer + b.fractional / 65536.0,
        reverse=lambda v, b: {
            "integer": int(v),
            "fractional": round((v - int(v)) * 65536),
        },
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _ReadOnlyComputedModel:
    """Model with a read-only ComputedField (no reverse)."""

    _body: _FakeBody | None

    duration = ComputedField[float](
        "_body",
        compute=lambda b: b.dividend / b.divisor,
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _ValidatedComputedModel:
    """Model with a validated ComputedField."""

    _body: _FakeBody | None

    def _check_positive(value: float, obj: object) -> None:  # type: ignore[misc]
        if value <= 0:
            raise ValueError("must be positive")

    rate = ComputedField[float](
        "_body",
        compute=lambda b: b.integer + b.fractional / 65536.0,
        reverse=lambda v, b: {
            "integer": int(v),
            "fractional": round((v - int(v)) * 65536),
        },
        validate=_check_positive,
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _DefaultComputedModel:
    """Model with a ComputedField that has a default."""

    _body: _FakeBody | None

    ratio = ComputedField[float](
        "_body",
        compute=lambda b: b.num / b.den,
        default=1.0,
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _SyntheticComputedModel:
    """Model with synthetic body for ComputedField."""

    _body: _FakeBody | None
    materialized: bool

    rate = ComputedField[float](
        "_body",
        compute=lambda b: b.integer + b.fractional / 65536.0,
        reverse=lambda v, b: {
            "integer": int(v),
            "fractional": round((v - int(v)) * 65536),
        },
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body
        self.materialized = False

    def _ensure_materialized(self) -> None:
        self.materialized = True
        assert self._body is not None
        object.__setattr__(self._body, "synthetic", False)


class TestComputedFieldRead:
    def test_compute_from_multiple_fields(self) -> None:
        body = _FakeBody(integer=24, fractional=0)
        model = _ComputedModel(body)
        assert model.frame_rate == 24.0

    def test_compute_fractional(self) -> None:
        body = _FakeBody(integer=29, fractional=63897)
        model = _ComputedModel(body)
        assert abs(model.frame_rate - 29.97) < 0.01

    def test_read_only_field_computes(self) -> None:
        body = _FakeBody(dividend=300, divisor=10)
        model = _ReadOnlyComputedModel(body)
        assert model.duration == 30.0


class TestComputedFieldWrite:
    def test_reverse_writes_multiple_fields(self) -> None:
        body = _FakeBody(integer=0, fractional=0)
        _FakeParent(body)
        model = _ComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.frame_rate = 24.0
        finally:
            _materialization_allowed.reset(token)
        assert body.integer == 24
        assert body.fractional == 0

    def test_reverse_fractional_value(self) -> None:
        body = _FakeBody(integer=0, fractional=0)
        _FakeParent(body)
        model = _ComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.frame_rate = 29.97
        finally:
            _materialization_allowed.reset(token)
        assert body.integer == 29
        assert abs(body.fractional - 63569) < 2

    def test_read_only_rejects_writes(self) -> None:
        body = _FakeBody(dividend=300, divisor=10)
        model = _ReadOnlyComputedModel(body)
        with pytest.raises(AttributeError, match="read-only"):
            model.duration = 5.0  # type: ignore[misc]


class TestComputedFieldDictOverride:
    def test_dict_override_beats_compute(self) -> None:
        body = _FakeBody(integer=24, fractional=0)
        model = _ComputedModel(body)
        model.__dict__["frame_rate"] = 99.0
        assert model.frame_rate == 99.0

    def test_write_clears_dict_override(self) -> None:
        body = _FakeBody(integer=24, fractional=0)
        _FakeParent(body)
        model = _ComputedModel(body)
        model.__dict__["frame_rate"] = 99.0
        token = _materialization_allowed.set(True)
        try:
            model.frame_rate = 30.0
        finally:
            _materialization_allowed.reset(token)
        assert "frame_rate" not in model.__dict__
        assert model.frame_rate == 30.0


class TestComputedFieldDefault:
    def test_default_when_body_is_none(self) -> None:
        model = _DefaultComputedModel(None)
        assert model.ratio == 1.0

    def test_no_default_raises_attribute_error(self) -> None:
        model = _ReadOnlyComputedModel(None)
        with pytest.raises(AttributeError, match="is None"):
            _ = model.duration

    def test_write_to_none_body_stores_in_dict(self) -> None:
        model = _ComputedModel(None)
        token = _materialization_allowed.set(True)
        try:
            model.frame_rate = 25.0
        finally:
            _materialization_allowed.reset(token)
        assert model.frame_rate == 25.0
        assert model.__dict__["frame_rate"] == 25.0


class TestComputedFieldSuppressMaterialization:
    def test_write_blocked_during_suppress(self) -> None:
        body = _FakeBody(integer=24, fractional=0)
        _FakeParent(body)
        model = _ComputedModel(body)
        with _suppress_materialization():
            with pytest.raises(RuntimeError, match="during parsing"):
                model.frame_rate = 30.0


class TestComputedFieldSyntheticMaterialization:
    def test_synthetic_body_triggers_ensure_materialized(self) -> None:
        body = _FakeBody(synthetic=True, integer=0, fractional=0)
        _FakeParent(body)
        model = _SyntheticComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.rate = 24.0
        finally:
            _materialization_allowed.reset(token)
        assert model.materialized is True
        assert body.synthetic is False

    def test_non_synthetic_body_skips_materialization(self) -> None:
        body = _FakeBody(synthetic=False, integer=0, fractional=0)
        _FakeParent(body)
        model = _SyntheticComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.rate = 24.0
        finally:
            _materialization_allowed.reset(token)
        assert model.materialized is False


class TestComputedFieldValidation:
    def test_validate_rejects_invalid_value(self) -> None:
        body = _FakeBody(integer=0, fractional=0)
        _FakeParent(body)
        model = _ValidatedComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            with pytest.raises(ValueError, match="must be positive"):
                model.rate = -1.0
        finally:
            _materialization_allowed.reset(token)

    def test_validate_accepts_valid_value(self) -> None:
        body = _FakeBody(integer=0, fractional=0)
        _FakeParent(body)
        model = _ValidatedComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.rate = 24.0
        finally:
            _materialization_allowed.reset(token)
        assert body.integer == 24


class TestComputedFieldClassAccess:
    def test_class_access_returns_descriptor(self) -> None:
        assert isinstance(_ComputedModel.frame_rate, ComputedField)


# ---------------------------------------------------------------------------
# ComputedField.enum contract tests
# ---------------------------------------------------------------------------


class _EnumComputedModel:
    """Model with a ComputedField.enum for an IntEnum-backed computed field."""

    _body: _FakeBody | None

    mode = ComputedField.enum(
        _MyEnum,
        "_body",
        compute=lambda b: _MyEnum(b.mode_flag),
        reverse=lambda v, b: {"mode_flag": int(v)},
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class _ReadOnlyEnumComputedModel:
    """Model with a read-only ComputedField.enum."""

    _body: _FakeBody | None

    mode = ComputedField.enum(
        _MyEnum,
        "_body",
        compute=lambda b: _MyEnum(b.mode_flag),
    )

    def __init__(self, body: _FakeBody | None) -> None:
        self._body = body


class TestComputedFieldEnumRead:
    def test_compute_returns_enum_member(self) -> None:
        body = _FakeBody(mode_flag=1)
        model = _EnumComputedModel(body)
        assert model.mode is _MyEnum.ON

    def test_read_only_enum_computes(self) -> None:
        body = _FakeBody(mode_flag=0)
        model = _ReadOnlyEnumComputedModel(body)
        assert model.mode is _MyEnum.OFF


class TestComputedFieldEnumWrite:
    def test_valid_enum_member_accepted(self) -> None:
        body = _FakeBody(mode_flag=0)
        _FakeParent(body)
        model = _EnumComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.mode = _MyEnum.ON
        finally:
            _materialization_allowed.reset(token)
        assert body.mode_flag == 1

    def test_valid_int_accepted(self) -> None:
        body = _FakeBody(mode_flag=0)
        _FakeParent(body)
        model = _EnumComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            model.mode = 1  # type: ignore[assignment]
        finally:
            _materialization_allowed.reset(token)
        assert body.mode_flag == 1

    def test_invalid_int_rejected(self) -> None:
        body = _FakeBody(mode_flag=0)
        _FakeParent(body)
        model = _EnumComputedModel(body)
        token = _materialization_allowed.set(True)
        try:
            with pytest.raises(ValueError, match="Invalid value 99"):
                model.mode = 99  # type: ignore[assignment]
        finally:
            _materialization_allowed.reset(token)

    def test_read_only_enum_rejects_writes(self) -> None:
        body = _FakeBody(mode_flag=0)
        model = _ReadOnlyEnumComputedModel(body)
        with pytest.raises(AttributeError, match="read-only"):
            model.mode = _MyEnum.ON  # type: ignore[misc]


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
