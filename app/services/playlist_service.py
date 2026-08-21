"""Playlist listing orchestration."""

from dataclasses import dataclass
from typing import Any

import structlog

from app.core.domain import Playlist, RekordboxLibrary
from app.services.library import UsbLibrary

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PlaylistListResult:
    """
    Result of a Rekordbox playlist list operation.

    Attributes:
        library: Opened library metadata.
        playlists: Flat playlist/folder list.
    """

    library: RekordboxLibrary
    playlists: tuple[Playlist, ...]

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize to a JSON-friendly dictionary.

        Returns:
            Dict with library info and playlist entries.
        """
        return {
            "library": {
                "mount_path": str(self.library.mount_path),
                "database_path": str(self.library.database_path),
                "format": self.library.db_format.value,
            },
            "playlists": [
                {
                    "id": p.id,
                    "name": p.name,
                    "parent_id": p.parent_id,
                    "is_folder": p.is_folder,
                    "track_count": p.track_count,
                }
                for p in self.playlists
            ],
            "count": len(self.playlists),
        }


def list_rekordbox_playlists(library: UsbLibrary) -> PlaylistListResult:
    """
    List Rekordbox playlists from an opened library (read-only).

    Args:
        library: Opened session handle.

    Returns:
        PlaylistListResult with library metadata and playlists.
    """
    playlists = tuple(library.rekordbox.list_playlists())
    logger.info("list_playlists_completed", count=len(playlists))
    return PlaylistListResult(library=library.rekordbox.library, playlists=playlists)
