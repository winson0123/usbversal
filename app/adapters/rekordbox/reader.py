"""Rekordbox read adapter using the rbox library for One Library exports."""

from __future__ import annotations

from pathlib import Path

import structlog
from rbox import OneLibrary
from rbox.enums import PlaylistType

from app.adapters.base import (
    DatabaseNotFoundError,
    RekordboxReadAdapter,
    UnsupportedDatabaseError,
)
from app.adapters.rekordbox.paths import resolve_rekordbox_database
from app.core.domain import Playlist, RekordboxDbFormat, RekordboxLibrary

logger = structlog.get_logger(__name__)


class RboxOneLibraryAdapter(RekordboxReadAdapter):
    """Read Rekordbox One Library (exportLibrary.db) via rbox."""

    def __init__(self, library: RekordboxLibrary, db: OneLibrary) -> None:
        """
        Initialize adapter with an opened rbox database.

        Args:
            library: Resolved library metadata.
            db: Open OneLibrary instance from rbox.
        """
        self._library = library
        self._db = db

    @property
    def library(self) -> RekordboxLibrary:
        """Return library metadata."""
        return self._library

    @property
    def database(self) -> OneLibrary:
        """Return the underlying rbox OneLibrary handle."""
        return self._db

    def list_playlists(self) -> list[Playlist]:
        """
        List playlists and folders from exportLibrary.db.

        Returns:
            Playlist domain objects mapped from rbox rows.
        """
        result: list[Playlist] = []
        for row in self._db.get_playlists():
            is_folder = row.attribute == PlaylistType.Folder
            track_count = None
            if not is_folder and hasattr(row, "items"):
                try:
                    track_count = len(row.items)
                except (TypeError, AttributeError):
                    track_count = None
            raw_parent = int(row.parent_id) if row.parent_id is not None else 0
            parent_id = None if raw_parent == 0 else raw_parent
            result.append(
                Playlist(
                    id=int(row.id),
                    name=str(row.name),
                    parent_id=parent_id,
                    is_folder=is_folder,
                    track_count=track_count,
                ),
            )
        logger.info(
            "rekordbox_playlists_loaded",
            database=str(self._library.database_path),
            count=len(result),
        )
        return result

    def get_playlist_track_paths(self, playlist_id: int) -> list[str]:
        """
        Return ordered Rekordbox content paths for a playlist.

        Args:
            playlist_id: Rekordbox playlist id (non-folder).

        Returns:
            List of content.path values in playlist order.

        Raises:
            ValueError: If playlist_id does not exist or is a folder.
        """
        playlist = self._db.get_playlist_by_id(playlist_id)
        if playlist is None:
            raise ValueError(f"Playlist not found: {playlist_id}")
        if playlist.attribute == PlaylistType.Folder:
            raise ValueError(f"Playlist {playlist_id} is a folder, not a track list")
        contents = self._db.get_playlist_contents(playlist_id)
        paths: list[str] = []
        for row in contents:
            path = getattr(row, "path", None)
            if path:
                paths.append(str(path))
        logger.info(
            "rekordbox_playlist_paths_loaded",
            playlist_id=playlist_id,
            track_count=len(paths),
        )
        return paths


def open_rekordbox_library(mount_path: Path) -> RekordboxReadAdapter:
    """
    Open a Rekordbox library on a mount for read-only access.

    Args:
        mount_path: Mount root containing PIONEER/rekordbox exports.

    Returns:
        Configured RekordboxReadAdapter instance.

    Raises:
        DatabaseNotFoundError: No Rekordbox database file under the mount.
        UnsupportedDatabaseError: Only unsupported formats are present.
    """
    resolved = resolve_rekordbox_database(mount_path)
    if resolved is None:
        raise DatabaseNotFoundError(
            f"No Rekordbox database under {mount_path} "
            "(expected PIONEER/rekordbox/exportLibrary.db or export.pdb)"
        )

    db_path, db_format = resolved
    library = RekordboxLibrary(
        mount_path=mount_path.resolve(),
        database_path=db_path,
        db_format=db_format,
    )

    if db_format == RekordboxDbFormat.ONE_LIBRARY:
        logger.info("opening_rekordbox_one_library", path=str(db_path))
        return RboxOneLibraryAdapter(library, OneLibrary(str(db_path)))

    raise UnsupportedDatabaseError(
        "Classic export.pdb (DeviceSQL) is not supported. "
        "Rekordbox One Library (exportLibrary.db) is required; re-export the USB "
        "for OPUS-QUAD / XDJ-AZ / OMNIS-DUO class devices."
    )
