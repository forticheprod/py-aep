from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .descriptors import ChunkField, ComputedField

if TYPE_CHECKING:
    from ..binary.item_chunks import HeadChunk
    from .project import Project
    from .viewer.viewer import Viewer

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)x(\d+)$")


def _reverse_version(value: str, body: HeadChunk) -> dict[str, int]:
    """Parse `"major.minorxbuild"` back into Chunk fields."""
    m = _VERSION_RE.match(value)
    if not m:
        msg = (
            f"version must match '{{major}}.{{minor}}x{{build}}' "
            f"(e.g. '25.6x101'), got {value!r}"
        )
        raise ValueError(msg)
    major, minor, build = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return {
        "ae_version_major_a": major // 8,
        "ae_version_major_b": major % 8,
        "ae_version_minor": minor,
        "ae_build_number": build,
    }


def _compute_version(body: HeadChunk) -> str:
    """Format the AE version as `{major}.{minor}x{build}`."""
    major = body.ae_version_major_a * 8 + body.ae_version_major_b
    return f"{major}.{body.ae_version_minor}x{body.ae_build_number}"


class Application:
    """
    The `Application` object represents the After Effects application. Attributes
    provide access to the project and application-level settings parsed from
    the binary file.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        print(app.version)
        ```

    See: https://ae-scripting.docsforadobe.dev/general/application/
    """

    build_number = ChunkField[str](
        "_head",
        "ae_build_number",
        reverse=int,
    )
    """The build number of After Effects that last saved the project.
    Read / Write.

    Warning:
        This attribute is read-only in ExtendScript. Modifying it could
        cause issues when opening the file in After Effects.
    """

    version = ComputedField[str](
        "_head",
        compute=_compute_version,
        reverse=_reverse_version,
    )
    """The version of After Effects that last saved the project, formatted as
    "{major}.{minor}x{build}" (e.g., "25.6x101"). Read / Write.

    Warning:
        This attribute is read-only in ExtendScript. Modifying it could
        cause issues when opening the file in After Effects.
    """

    is_beta = ChunkField[bool]("_head", "ae_version_beta_flag")
    """Indicates whether the After Effects version is a beta version. Read / Write.

    Warning:
        This attribute is read-only in ExtendScript. Modifying it could
        cause issues when opening the file in After Effects.
    """

    app_name: str = "After Effects"
    """The name of the application. Always "After Effects". Read-only."""

    def __init__(
        self,
        *,
        _head: HeadChunk,
        project: Project,
        active_viewer: Viewer | None = None,
    ) -> None:
        self._head = _head
        self._project = project
        self._active_viewer = active_viewer

    def __repr__(self) -> str:
        return f"Application(version={self.version!r}, build_number={self.build_number!r}, app_name={self.app_name!r})"

    @property
    def project(self) -> Project:
        """The project that is currently loaded. Read-only."""
        return self._project

    @property
    def active_viewer(self) -> Viewer | None:
        """The Viewer object for the currently focused or active-focused viewer
        (Composition, Layer, or Footage) panel. Returns `None` if no viewers
        are open. Read-only."""
        return self._active_viewer

    @property
    def build_name(self) -> str:
        """A string indicating the version and build of After Effects, formatted
        as "{major}.{minor}x{build}" (e.g., "25.6x101"). Read / Write.

        Alias for [version][py_aep.models.application.Application.version].

        Warning:
            This attribute is read-only in ExtendScript. Modifying it could
            cause issues when opening the file in After Effects.
        """
        return self.version

    @build_name.setter
    def build_name(self, value: str) -> None:
        self.version = value
