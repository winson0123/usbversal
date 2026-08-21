"""Domain models for library discovery and metadata reads."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class LibraryType(StrEnum):
    """Detected DJ library vendor type."""

    REKORDBOX = "rekordbox"
    SERATO = "serato"


class RekordboxDbFormat(StrEnum):
    """Rekordbox on-disk database format."""

    ONE_LIBRARY = "exportLibrary.db"
    DEVICE_SQL = "export.pdb"


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


@dataclass(frozen=True)
class Playlist:
    """
    A playlist or folder node in a DJ library hierarchy.

    Attributes:
        id: Vendor-specific playlist identifier.
        name: Display name.
        parent_id: Parent playlist/folder id, or None for root children.
        is_folder: True when the node is a folder, not a leaf playlist.
        track_count: Number of tracks when known (read-only listing may omit).
    """

    id: int
    name: str
    parent_id: int | None
    is_folder: bool
    track_count: int | None = None


@dataclass(frozen=True)
class RekordboxLibrary:
    """
    Resolved Rekordbox library opened for read-only access.

    Attributes:
        mount_path: USB or directory root used for resolution.
        database_path: Path to the opened database file.
        db_format: Detected Rekordbox database format.
    """

    mount_path: Path
    database_path: Path
    db_format: RekordboxDbFormat


@dataclass(frozen=True)
class SeratoCrate:
    """
    A Serato crate (playlist) file under Subcrates/.

    Attributes:
        name: Crate display name (typically the .crate filename stem).
        path: Absolute path to the .crate file.
        track_count: Number of track path entries in the crate.
    """

    name: str
    path: Path
    track_count: int


@dataclass(frozen=True)
class SeratoLibrary:
    """
    Resolved Serato library on a mount (read-only).

    Attributes:
        mount_path: USB or directory root.
        serato_root: Path to _Serato_ directory.
        database_path: Path to database V2 file.
        database_track_count: Tracks indexed in database V2.
    """

    mount_path: Path
    serato_root: Path
    database_path: Path
    database_track_count: int
