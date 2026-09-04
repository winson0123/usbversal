"""Playlist track rows for the Library screen preview table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.adapters.serato import crate_name_for, read_crate_track_paths, volume_label_for
from app.adapters.serato.paths import list_crate_files
from app.core.domain import SyncState
from app.core.track_paths import normalize_track_path
from app.services.library import UsbLibrary
from app.services.track_records import (
    RekordboxContent,
    RekordboxLookups,
    load_lookups,
)
from app.services.track_sync import (
    content_for_path,
    contents_by_path,
    track_sync_state,
    warm_analysis_ported_cache,
)


@dataclass(frozen=True)
class TrackPreview:
    """
    One playlist track as the Library preview table shows it.

    Attributes:
        title: Rekordbox title, or the file name when title is missing.
        genre: Genre name, or empty.
        key: Key name, or empty.
        bpm: Tempo to two decimal places, or empty.
        state: Green when the track is in the crate and analysis is on
            the file (or Rekordbox had nothing to port); yellow when it
            is in the crate but analysis is missing; red when it is not
            in the crate.
    """

    title: str
    genre: str
    key: str
    bpm: str
    state: SyncState


def preview_playlist_tracks(library: UsbLibrary, playlist_id: int) -> list[TrackPreview]:
    """
    Build preview rows for one playlist, in playlist order.

    Colour follows crate membership and whether Rekordbox analysis is
    already on the audio file.

    Args:
        library: Opened session handle.
        playlist_id: Rekordbox playlist id (a leaf, not a folder).

    Returns:
        One row per path in the playlist. Missing metadata stays blank.
    """
    playlists = library.rekordbox.list_playlists()
    by_id = {playlist.id: playlist for playlist in playlists}
    playlist = by_id.get(playlist_id)
    if playlist is None or playlist.is_folder:
        return []

    crate_name = crate_name_for(playlist, by_id, volume=volume_label_for(library.mount))
    in_crate = _crate_paths(library.serato_root).get(crate_name, set())
    contents = contents_by_path(library.rekordbox.database)
    lookups = _safe_lookups(library)
    cache: dict[str, bool] = {}
    try:
        raw_paths = list(library.rekordbox.get_playlist_track_paths(playlist_id))
    except Exception:
        return []
    warm_analysis_ported_cache(
        library.mount,
        [(raw, content_for_path(contents, raw)) for raw in raw_paths],
        cache,
    )
    rows: list[TrackPreview] = []
    for raw in raw_paths:
        path = normalize_track_path(raw)
        content = content_for_path(contents, raw)
        state = track_sync_state(
            in_crate=path in in_crate,
            mount=library.mount,
            raw=raw,
            content=content,
            cache=cache,
        )
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


def _safe_lookups(library: UsbLibrary) -> RekordboxLookups:
    """
    Load id-to-name tables, or empty tables when the adapter has none.

    ``load_lookups`` already isolates per-table Diesel/rbox failures.
    This catches adapters that lack a database handle at all (tests,
    stubs) so the preview pane still paints titles and sync colours.

    Args:
        library: Opened session handle.

    Returns:
        Lookups for genre and key names.
    """
    try:
        return load_lookups(library.rekordbox.database)
    except Exception:
        return RekordboxLookups({}, {}, {}, {})


def _row_from_content(
    path: str,
    content: RekordboxContent | None,
    lookups: RekordboxLookups,
    state: SyncState,
) -> TrackPreview:
    """
    Fill one preview row from a content row, or from the path alone.

    Args:
        path: Normalized track path.
        content: Rekordbox content row, or None when missing.
        lookups: Genre and key names.
        state: Traffic-light colour for the row.

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
