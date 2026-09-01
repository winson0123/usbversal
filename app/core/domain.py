"""Domain models for library discovery and metadata reads."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


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
        source: Scanner identifier (linux_media, mac_volumes, windows_drive).
    """

    path: Path
    source: str


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


class SyncState(StrEnum):
    """How completely a Rekordbox playlist is mirrored into a Serato crate."""

    NOT_SYNCED = "not_synced"
    PARTIAL = "partial"
    SYNCED = "synced"


@dataclass(frozen=True)
class PlaylistSyncState:
    """
    How much of one playlist has reached its Serato crate.

    Attributes:
        playlist_id: Rekordbox playlist id.
        playlist_name: Rekordbox playlist display name.
        crate_name: Crate filename stem the playlist maps to.
        total: Tracks in the Rekordbox playlist.
        in_crate: Playlist tracks already present in the crate.
        complete: Playlist tracks that are green: in the crate, and
            analysis is on the file or Rekordbox had nothing to port.
        syncable: Playlist tracks Serato can index today.
    """

    playlist_id: int
    playlist_name: str
    crate_name: str
    total: int
    in_crate: int
    complete: int
    syncable: int

    @property
    def state(self) -> SyncState:
        """Traffic-light state: green only counts as finished."""
        if self.total == 0 or self.complete >= self.total:
            return SyncState.SYNCED
        if self.complete == 0 and self.in_crate == 0:
            return SyncState.NOT_SYNCED
        return SyncState.PARTIAL

    @property
    def blocked(self) -> int:
        """Tracks that cannot be synced because Serato has no record of them."""
        return self.total - self.syncable


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
