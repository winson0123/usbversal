"""Domain models for library discovery."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class LibraryType(StrEnum):
    """Detected DJ library vendor type."""

    REKORDBOX = "rekordbox"
    SERATO = "serato"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MountPoint:
    """
    A normalized mount path discovered on the system.

    Attributes:
        path: Resolved absolute path to the mount root.
        source: Scanner identifier (e.g. linux_mnt, windows_drive).
    """

    path: Path
    source: str


@dataclass(frozen=True)
class LibraryLocation:
    """
    A detected DJ library on a mount.

    Attributes:
        path: Root path of the detected library or key database file.
        library_type: rekordbox, serato, or unknown.
        confidence: Heuristic score in [0.0, 1.0].
        mount_path: Mount under which the library was found.
        indicators: Human-readable markers that triggered detection.
    """

    path: Path
    library_type: LibraryType
    confidence: float
    mount_path: Path
    indicators: tuple[str, ...]
