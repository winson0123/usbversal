"""Playlist track rows for the Library screen preview table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.adapters.serato import crate_name_for, read_crate_track_paths, volume_label_for
from app.adapters.serato.paths import list_crate_files
from app.core.domain import SyncState
from app.core.track_paths import normalize_track_path
from app.services.library import UsbLibrary
from app.services.track_records import RekordboxLookups, load_lookups, serato_path


@dataclass(frozen=True)
class TrackPreview:
    """
    One playlist track as the Library preview table shows it.

    Attributes:
        title: Rekordbox title, or the file name when title is missing.
        genre: Genre name, or empty.
        key: Key name, or empty.
        bpm: Tempo to two decimal places, or empty.
        state: Green when the track is in the crate, red when it is not.
    """

    title: str
    genre: str
    key: str
    bpm: str
    state: SyncState


def preview_playlist_tracks(library: UsbLibrary, playlist_id: int) -> list[TrackPreview]:
    """
    Build preview rows for one playlist, in playlist order.

    Crate membership is the colour for this pass: in the crate is green,
    missing is red. Analysis-on-file (yellow) is a later task.

    Args:
        library: Opened session handle.
        playlist_id: Rekordbox playlist id (a leaf, not a folder).

    Returns:
        One row per path in the playlist. Unknown metadata stays blank.
    """
    playlists = library.rekordbox.list_playlists()
    by_id = {playlist.id: playlist for playlist in playlists}
    playlist = by_id.get(playlist_id)
    if playlist is None or playlist.is_folder:
        return []

    crate_name = crate_name_for(playlist, by_id, volume=volume_label_for(library.mount))
    in_crate = _crate_paths(library.serato_root).get(crate_name, set())
    contents = _contents_by_path(library)
    lookups = _safe_lookups(library)
    rows: list[TrackPreview] = []
    for raw in library.rekordbox.get_playlist_track_paths(playlist_id):
        path = normalize_track_path(raw)
        content = contents.get(path) or contents.get(serato_path(raw))
        state = SyncState.SYNCED if path in in_crate else SyncState.NOT_SYNCED
        rows.append(_row_from_content(path, content, lookups, state))
    return rows


def _crate_paths(serato_root: Path | None) -> dict[str, set[str]]:
    """
    Map crate stem to normalized track paths.

    Args:
        serato_root: Path to ``_Serato_``, or None when absent.

    Returns:
        Crate filename stem to the tracks it holds.
    """
    if serato_root is None:
        return {}
    return {
        path.stem: {normalize_track_path(t) for t in read_crate_track_paths(path)}
        for path in list_crate_files(serato_root)
    }


def _contents_by_path(library: UsbLibrary) -> dict[str, Any]:
    """
    Map normalized and drive-relative paths to Rekordbox content rows.

    Args:
        library: Opened session handle.

    Returns:
        Path string to content row. Empty when the adapter has no contents.
    """
    fetch = getattr(library.rekordbox.database, "get_contents", None)
    if not callable(fetch):
        return {}
    try:
        rows = list(fetch())
    except TypeError:
        return {}
    by_path: dict[str, Any] = {}
    for content in rows:
        raw = getattr(content, "path", None)
        if not raw:
            continue
        by_path[normalize_track_path(str(raw))] = content
        by_path[serato_path(str(raw))] = content
    return by_path


def _safe_lookups(library: UsbLibrary) -> RekordboxLookups:
    """
    Load id-to-name tables, or empty tables when the adapter has none.

    Args:
        library: Opened session handle.

    Returns:
        Lookups for genre and key names.
    """
    try:
        return load_lookups(library.rekordbox.database)
    except (TypeError, AttributeError):
        return RekordboxLookups({}, {}, {}, {})


def _row_from_content(
    path: str,
    content: Any | None,
    lookups: RekordboxLookups,
    state: SyncState,
) -> TrackPreview:
    """
    Fill one preview row from a content row, or from the path alone.

    Args:
        path: Normalized track path.
        content: Rekordbox content row, or None when missing.
        lookups: Genre and key names.
        state: Crate-membership colour.

    Returns:
        Display fields for the table.
    """
    title = Path(path).name
    genre = ""
    key = ""
    bpm = ""
    if content is not None:
        title = getattr(content, "title", None) or title
        genre_id = getattr(content, "genre_id", None)
        key_id = getattr(content, "key_id", None)
        if genre_id is not None:
            genre = lookups.genres.get(genre_id, "")
        if key_id is not None:
            key = lookups.keys.get(key_id, "")
        bpmx100 = getattr(content, "bpmx100", None)
        if bpmx100:
            bpm = f"{bpmx100 / 100:.2f}"
    return TrackPreview(title=title, genre=genre, key=key, bpm=bpm, state=state)
