from __future__ import annotations

from typing import TYPE_CHECKING

from py_aep.enums import Label

from ...binary.misc_chunks import NmhdChunk
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import index_by_identity
from ..descriptors import ChunkField
from ..validators import (
    validate_int,
    validate_marker_duration,
    validate_string,
    validate_u4,
)

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from .keyframe import Keyframe


def _validate_params(value: dict[str, str]) -> None:
    if not isinstance(value, dict):
        raise ValueError("params must be a dictionary of string key-value pairs")
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, str):
            raise ValueError("params must be a dictionary of string key-value pairs")


class MarkerValue:
    """
    The `MarkerValue` object represents a layer or composition marker, which
    associates a comment, and optionally a chapter reference point, Web-page
    link, or Flash Video cue point with a particular point in a layer.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        marker = comp.markers[0]
        print(marker.comment)
        ```

    See: https://ae-scripting.docsforadobe.dev/other/markervalue/
    """

    frame_duration = ChunkField[int](
        "_nmhd",
        "frame_duration",
        validate=validate_u4,
    )
    """The marker's duration, in frames. Read / Write."""

    duration = ChunkField[float](
        "_nmhd",
        "duration_seconds",
        validate=validate_marker_duration,
    )
    """The marker's duration, in seconds. Read / Write."""

    label = ChunkField.enum(Label, "_nmhd", "label")
    """
    The label color. Colors are represented by their number (0 for None, or 1
    to 16 for one of the preset colors in the Labels preferences).
    Read / Write.
    """

    navigation = ChunkField.bool(
        "_nmhd",
        "navigation",
    )
    """Whether the marker is a navigation marker. Read / Write."""

    protected_region = ChunkField.bool(
        "_nmhd",
        "protected_region",
    )
    """
    State of the Protected Region option in the Composition Marker dialog box.
    When `True`, the composition marker behaves as a protected region. Will
    also return `True` for protected region markers on nested composition
    layers, but is otherwise not applicable to layer markers. Read / Write.
    """

    comment = ChunkField[str]("_comment_utf8", "value")
    """
    A text comment for this marker. This comment appears in the Timeline panel
    next to the layer marker. Read / Write.
    """

    chapter = ChunkField[str]("_chapter_utf8", "value")
    """
    A text chapter link for this marker. Chapter links initiate a jump to a
    chapter in a QuickTime movie or in other formats that support chapter
    marks. Read / Write.
    """

    url = ChunkField[str]("_url_utf8", "value")
    """A URL for this marker. This URL is an automatic link to a Web page. Read / Write."""

    frame_target = ChunkField[str]("_frame_target_utf8", "value")
    """
    A text frame target for this marker. Together with the URL value, this
    targets a specific frame within a Web page. Read / Write.
    """

    cue_point_name = ChunkField[str]("_cue_point_name_utf8", "value")
    """The Flash Video cue point name, as shown in the Marker dialog box. Read / Write."""

    def __init__(
        self,
        comment: str = "",
        chapter: str = "",
        url: str = "",
        frame_target: str = "",
        cue_point_name: str = "",
        params: dict[str, str] | None = None,
    ) -> None:
        for arg in (comment, chapter, url, frame_target, cue_point_name):
            validate_string(arg)
        if params is not None:
            _validate_params(params)
        self._nmhd = NmhdChunk()
        self._comment_utf8 = Utf8Chunk(value=comment)
        self._chapter_utf8 = Utf8Chunk(value=chapter)
        self._url_utf8 = Utf8Chunk(value=url)
        self._frame_target_utf8 = Utf8Chunk(value=frame_target)
        self._cue_point_name_utf8 = Utf8Chunk(value=cue_point_name)
        self._keyframe: Keyframe | None = None
        self._nmrd: ListChunk | None = None
        self._frame_time = 0
        self._param_utf8s: list[Utf8Chunk] = []
        if params:
            for key, val in params.items():
                self._param_utf8s.append(Utf8Chunk(value=key))
                self._param_utf8s.append(Utf8Chunk(value=val))
            self._nmhd.num_params = len(params)

    @classmethod
    def _from_binary(
        cls,
        *,
        _nmhd: NmhdChunk,
        _comment_utf8: Utf8Chunk,
        _chapter_utf8: Utf8Chunk,
        _url_utf8: Utf8Chunk,
        _frame_target_utf8: Utf8Chunk,
        _cue_point_name_utf8: Utf8Chunk,
        _keyframe: Keyframe | None = None,
        frame_time: int = 0,
        _param_utf8s: list[Utf8Chunk] | None = None,
        _nmrd: ListChunk | None = None,
    ) -> MarkerValue:
        """Wrap parsed marker chunks as a `MarkerValue`."""
        obj = cls.__new__(cls)
        obj._nmhd = _nmhd
        obj._comment_utf8 = _comment_utf8
        obj._chapter_utf8 = _chapter_utf8
        obj._url_utf8 = _url_utf8
        obj._frame_target_utf8 = _frame_target_utf8
        obj._cue_point_name_utf8 = _cue_point_name_utf8
        obj._keyframe = _keyframe
        obj._nmrd = _nmrd
        obj._frame_time = frame_time
        obj._param_utf8s = _param_utf8s or []
        return obj

    @property
    def params(self) -> dict[str, str]:
        """Key-value pairs for Flash Video cue-point parameters. Read / Write."""
        result: dict[str, str] = {}
        for i in range(0, len(self._param_utf8s) - 1, 2):
            key = self._param_utf8s[i].value
            val = self._param_utf8s[i + 1].value
            result[key] = val
        return result

    @params.setter
    def params(self, value: dict[str, str]) -> None:
        _validate_params(value)
        old = self._param_utf8s
        new: list[Utf8Chunk] = []
        for i, (key, val) in enumerate(value.items()):
            if 2 * i + 1 < len(old):
                # Reuse existing chunk pairs in place (keeps tree position).
                old[2 * i].value = key
                old[2 * i + 1].value = val
                new.extend((old[2 * i], old[2 * i + 1]))
            else:
                new.extend((Utf8Chunk(value=key), Utf8Chunk(value=val)))
        removed = old[len(new) :]
        added = new[len(old) :]
        if self._nmrd is not None and (removed or added):
            # Splice grown / shrunk pairs into the backing Nmrd list.
            chunks = self._nmrd.chunks
            for chunk in removed:
                try:
                    del chunks[index_by_identity(chunks, chunk)]
                except ValueError:
                    pass
            if added:
                kept = new[: len(new) - len(added)]
                anchor = kept[-1] if kept else self._cue_point_name_utf8
                try:
                    pos = index_by_identity(chunks, anchor)
                except ValueError:
                    pos = len(chunks) - 1
                chunks[pos + 1 : pos + 1] = added
        self._param_utf8s = new
        self._nmhd.num_params = len(value)

    @property
    def frame_time(self) -> int:
        """The time of the marker, in frames."""
        if self._keyframe is not None:
            return self._keyframe.frame_time
        return self._frame_time

    @frame_time.setter
    def frame_time(self, value: int) -> None:
        validate_int(value)
        if self._keyframe is not None:
            self._keyframe.frame_time = value
        else:
            self._frame_time = value

    @property
    def event_cue_point(self) -> bool:
        """
        When `True`, the FlashVideo cue point is for an event; otherwise, it is
        for navigation.
        """
        return not self.navigation
