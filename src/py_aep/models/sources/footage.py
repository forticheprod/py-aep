from __future__ import annotations

from typing import TYPE_CHECKING, List, cast

from ...binary.utils import (
    ChunkNotFoundError,
    find_by_type,
    find_chunks_after,
    toggle_flag_chunk,
)
from ...color.envelope import (
    PROFILE_TYPE_OCIO,
    build_icc_envelope,
    parse_envelope,
)
from ...color.icc import default_icc_library
from ...color.ocio import ocio_color_profile_envelope, require_ocio_config
from ...enums import (
    AlphaMode,
    FieldSeparationType,
    LinearLightMode,
    PulldownPhase,
)
from ...enums.mappings import map_media_color_space, profile_id_for_name
from ..descriptors import ChunkField
from ..validators import (
    _validate_number,
    validate_bool,
    validate_rgb_color,
    validate_string,
)

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import SspcChunk
    from ...binary.scalar_chunks import U1Chunk, Utf8Chunk
    from ...color.envelope import ColorProfile
    from ...color.icc import IccProfileLibrary
    from ..project import Project


class FootageSource:
    """
    The `FootageSource` object holds information describing the source of some
    footage. It is used as the `main_source` of a `FootageItem` object, or the
    `proxy_source` of a `CompItem` object or `FootageItem`.

    See: https://ae-scripting.docsforadobe.dev/sources/footagesource/
    """

    alpha_mode = ChunkField.enum(
        AlphaMode,
        "_sspc",
        "alpha_mode_raw",
    )
    """Defines how the alpha information in the footage is interpreted.
    If `has_alpha` is `False`, this attribute has no relevant meaning.
    Read / Write."""

    field_separation_type = ChunkField.enum(
        FieldSeparationType,
        "_sspc",
        "field_separation_type",
    )
    """How the fields are to be separated in non-still footage.
    Read / Write."""

    has_alpha = ChunkField[bool]("_sspc", "has_alpha", read_only=True)
    """When `True`, the footage has an alpha component. In this case, the
    attributes `alpha_mode`, `invert_alpha`, and `premultiplied` have valid
    values. When `False`, those attributes have no relevant meaning for the
    footage. Read-only."""

    high_quality_field_separation = ChunkField.bool(
        "_sspc",
        "high_quality_field_separation",
        transform=lambda v: v % 2 != 0,
        reverse=int,
    )
    """When `True`, After Effects uses special algorithms to determine how to
    perform high-quality field separation. Read / Write."""

    invert_alpha = ChunkField.bool(
        "_sspc",
        "invert_alpha",
    )
    """When `True`, an alpha channel in a footage clip or proxy should be
    inverted. This attribute is valid only if an alpha is present. If
    `has_alpha` is `False`, or if `alpha_mode` is
    [AlphaMode.IGNORE][py_aep.enums.AlphaMode], this attribute is
    ignored. Read / Write."""

    loop = ChunkField[int](
        "_sspc",
        "loop",
        validate=_validate_number(min=1, max=9999, integer=True),
    )
    """The number of times that the footage is to be played consecutively
    when used in a composition. Read / Write."""

    premul_color = ChunkField[List[float]](
        "_sspc",
        "premul_color",
        validate=validate_rgb_color,
    )
    """The color to be premultiplied. This attribute is valid only if
    the `alpha_mode` is
    [AlphaMode.PREMULTIPLIED][py_aep.enums.AlphaMode].
    Read / Write."""

    interpret_as_linear_light = ChunkField.enum(
        LinearLightMode,
        "_linl",
        "value",
        default=LinearLightMode.OFF,
    )
    """The Interpret As Linear Light setting from the Interpret Footage >
    Color Management tab. Read / Write.

    Note:
        Not exposed in ExtendScript."""

    conform_frame_rate = ChunkField[float](
        "_sspc",
        "conform_frame_rate",
        validate=_validate_number(min=0.0, max=999.0),
    )
    """A frame rate to use instead of the `native_frame_rate` value. If
    set to 0, the `native_frame_rate` is used instead. Read / Write."""

    display_frame_rate = ChunkField[float](
        "_sspc",
        "display_frame_rate",
        read_only=True,
    )
    """The effective frame rate as displayed and rendered in compositions.
    If `remove_pulldown` is active, the rate is multiplied by 0.8.
    Read-only."""

    remove_pulldown = ChunkField.enum(
        PulldownPhase,
        "_sspc",
        "remove_pulldown",
        post_set="_on_remove_pulldown_set",
    )
    """Controls which pulldown phase to remove from the source footage.
    [PulldownPhase.OFF][py_aep.enums.PulldownPhase] by default.
    Read / Write."""

    def _on_remove_pulldown_set(self) -> None:
        """Co-set a field order when a 3:2 pulldown phase is applied.

        AE requires field separation to be set whenever a standard 3:2
        pulldown phase (binary 1-5) is removed; a file with such a phase but
        no field order is rejected ("field order must be set before 3:2
        pulldown can be removed"). The 24P-advance phases (binary 6-10) are
        exempt. Mirror AE's Interpret Footage dialog, which forces a field
        order and defaults to Upper Field First.
        """
        if (
            1 <= self._sspc.remove_pulldown <= 5
            and self.field_separation_type == FieldSeparationType.OFF
        ):
            self.field_separation_type = FieldSeparationType.UPPER_FIELD_FIRST

    native_frame_rate = ChunkField[float]("_sspc", "native_frame_rate", read_only=True)
    """The native frame rate of the footage. Read-only."""

    _width = ChunkField[int]("_sspc", "width", read_only=True)
    _height = ChunkField[int]("_sspc", "height", read_only=True)
    _pixel_aspect = ChunkField[float]("_sspc", "pixel_aspect", read_only=True)
    _footage_missing = ChunkField[bool](
        "_sspc",
        "footage_missing_at_save",
        read_only=True,
    )
    _start_frame = ChunkField[int]("_sspc", "start_frame", read_only=True)
    _end_frame = ChunkField[int]("_sspc", "end_frame", read_only=True)

    @property
    def _has_audio(self) -> bool:
        return self._sspc.audio_sample_rate > 0

    @property
    def _duration(self) -> float:
        """Total duration in seconds (with conform and loop)."""
        sspc = self._sspc
        source_duration = sspc.duration
        conform = sspc.conform_frame_rate
        if conform != 0:
            conform_factor = sspc.native_frame_rate / conform
        else:
            conform_factor = 1.0
        return source_duration * conform_factor * sspc.loop

    @property
    def _frame_duration(self) -> int:
        return int(self._duration * self.display_frame_rate)

    def __init__(
        self,
        *,
        _sspc: SspcChunk,
        _linl: U1Chunk | None = None,
        _clrs: ListChunk | None = None,
    ) -> None:
        self._sspc = _sspc
        self._linl = _linl
        self._clrs = _clrs
        self._project: Project | None = None

    def _icc_lib(self) -> IccProfileLibrary:
        """ICC library for Adobe-CMS profile writes - the owning project's
        (honouring `icc_profile_dirs`) when wired, else the global default."""
        if self._project is not None:
            return self._project._icc_lib()
        return default_icc_library()

    @property
    def preserve_rgb(self) -> bool:
        """When `True`, the footage Preserve RGB setting is enabled.
        From the Interpret Footage > Color Management tab. Read / Write.

        Note:
            Not exposed in ExtendScript."""
        if self._clrs is None:
            return False
        return any(c.chunk_type == "prgb" for c in self._clrs.chunks)

    @preserve_rgb.setter
    def preserve_rgb(self, value: bool) -> None:
        validate_bool(value)
        if self._clrs is None:
            raise AttributeError(
                "Cannot set preserve_rgb: no CLRS container. Update the value in After Effects then re-parse the project to modify this footage source."
            )
        toggle_flag_chunk(self._clrs, "prgb", value)

    @property
    def media_color_space(self) -> str:
        """The media color space from the Interpret Footage >
        Color Management tab. Read / Write.

        Returns `"Embedded"`, `"Working Color Space"`, the name of an assigned
        OCIO color space, or the name of an Adobe ICC profile (e.g.
        `"Apple RGB"`). As with [working_space][py_aep.models.project.Project.working_space],
        an assigned OCIO space reads back as AE's stored `colorProfileName`:
        `"<family>/<name>"` for a direct color-space pick (e.g.
        `"ACES/ACES - ACEScg"`), or the target name for a role/alias pick.

        Writable: `"Working Color Space"`, `"Embedded"`, an Adobe ICC profile
        name, or - in OCIO mode - any color space, role, alias or
        `display/view` pair of the project's OCIO configuration (the
        `"<family>/<name>"` form this getter returns is accepted too). The
        config must be resolvable, since the envelope AE writes depends on
        which kind the name is. An Adobe profile is identified by its 16-byte
        ID and its ICC bytes are discovered on disk
        (`ColorProfileNotFoundError` if not installed).

        Note:
            Assigning back what this getter returns is lossy for a ROLE pick.
            AE stores the role's TARGET, not the role, and many roles can
            share one target (ACES 1.2 points `rendering`, `scene_linear` and
            `compositing_linear` all at `ACES - ACEScg`), so which role was
            chosen is not recoverable from the file. Re-assigning the target
            name records a direct color-space pick instead - the same color
            transform, different bytes. Pass the role name (e.g.
            `"matte_paint"`) to write a role pick.

        Note:
            Not exposed in ExtendScript."""
        if self._clrs is None:
            return "Embedded"
        ipws_chunk = cast(
            "U1Chunk", find_by_type(chunks=self._clrs.chunks, chunk_type="ipws")
        )
        if ipws_chunk.value:
            return "Working Color Space"
        # In OCIO mode the assigned color space is carried as an OCIO envelope in
        # the `ocsp` Utf8 (apid is the unmanaged sentinel). In Adobe mode `ocsp`
        # holds the embedded/override profile and `apid` is the discriminator.
        ocsp = self._ocsp_profile()
        if ocsp is not None and ocsp.profile_type == PROFILE_TYPE_OCIO:
            return ocsp.name
        apid_chunk = find_by_type(chunks=self._clrs.chunks, chunk_type="apid")
        return map_media_color_space(False, apid_chunk.data)

    @media_color_space.setter
    def media_color_space(self, value: str) -> None:
        validate_string(value)
        if self._clrs is None:
            raise AttributeError(
                "Cannot set media_color_space: no CLRS container. Update the "
                "value in After Effects then re-parse the project to modify "
                "this footage source."
            )
        ipws_chunk = cast(
            "U1Chunk", find_by_type(chunks=self._clrs.chunks, chunk_type="ipws")
        )
        apid_chunk = find_by_type(chunks=self._clrs.chunks, chunk_type="apid")
        if value == "Working Color Space":
            # AE sets ipws, clears the override id, and empties the ocsp Utf8.
            ipws_chunk.value = 1
            apid_chunk.data = b"\xff" * 16
            self._write_ocsp("")
            return
        ipws_chunk.value = 0
        if value == "Embedded":
            # Revert to the file's embedded profile (mirrored in the Mcsp Utf8).
            apid_chunk.data = b"\xff" * 16
            self._write_ocsp(self._embedded_envelope())
            return
        if profile_id_for_name(value) is not None:
            # Adobe ICC override: apid is the catalogued profile ID and the ocsp
            # carries the embedded ICC bytes (discovered from the standard Adobe
            # Color dirs). For most profiles the bytes hash to the same ID; the
            # handful AE generates a private variant for (Apple/Adobe RGB,
            # ColorMatch, ROMM) embed the on-disk copy AE still recognizes.
            lib = self._icc_lib()
            apid_chunk.data = lib.hash_for(value)
            self._write_ocsp(build_icc_envelope(value, lib.bytes_for(value)))
            return
        # Treat any other name as an OCIO color space (no ICC, apid unmanaged).
        # The envelope depends on the SELECTION KIND, so the config is
        # required - AE-verified against a direct-pick and a role-pick sample.
        apid_chunk.data = b"\xff" * 16
        self._write_ocsp(self._ocio_envelope(value))

    def _ocio_envelope(self, name: str) -> str:
        """Build the OCIO envelope AE writes for `name` (see
        [ocio_color_profile_envelope][py_aep.color.ocio.ocio_color_profile_envelope])."""
        project = self._project
        config = require_ocio_config(
            project.ocio_configuration_file if project is not None else None,
            f"build the color-profile envelope for {name!r}",
        )
        return ocio_color_profile_envelope(config, name)

    def _ocsp_utf8(self) -> Utf8Chunk | None:
        """The `Utf8` chunk after the CLRS `ocsp` marker (the assigned space)."""
        if self._clrs is None:
            return None
        try:
            after = find_chunks_after(
                chunks=self._clrs.chunks, chunk_type="Utf8", after_type="ocsp"
            )
        except ChunkNotFoundError:
            return None
        return cast("Utf8Chunk", after[0]) if after else None

    def _ocsp_profile(self) -> ColorProfile | None:
        utf8 = self._ocsp_utf8()
        if utf8 is None or "baseColorProfile" not in utf8.value:
            return None
        return parse_envelope(utf8.value)

    def _embedded_envelope(self) -> str:
        """The embedded source profile envelope (CLRS `Mcsp` Utf8), or `{}`."""
        if self._clrs is None:
            return "{}"
        try:
            after = find_chunks_after(
                chunks=self._clrs.chunks, chunk_type="Utf8", after_type="Mcsp"
            )
        except ChunkNotFoundError:
            return "{}"
        return cast("Utf8Chunk", after[0]).value if after else "{}"

    def _write_ocsp(self, envelope: str) -> None:
        utf8 = self._ocsp_utf8()
        if utf8 is None:
            raise AttributeError(
                "Cannot set media_color_space: no 'ocsp' color chunk in CLRS."
            )
        utf8.value = envelope

    @property
    def is_still(self) -> bool:
        """When `True` the footage is still; When `False`, it has a
        time-based component. Read-only."""
        return self._sspc.duration == 0
