"""Import options for importing files into an After Effects project."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ..enums import ImportAsType

# File extensions that can be imported as compositions (multi-layer).
_COMP_IMPORTABLE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".psd",
        ".ai",
        ".pdf",
    }
)

# File extensions that support sequence import.
_SEQUENCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".bmp",
        ".cin",
        ".dpx",
        ".exr",
        ".gif",
        ".hdr",
        ".iff",
        ".jpg",
        ".jpeg",
        ".png",
        ".psd",
        ".sgi",
        ".tga",
        ".tif",
        ".tiff",
    }
)

# Pattern to match trailing digits in a filename stem (e.g. "frame001").
_NUMBERED_RE = re.compile(r"(\d+)$")


class ImportOptions:
    """Options for importing a file into an After Effects project.

    This is a parameter container used by `Project.import_file()`. It
    validates the import settings before the actual import operation.

    Unlike most py_aep classes, `ImportOptions` has no chunk backing -
    import settings are not stored in the `.aep` binary format.

    Example:
        ```python
        from pathlib import Path
        from py_aep import ImportOptions, ImportAsType

        opts = ImportOptions(Path("footage/shot_001.png"))
        opts.sequence = True
        opts.import_as = ImportAsType.FOOTAGE
        ```

    See: https://ae-scripting.docsforadobe.dev/other/importoptions/
    """

    def __init__(self, file: str | os.PathLike[str]) -> None:
        if not isinstance(file, (str, os.PathLike)):
            raise ValueError("file must be a string or Path.")
        if not isinstance(file, Path):
            file = Path(file)
        self._file = file
        self._import_as = ImportAsType.FOOTAGE
        self._sequence = False
        self._force_alphabetical = False

    @property
    def file(self) -> Path:
        """The file to be imported. If a file is set in the constructor, you can access
        it through this attribute. Read / Write."""
        return self._file

    @file.setter
    def file(self, value: str | os.PathLike[str]) -> None:
        if not isinstance(value, (str, os.PathLike)):
            raise ValueError("file must be a string or Path.")
        self._file = Path(value)

    @property
    def import_as(self) -> ImportAsType:
        """How to import the file. Read / Write."""
        return self._import_as

    @import_as.setter
    def import_as(self, value: ImportAsType) -> None:
        if not isinstance(value, (int, ImportAsType)):
            raise ValueError("import_as must be an ImportAsType enum value.")
        self._import_as = ImportAsType(value)

    @property
    def sequence(self) -> bool:
        """When `True`, import the file as part of a numbered image
        sequence. Read / Write."""
        return self._sequence

    @sequence.setter
    def sequence(self, value: bool) -> None:
        self._sequence = bool(value)

    @property
    def force_alphabetical(self) -> bool:
        """When `True` and `sequence` is also `True`, use alphabetical
        order for sequence frame numbering. Read / Write."""
        return self._force_alphabetical

    @force_alphabetical.setter
    def force_alphabetical(self, value: bool) -> None:
        self._force_alphabetical = bool(value)

    def can_import_as(self, type: int | ImportAsType) -> bool:
        """Check whether the file can be imported as the given type.

        Args:
            type: The import type to check.

        Returns:
            `True` if the file can be imported as `type`.
        """
        type = ImportAsType(type)
        suffix = self._file.suffix.lower()

        if type == ImportAsType.FOOTAGE:
            return True

        if type == ImportAsType.PROJECT:
            return suffix in (".aep", ".aet")

        if type in (ImportAsType.COMP, ImportAsType.COMP_CROPPED_LAYERS):
            return suffix in _COMP_IMPORTABLE_EXTENSIONS

        return False

    def is_file_name_numbered(self) -> tuple[bool, int]:
        """Check whether the filename ends with a number.

        Returns:
            A tuple of `(is_numbered, first_number)` where
            `is_numbered` is `True` when the filename stem ends with
            digits and `first_number` is the parsed integer value (or
            `0` when not numbered).
        """
        stem = self._file.stem
        m = _NUMBERED_RE.search(stem)
        if m is not None:
            return True, int(m.group(1))
        return False, 0

    def __repr__(self) -> str:
        return (
            f"ImportOptions(file={self._file!r}, import_as={self._import_as.name}, "
            f"sequence={self._sequence})"
        )
