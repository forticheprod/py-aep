from __future__ import annotations

import typing

from py_aep.enums import Label

from ...kaitai.descriptors import ChunkField
from ..validators import validate_number

if typing.TYPE_CHECKING:
    from ...kaitai import Aep
    from .keyframe import Keyframe


def _reverse_duration(value: float, body: Aep.NmhdBody) -> dict[str, int]:
    """Convert duration in seconds to frame_duration in 600ths."""
    return {"frame_duration": round(value * 600)}


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
        validate=validate_number(min=0, integer=True),
    )
    """The marker's duration, in frames. Read / Write."""

    duration = ChunkField[float](
        "_nmhd",
        "duration",
        reverse_instance_field=_reverse_duration,
    )
    """The marker's duration, in seconds. Read / Write."""

    label = ChunkField.enum(Label, "_nmhd", "label")
    """
    The label color. Colors are represented by their number (0 for None, or 1
    to 16 for one of the preset colors in the Labels preferences).
    Read / Write.
    """

    navigation = ChunkField.bool("_nmhd", "navigation")
    """Whether the marker is a navigation marker. Read / Write."""

    protected_region = ChunkField.bool("_nmhd", "protected_region")
    """
    State of the Protected Region option in the Composition Marker dialog box.
    When `True`, the composition marker behaves as a protected region. Will
    also return `True` for protected region markers on nested composition
    layers, but is otherwise not applicable to layer markers. Read / Write.
    """

    comment = ChunkField[str]("_comment_utf8", "contents")
    """
    A text comment for this marker. This comment appears in the Timeline panel
    next to the layer marker. Read / Write.
    """

    chapter = ChunkField[str]("_chapter_utf8", "contents")
    """
    A text chapter link for this marker. Chapter links initiate a jump to a
    chapter in a QuickTime movie or in other formats that support chapter
    marks. Read / Write.
    """

    url = ChunkField[str]("_url_utf8", "contents")
    """A URL for this marker. This URL is an automatic link to a Web page. Read / Write."""

    frame_target = ChunkField[str]("_frame_target_utf8", "contents")
    """
    A text frame target for this marker. Together with the URL value, this
    targets a specific frame within a Web page. Read / Write.
    """

    cue_point_name = ChunkField[str]("_cue_point_name_utf8", "contents")
    """The Flash Video cue point name, as shown in the Marker dialog box. Read / Write."""

    def __init__(
        self,
        *,
        _nmhd: Aep.NmhdBody,
        _comment_utf8: Aep.Utf8Body,
        _chapter_utf8: Aep.Utf8Body,
        _url_utf8: Aep.Utf8Body,
        _frame_target_utf8: Aep.Utf8Body,
        _cue_point_name_utf8: Aep.Utf8Body,
        _keyframe: Keyframe | None = None,
        frame_time: int = 0,
        _param_utf8s: list[Aep.Utf8Body] | None = None,
    ) -> None:
        self._nmhd = _nmhd
        self._comment_utf8 = _comment_utf8
        self._chapter_utf8 = _chapter_utf8
        self._url_utf8 = _url_utf8
        self._frame_target_utf8 = _frame_target_utf8
        self._cue_point_name_utf8 = _cue_point_name_utf8
        self._keyframe = _keyframe

        self._frame_time = frame_time

        self._param_utf8s = _param_utf8s or []

    @property
    def params(self) -> dict[str, str]:
        """Key-value pairs for Flash Video cue-point parameters."""
        result: dict[str, str] = {}
        for i in range(0, len(self._param_utf8s) - 1, 2):
            key = self._param_utf8s[i].contents.split("\x00")[0]
            val = self._param_utf8s[i + 1].contents.split("\x00")[0]
            result[key] = val
        return result

    @params.setter
    def params(self, value: dict[str, str]) -> None:
        bodies = self._param_utf8s
        idx = 0
        for key, val in value.items():
            if idx + 1 < len(bodies):
                bodies[idx].contents = key
                bodies[idx + 1].contents = val
            idx += 2

    @property
    def frame_time(self) -> int:
        """The time of the marker, in frames."""
        if self._keyframe is not None:
            return self._keyframe.frame_time
        return self._frame_time

    @frame_time.setter
    def frame_time(self, value: int) -> None:
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
