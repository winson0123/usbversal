"""Playlist sync state: how much of each Rekordbox playlist reached Serato."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from app.adapters.serato import (
    crate_name_for,
    read_crate_track_paths,
    read_database_track_paths,
)
from app.adapters.serato.paths import list_crate_files
from app.core.domain import Playlist, PlaylistSyncState
from app.core.track_paths import normalize_track_path
from app.services.library import UsbLibrary

logger = structlog.get_logger(__name__)


def _crate_contents(serato_root: Path | None) -> dict[str, set[str]]:
    """
    Map crate filename stem to the normalized track paths it holds.

    Args:
        serato_root: Path to _Serato_, or None when absent.

    Returns:
        Dict of crate stem -> set of normalized track paths.
    """
    if serato_root is None:
        return {}
    return {
        path.stem: {normalize_track_path(t) for t in read_crate_track_paths(path)}
        for path in list_crate_files(serato_root)
    }


def _database_index(database_path: Path | None) -> set[str]:
    """
    Return normalized track paths Serato has indexed.

    Args:
        database_path: Path to database V2, or None when absent.

    Returns:
        Set of normalized track paths.
    """
    if database_path is None:
        return set()
    return {normalize_track_path(t) for t in read_database_track_paths(database_path)}


def playlist_sync_states(library: UsbLibrary) -> tuple[PlaylistSyncState, ...]:
    """
    Compute sync state for every Rekordbox playlist on the stick.

    Compares each playlist against the crate it maps to, and against the Serato
    database index that determines what can be written at all.

    Args:
        library: Opened session handle.

    Returns:
        PlaylistSyncState per non-folder playlist, in Rekordbox order.
    """
    crates = _crate_contents(library.serato_root)
    indexed = _database_index(library.serato_database)

    states: list[PlaylistSyncState] = []
    for playlist in library.rekordbox.list_playlists():
        if playlist.is_folder:
            continue
        tracks = [
            normalize_track_path(t) for t in library.rekordbox.get_playlist_track_paths(playlist.id)
        ]
        crate_name = crate_name_for(playlist)
        in_crate = crates.get(crate_name, set())
        states.append(
            PlaylistSyncState(
                playlist_id=playlist.id,
                playlist_name=playlist.name,
                crate_name=crate_name,
                total=len(tracks),
                in_crate=sum(1 for t in tracks if t in in_crate),
                syncable=sum(1 for t in tracks if t in indexed),
            )
        )

    logger.info("sync_states_computed", playlists=len(states))
    return tuple(states)


def find_crate_name_collisions(playlists: tuple[Playlist, ...]) -> dict[str, list[str]]:
    """
    Find playlists that would write to the same crate file.

    Serato crates are flat, so two playlists in different folders can collide
    on a single filename and silently overwrite one another.

    Args:
        playlists: Playlist nodes to check.

    Returns:
        Dict of crate stem -> colliding playlist names, for collisions only.
    """
    by_name: dict[str, list[str]] = {}
    for playlist in playlists:
        if playlist.is_folder:
            continue
        by_name.setdefault(crate_name_for(playlist), []).append(playlist.name)
    return {name: owners for name, owners in by_name.items() if len(owners) > 1}


def sync_states_to_dict(states: tuple[PlaylistSyncState, ...]) -> dict[str, Any]:
    """
    Serialize sync states for machine-readable output.

    Args:
        states: Computed playlist sync states.

    Returns:
        JSON-friendly dict with per-playlist entries and a state summary.
    """
    summary: dict[str, int] = {}
    for state in states:
        summary[state.state.value] = summary.get(state.state.value, 0) + 1
    return {
        "playlists": [
            {
                "playlist_id": s.playlist_id,
                "playlist_name": s.playlist_name,
                "crate_name": s.crate_name,
                "total": s.total,
                "in_crate": s.in_crate,
                "syncable": s.syncable,
                "blocked": s.blocked,
                "state": s.state.value,
            }
            for s in states
        ],
        "summary": summary,
        "count": len(states),
    }
