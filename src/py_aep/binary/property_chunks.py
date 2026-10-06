"""Property-level chunk types: tdsb, tdb4, cdat, tdum/tduM.

TdsbChunk and Tdb4Chunk use `fmt_field()` with `BitField` descriptors.
CdatChunk and TdumChunk override `read()` / `write()` because they
have variable-length or context-dependent layouts.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, TypeVar

from attrs import Factory, define

from .bin_utils import read_bytes, write_bytes
from .bitfield import BitField
from .chunk import Chunk, ContainerChunk
from .fmt_field import (
    bool_field,
    bytes_field,
    f8_field,
    u1_field,
    u2_field,
    u4_field,
)
from .registry import register
from .scalar_chunks import Utf8Chunk, _StringChunkBase
from .utils import find_by_type

if TYPE_CHECKING:
    from typing import IO, Any


# ---------------------------------------------------------------------------
# tdsb - property flags (4 bytes, always inside LIST:tdbs at index 0)
# ---------------------------------------------------------------------------


@register("tdsb")
@define
class TdsbChunk(Chunk):
    """Property flags chunk (4 bytes).

    Bit-level flags are exposed via `BitField` descriptors that read/write
    through the raw byte fields.
    """

    chunk_type: str = "tdsb"

    roto_bezier: bool = bool_field()
    """RotoBezier flag for mask shapes (byte 0). 1 = enabled."""

    _pad1: int = u1_field(repr=False)
    _lock_flags: int = u1_field(repr=False)
    _enable_flags: int = u1_field(default=1, repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    ratio_unlinked = BitField("_lock_flags", 5)
    """Set when a Scale or Mask Feather's dimensions are unlinked (its
    constrain-proportions switch off). Clear on new layers; in AE-saved
    projects only those two streams carry it, mostly on non-uniform
    values."""
    dimensions_separated = BitField("_lock_flags", 3)
    """Whether a separation leader's dimensions are split.

    Bit 3 of the lock byte, NOT bit 1 of the enable byte: that one is the
    Timeline `hidden` flag, and it is also set on an UNSEPARATED position
    that does not apply (an ambient light, an environment light). Checked
    against every AE-exported `dimensionsSeparated` in the sample corpus -
    the lock bit agrees 288/288, the enable bit 285/288."""
    enabled = BitField("_enable_flags", 0)
    hidden = BitField("_enable_flags", 1)
    """The stream is hidden in the Timeline because it does not apply to
    the layer as it is: a 3D-only property on a 2D layer, an option of
    another light type, a separated position's leader, an effect parameter
    its plugin hides. AE refuses an expression on a hidden stream, and
    recomputes the flag from the layer's state when it opens a project, so
    it never changes what renders."""


# ---------------------------------------------------------------------------
# tdb4 - property metadata (124 bytes, inside LIST:tdbs at index 2)
# ---------------------------------------------------------------------------
#
# Struct layout (big-endian, 124 bytes):
#   H   magic (0xdb99)
#   H   dimensions
#   B   pad1
#   B   spatial/static flags
#   H   pad2a
#   H   value_hint_type
#   B   value_hint_flag
#   B   can_vary_over_time flags
#   H   pad3a
#   H   time_base (0x7800 when has_time_base, else 0)
#   5d  unknown floats (threshold, aspect, 1.0, 1.0, 1.0)
#   B   pad4
#   B   no_value flags
#   B   pad5
#   B   type flags (vector, integer, color)
#   B   property_category
#   I   pad6a
#   H   pad6b
#   B   pad6c
#   B   animated
#   3s  pad
#   I   reserved_48
#   B   reserved_4c
#   B   reserved_4d
#   B   pad
#   B   spatial_marker
#   I   pad
#   4d  reserved_54 / 5c / 64 / 6c
#   H   pad9a
#   B   pad9b
#   B   expression_disabled flags
#   I   pad10


@register("tdb4")
@define
class Tdb4Chunk(Chunk):
    """Property metadata chunk (124 bytes)."""

    chunk_type: str = "tdb4"

    _magic: int = u2_field(default=0xDB99, repr=False)
    dimensions: int = u2_field(default=1)
    _pad1: int = u1_field(repr=False)
    _spatial_static_flags: int = u1_field(default=1, repr=False)
    _pad2a: int = u2_field(repr=False)
    _value_hint_type: int = u2_field(repr=False)
    _value_hint_flag: int = u1_field(repr=False)
    _cvot_flags: int = u1_field(repr=False)
    _time_base: int = u4_field(repr=False)
    """Keyframe time units per second for the OWNING LAYER.

    `layer_timebase(cdta.internal_timebase, layer.stretch / 100)` (see
    `composition_chunks.layer_timebase`) - a full
    32-bit field, not a 16-bit one: a 300 % stretched layer at 24 fps stores
    73728 (0x00012000), which does not fit in two bytes (measured on AE 2026
    across 50 / 101 / 150 / 300 / -150 % stretch)."""
    _arc_accuracy: float = f8_field(default=0.0001, repr=False)
    """Tolerance AE fits a spatial segment's arc-length spline to, as a
    squared distance in the measured space: 1e-4 for a value stored in
    pixels, 6.25e-12 for a point stored normalized to its layer."""
    pixel_aspect: float = f8_field(default=1.0, repr=False)
    """X multiplier AE measures a motion path with (the first of four,
    one per dimension): the containing comp's pixel aspect ratio for a
    layer's spatial property, the layer's display aspect (width / height)
    for a normalized point; 1.0 elsewhere."""
    _arc_multiplier_y: float = f8_field(default=1.0, repr=False)
    _arc_multiplier_z: float = f8_field(default=1.0, repr=False)
    _arc_multiplier_w: float = f8_field(default=1.0, repr=False)
    _pad4: int = u1_field(repr=False)
    _no_value_flags: int = u1_field(repr=False)
    _pad5: int = u1_field(repr=False)
    _type_flags: int = u1_field(repr=False)
    _property_category: int = u1_field(repr=False)
    _pad6a: int = u4_field(repr=False)
    _pad6b: int = u2_field(repr=False)
    _pad6c: int = u1_field(repr=False)
    animated: bool = bool_field()
    _pad_45: bytes = bytes_field(3, repr=False)
    _reserved_48: int = u4_field(repr=False)
    """A time in timebase units, or 0x80000000, in the samples."""
    _reserved_4c: int = u1_field(repr=False)
    _reserved_4d: int = u1_field(repr=False)
    _pad_4e: int = u1_field(repr=False)
    _spatial_marker: int = u1_field(repr=False)
    """Byte 0x4F, the keyframe record's key flags: non-zero (bit 0) on a
    spatial stream. Kept as the whole byte, not a `bool`: After Effects
    writes 0x07 on the Transform effect's points in some production
    projects, and coercing it to 1 changed those bytes as soon as their
    layer was read."""
    _pad_50: int = u4_field(repr=False)
    # Four doubles: 0.0 in the samples, 0x5C / 0x6C sometimes 0.16666666667.
    _reserved_54: float = f8_field(repr=False)
    _reserved_5c: float = f8_field(repr=False)
    _reserved_64: float = f8_field(repr=False)
    _reserved_6c: float = f8_field(repr=False)
    _pad9a: int = u2_field(repr=False)
    _pad9b: int = u1_field(repr=False)
    _expr_flags: int = u1_field(repr=False)
    _pad10: int = u4_field(repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    is_spatial = BitField("_spatial_static_flags", 3)
    static = BitField("_spatial_static_flags", 0)
    can_vary_over_time = BitField("_cvot_flags", 1)
    no_value = BitField("_no_value_flags", 0)
    vector = BitField("_type_flags", 3)
    integer = BitField("_type_flags", 2)
    color = BitField("_type_flags", 0)
    expression_disabled = BitField("_expr_flags", 0)
    # AE's expression-present marker: the high byte of `_pad10` (0x01000000),
    # set whenever an expression Utf8 is present (independent of enabled/
    # disabled). AE rejects a file with the marker set but no expression Utf8
    # as "missing data in file".
    has_expression = BitField("_pad10", 24)

    @property
    def has_time_base(self) -> bool:
        return self._time_base != 0


# ---------------------------------------------------------------------------
# tdb4 state-template helpers
#
# The animated helper encodes AE's animated field sets for the three
# property classes (color / spatial / plain numeric); the static helper
# encodes AE's animated -> static transition. They are free functions
# rather than methods because the business logic lives in the model layer;
# chunk classes are data containers.
#
# Both were measured on AE 2026 output across 1D / 2D / 3D / spatial /
# color properties; `_animate_tdb4` and `_static_tdb4` in property.py are
# the callers.
# ---------------------------------------------------------------------------


def tdb4_apply_animated_template(t: Tdb4Chunk, *, color: bool, spatial: bool) -> None:
    """Apply AE's animated-property tdb4 field set in-place.

    Sets the fields that differ between static and animated state for the
    three property classes:
    - color  (`color=True, spatial=False`)
    - spatial (`color=False, spatial=True`)
    - plain numeric / vector (`color=False, spatial=False`)

    Args:
        t: The `Tdb4Chunk` to mutate.
        color: `True` for color properties.
        spatial: `True` for spatial (position / point) properties.
    """
    t.animated = True
    t._cvot_flags = 0xFF
    t._value_hint_flag = 0xFF
    # Do NOT set _time_base here: it is the containing comp's
    # internal_timebase, which this layer cannot know. The caller stamps it
    # (Property._ensure_time_base). Hard-coding 24576 here wrote a 24 fps
    # timebase into every animated property of every non-24 fps comp.
    if color:
        t._property_category = 0x01
        t._value_hint_type = 2
        t._spatial_static_flags = 6
        t._pad2a = 1
    elif spatial:
        t._property_category = 0x09
        t._type_flags |= 0x08
        t._value_hint_type = 0xFFFF
        t._spatial_static_flags = 14
        t._pad2a = 3
    else:
        t._property_category = 0x09
        t._type_flags |= 0x08
        t._value_hint_type = 1
        t._spatial_static_flags = 0
        t._pad2a = 0


def tdb4_clear_keyframe_record(t: Tdb4Chunk) -> None:
    """Zero the keyframe record a static stream keeps (0x48-0x73), as AE
    does on every animated stream."""
    t._reserved_48 = t._reserved_4c = t._reserved_4d = t._pad_4e = 0
    t._spatial_marker = False
    t._pad_50 = 0
    t._reserved_54 = t._reserved_5c = t._reserved_64 = t._reserved_6c = 0.0


def tdb4_apply_static_template(
    t: Tdb4Chunk,
    *,
    in_interpolation: int,
    out_interpolation: int,
    spatial_flags: int,
) -> None:
    """Apply AE's animated -> static transition in-place (the last keyframe
    was removed).

    AE sets the static bit, clears the animated flag, sets the record's
    key-flag bit 0 (0x4F) when the stream flags have bit 1, and stores the
    removed keyframe's in/out interpolation (0x4C/0x4D) and spatial flags
    (0x50); every other byte keeps its animated value - category,
    value-hint and cvot bytes and time base included (measured on AE 2026
    for Position, Scale, Rotation, Opacity, an effect colour, a mask path
    and a shape group's Position and Fill Color). Restoring the bytes of a
    never-animated stream instead makes AE ignore the static value: a layer
    or shape Position reads back at its default and a shape Fill Color
    fails to evaluate.

    Args:
        t: The `Tdb4Chunk` to mutate.
        in_interpolation: The removed keyframe's in interpolation code.
        out_interpolation: The removed keyframe's out interpolation code.
        spatial_flags: The removed keyframe's spatial flags (0 for a
            non-spatial keyframe).
    """
    t.static = True
    t.animated = False
    t._spatial_marker = bool(t._spatial_static_flags & 0x02)
    t._reserved_4c = in_interpolation
    t._reserved_4d = out_interpolation
    t._pad_50 = spatial_flags


def tdb4_apply_vf_axis_template(t: Tdb4Chunk) -> None:
    """Apply AE's active variable-font-axis tdb4 field set in-place.

    AE 2026 canon for an active `ADBE Text VF Axis` slot (byte-diffed
    against the variable_font_axis_static fixture).

    Args:
        t: The `Tdb4Chunk` to mutate.
    """
    t.dimensions = 2
    t._value_hint_type = 1
    t._cvot_flags = 7
    t._type_flags = 8
    t._property_category = 9


# ---------------------------------------------------------------------------
# cdat - property value doubles (variable length, optional LE for OTST)
# ---------------------------------------------------------------------------


@register("cdat")
@define
class CdatChunk(Chunk):
    """Property value chunk storing one or more doubles.

    Normally big-endian.  When `is_le` is true (inside an OTST
    orientation list), values are stored little-endian.
    """

    chunk_type: str = "cdat"

    values: list[float] = Factory(list)
    is_le: bool = False
    pad: bytes = b""
    """Trailing bytes after the values: empty, or 4 zero bytes for the empty
    cdat AE writes in a text-document `tdbs`. Settable at construction."""

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        is_le: bool = False,
        **kwargs: Any,
    ) -> CdatChunk:
        count = size // 8
        if count == 0:
            pad = read_bytes(fp, size) if size > 0 else b""
            return cls(chunk_type=chunk_type, is_le=is_le, pad=pad)
        fmt = "<" if is_le else ">"
        fmt += f"{count}d"
        raw = read_bytes(fp, count * 8)
        vals = list(struct.unpack(fmt, raw))
        rest = size - count * 8
        pad = read_bytes(fp, rest) if rest > 0 else b""
        return cls(chunk_type=chunk_type, values=vals, is_le=is_le, pad=pad)

    def write(self, fp: IO[bytes]) -> int:
        written = 0
        if self.values:
            count = len(self.values)
            fmt = "<" if self.is_le else ">"
            fmt += f"{count}d"
            raw = struct.pack(fmt, *self.values)
            written += write_bytes(fp, raw)
        if self.pad:
            written += write_bytes(fp, self.pad)
        return written


# ---------------------------------------------------------------------------
# tdum / tduM - property min/max value (variable, context-dependent)
# ---------------------------------------------------------------------------


@register("tdum", "tduM")
@define
class TdumChunk(Chunk):
    """Property min/max value chunk.

    Layout depends on sibling tdb4 flags:
    - color: 4 x f4 (big-endian floats)
    - integer with a 4-byte body: 1 x u4 (big-endian uint32)
    - otherwise: N x f8 (big-endian doubles, N = size / 8). After Effects
      writes integer-flagged bounds as doubles too: every one of the 47652
      in the sample corpus is 8 bytes.
    """

    values: list[float] = Factory(list)
    """Stored values (floats for color/scalar, int cast to float for integer)."""

    is_color: bool = False
    is_integer: bool = False

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        is_color: bool = False,
        is_integer: bool = False,
        **kwargs: Any,
    ) -> TdumChunk:
        raw = read_bytes(fp, size)
        if is_color:
            vals = list(struct.unpack(">4f", raw[:16]))
            trailing = raw[16:]
        elif is_integer and size < 8:
            (v,) = struct.unpack(">I", raw[:4])
            vals = [float(v)]
            trailing = raw[4:]
        else:
            # Read as a u4, a double's high word turned 100.0 into 1079574528.
            is_integer = False
            count = size // 8
            vals = list(struct.unpack(f">{count}d", raw[: count * 8]))
            trailing = raw[count * 8 :]
        instance = cls(
            chunk_type=chunk_type,
            values=vals,
            is_color=is_color,
            is_integer=is_integer,
        )
        if trailing:
            object.__setattr__(instance, "_trailing", trailing)
        return instance

    def write(self, fp: IO[bytes]) -> int:
        if self.is_color:
            raw = struct.pack(">4f", *self.values)
        elif self.is_integer:
            raw = struct.pack(">I", int(self.values[0]))
        else:
            raw = struct.pack(f">{len(self.values)}d", *self.values)
        written = write_bytes(fp, raw)
        if self._trailing:
            written += write_bytes(fp, self._trailing)
        return written


# ---------------------------------------------------------------------------
# otda - orientation keyframe data (N big-endian doubles)
# ---------------------------------------------------------------------------


@register("otda")
@define
class OtdaChunk(Chunk):
    """Orientation keyframe data: N big-endian doubles (typically 3 for XYZ)."""

    chunk_type: str = "otda"
    values: list[float] = Factory(list)

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> OtdaChunk:
        raw = read_bytes(fp, size)
        n = size // 8
        vals = list(struct.unpack(f">{n}d", raw[: n * 8]))
        trailing = raw[n * 8 :]
        instance = cls(chunk_type=chunk_type, values=vals)
        if trailing:
            object.__setattr__(instance, "_trailing", trailing)
        return instance

    def write(self, fp: IO[bytes]) -> int:
        raw = struct.pack(f">{len(self.values)}d", *self.values)
        written = write_bytes(fp, raw)
        if self._trailing:
            written += write_bytes(fp, self._trailing)
        return written


# ---------------------------------------------------------------------------
# tdmn - match name (40 bytes, null-padded)
# ---------------------------------------------------------------------------


@register("tdmn")
@define
class TdmnChunk(_StringChunkBase):
    """Fixed-width 40-byte null-padded match name chunk."""

    chunk_type: str = "tdmn"
    _ENCODING = "UTF-8"

    @classmethod
    def read(
        cls, fp: IO[bytes], size: int, *, chunk_type: str = "", **kw: Any
    ) -> TdmnChunk:
        raw = read_bytes(fp, size)
        return cls(chunk_type=chunk_type, value=raw.rstrip(b"\x00").decode("UTF-8"))

    def write(self, fp: IO[bytes]) -> int:
        encoded = self.value.encode("UTF-8")[:40]
        padded = encoded.ljust(40, b"\x00")
        return write_bytes(fp, padded)


# Sentinel AE writes as the tdsn display name for unnamed properties;
# the name then resolves from the auto-name.
TDSN_SENTINEL = "-_0_/-"

_TdsnT = TypeVar("_TdsnT", bound="TdsnChunk")


@register("tdsn")
@define
class TdsnChunk(ContainerChunk):
    """Display-name container (`tdsn`) wrapping a single `Utf8` child.

    AE writes the `-_0_/-` sentinel for unnamed properties; the display
    name then resolves from the match name.
    """

    chunk_type: str = "tdsn"

    @classmethod
    def new(cls: type[_TdsnT], name: str = "", *, synthetic: bool = False) -> _TdsnT:
        """Build a tdsn wrapping `name`."""
        return cls(
            chunks=[Utf8Chunk(value=name, synthetic=synthetic)],
            synthetic=synthetic,
        )

    @property
    def utf8(self) -> Utf8Chunk:
        """The `Utf8` child holding the display name.

        Raises:
            ChunkNotFoundError: If the tdsn has no Utf8 child, so callers
                can degrade to the auto-name like any missing chunk.
        """
        chunk = find_by_type(chunks=self.chunks, chunk_type="Utf8")
        assert isinstance(chunk, Utf8Chunk)
        return chunk


@register("vfdn")
@define
class VfdnChunk(TdsnChunk):
    """Variable-font axis display-name container (`vfdn`) wrapping a
    single `Utf8` child (e.g. `Font Axis Weight`).

    AE 26+ writes one after each active `ADBE Text VF Axis` slot's tdbs
    inside a text animator's Properties group; the name comes from the
    font's own axis name table. Structurally a `tdsn`; a missing Utf8
    child degrades to the tag-derived name.
    """

    chunk_type: str = "vfdn"
