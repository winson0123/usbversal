"""Playlist sync state: how much of each Rekordbox playlist reached Serato."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.adapters.base import WriteContext
from app.adapters.rekordbox.anlz import (
    AnlzError,
    Beat,
    HotCue,
    extended_path,
    read_beats,
    read_hot_cues,
)
from app.adapters.serato import (
    crate_name_for,
    read_crate_track_paths,
    read_database_track_paths,
)
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.library_db import (
    TrackAnalysis,
    library_db_path,
    read_track_analysis,
    update_track_analysis,
)
from app.adapters.serato.markers2 import Cue, decode_markers, encode_markers, replace_cues
from app.adapters.serato.neworder import merge_crate_order, write_crate_order
from app.adapters.serato.paths import list_crate_files
from app.adapters.serato.tags import TagFormatError, read_geob, write_geob
from app.adapters.serato.writer import (
    CrateExistsError,
    append_database_tracks,
    write_crate,
)
from app.core.domain import Playlist, PlaylistSyncState, SyncState
from app.core.playlist_tree import PlaylistNode, build_playlist_tree
from app.core.track_paths import normalize_track_path
from app.services.backup_service import backup_mount_for_migration
from app.services.library import UsbLibrary
from app.services.migration_service import PlaylistNotFoundError, SeratoLibraryRequiredError
from app.services.track_records import (
    RekordboxLookups,
    build_track_record,
    load_lookups,
    serato_path,
)

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
    playlists = library.rekordbox.list_playlists()
    by_id = {p.id: p for p in playlists}

    states: list[PlaylistSyncState] = []
    for playlist in playlists:
        if playlist.is_folder:
            continue
        tracks = [
            normalize_track_path(t) for t in library.rekordbox.get_playlist_track_paths(playlist.id)
        ]
        crate_name = crate_name_for(playlist, by_id)
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


@dataclass(frozen=True)
class PlaylistTreeSyncState:
    """
    One node of the playlist tree, carrying its own or its rolled-up sync state.

    Attributes:
        node: Underlying tree node (the playlist/folder plus nested children).
        state: This node's traffic-light state -- a leaf's own state, or a
            folder's rolled up from its descendants.
        synced: Tracks already in the crate -- a leaf's own ``in_crate``, or
            the sum across a folder's descendants.
        total: Tracks in the playlist -- a leaf's own ``total``, or the sum
            across a folder's descendants.
        children: Nested tree-sync-state nodes, mirroring ``node.children``.
    """

    node: PlaylistNode
    state: SyncState
    synced: int
    total: int
    children: tuple[PlaylistTreeSyncState, ...] = ()


def combine_sync_states(states: list[SyncState]) -> SyncState:
    """
    Combine several sync states into one overall verdict.

    Green only if every one is fully synced, red only if none of them are --
    including no states at all, which reads as nothing outstanding to sync
    rather than vacuously "all synced" -- yellow otherwise. Used both for a
    folder's rollup from its children and, in the TUI, for a library-wide
    "select all" node's rollup from every top-level playlist.

    Args:
        states: Sync states to combine.

    Returns:
        The combined traffic-light state.
    """
    if not states:
        return SyncState.NOT_SYNCED
    if all(state == SyncState.SYNCED for state in states):
        return SyncState.SYNCED
    if all(state == SyncState.NOT_SYNCED for state in states):
        return SyncState.NOT_SYNCED
    return SyncState.PARTIAL


def playlist_tree_sync_states(library: UsbLibrary) -> tuple[PlaylistTreeSyncState, ...]:
    """
    Build the playlist tree with a red/yellow/green state at every node.

    A leaf's state and counts come straight from ``playlist_sync_states``. A
    folder's state is rolled up from its children -- which, for a nested
    folder, is already itself a rollup, so the same three-way rule composes
    correctly at every depth without re-walking descendants -- and its counts
    are simply the sum of its children's.

    Args:
        library: Opened session handle.

    Returns:
        Root-level tree-sync-state nodes, in Rekordbox order.
    """
    leaf_states = {state.playlist_id: state for state in playlist_sync_states(library)}
    roots = build_playlist_tree(library.rekordbox.list_playlists())

    def _walk(node: PlaylistNode) -> PlaylistTreeSyncState:
        children = tuple(_walk(child) for child in node.children)
        if node.playlist.is_folder:
            state = combine_sync_states([child.state for child in children])
            synced = sum(child.synced for child in children)
            total = sum(child.total for child in children)
        else:
            leaf = leaf_states.get(node.playlist.id)
            state = leaf.state if leaf is not None else SyncState.NOT_SYNCED
            synced = leaf.in_crate if leaf is not None else 0
            total = leaf.total if leaf is not None else 0
        return PlaylistTreeSyncState(
            node=node, state=state, synced=synced, total=total, children=children
        )

    return tuple(_walk(node) for node in roots)


def find_crate_name_collisions(playlists: tuple[Playlist, ...]) -> dict[str, list[str]]:
    """
    Find playlists that would write to the same crate file.

    ``crate_name_for`` encodes each ancestor folder into the filename, so two
    playlists sharing a name in different folders no longer collide. What
    still can: two playlists in the *same* folder, or two whose names differ
    only in characters ``sanitize_crate_name`` strips (``"Trance/2024"`` and
    ``"Trance:2024"`` both become ``"Trance_2024"``).

    Args:
        playlists: Playlist nodes to check.

    Returns:
        Dict of crate stem -> colliding playlist names, for collisions only.
    """
    by_id = {p.id: p for p in playlists}
    by_name: dict[str, list[str]] = {}
    for playlist in playlists:
        if playlist.is_folder:
            continue
        by_name.setdefault(crate_name_for(playlist, by_id), []).append(playlist.name)
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


@dataclass(frozen=True)
class PlaylistSyncResult:
    """
    Outcome of syncing one playlist.

    Attributes:
        playlist_id: Rekordbox playlist id.
        playlist_name: Rekordbox playlist display name.
        crate_name: Crate filename stem written.
        tracks: Tracks placed in the crate.
        error: Failure message, when the playlist could not be synced.
    """

    playlist_id: int
    playlist_name: str
    crate_name: str
    tracks: int
    error: str | None = None


@dataclass(frozen=True)
class AnalysisSyncResult:
    """
    Outcome of writing Rekordbox analysis into Serato tags and the index.

    Attributes:
        grids_written: Tracks that received a Serato BeatGrid tag.
        cues_written: Tracks that received Serato Markers2 hot cues.
        index_rows_updated: location.sqlite rows updated to match.
        errors: One "path: reason" message per track that could not be written.
    """

    grids_written: int
    cues_written: int
    index_rows_updated: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class SyncReport:
    """
    Outcome of one sync run.

    Attributes:
        mount: Mount that was synced.
        dry_run: True when nothing was written.
        backup_id: Backup taken before writing, None on a dry run.
        records_added: Track records added to the Serato database.
        results: Per-playlist outcomes in selection order.
        grids_written: Tracks that received a Serato BeatGrid tag.
        cues_written: Tracks that received Serato Markers2 hot cues.
        index_rows_updated: location.sqlite rows updated to match.
        analysis_errors: One message per track whose analysis could not be written.
    """

    mount: Path
    dry_run: bool
    backup_id: str | None
    records_added: int
    results: tuple[PlaylistSyncResult, ...]
    grids_written: int = 0
    cues_written: int = 0
    index_rows_updated: int = 0
    analysis_errors: tuple[str, ...] = ()

    @property
    def crates_written(self) -> int:
        """Number of playlists that reached a crate."""
        return sum(1 for r in self.results if r.error is None)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the report for machine-readable output.

        Returns:
            JSON-friendly dict describing the run.
        """
        return {
            "mount": str(self.mount),
            "dry_run": self.dry_run,
            "backup_id": self.backup_id,
            "records_added": self.records_added,
            "crates_written": self.crates_written,
            "grids_written": self.grids_written,
            "cues_written": self.cues_written,
            "index_rows_updated": self.index_rows_updated,
            "analysis_errors": list(self.analysis_errors),
            "playlists": [
                {
                    "playlist_id": r.playlist_id,
                    "playlist_name": r.playlist_name,
                    "crate_name": r.crate_name,
                    "tracks": r.tracks,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def _analysis_dat_path(mount: Path, content: Any) -> Path | None:
    """
    Resolve a Rekordbox track's ANLZ .DAT path on the mount.

    Args:
        mount: Mount root.
        content: rbox content row for the track.

    Returns:
        Path to the .DAT file, or None when Rekordbox has not analysed it.
    """
    raw = getattr(content, "analysis_data_file_path", None)
    if not raw:
        return None
    return mount / serato_path(raw)


def _write_track_tags(audio_path: Path, beats: list[Beat], cues: list[HotCue]) -> None:
    """
    Write a track's beatgrid and hot cues into its audio tags.

    Args:
        audio_path: Path to the .mp3 or .wav file.
        beats: Beats to encode as a Serato BeatGrid, empty to leave it alone.
        cues: Hot cues to encode as Serato Markers2, empty to leave them alone.
    """
    updates: dict[str, bytes] = {}
    if beats:
        grid = encode_beatgrid(beats)
        if grid is not None:
            updates["Serato BeatGrid"] = grid
    if cues:
        existing = read_geob(audio_path).get("Serato Markers2")
        markers = decode_markers(existing) if existing else []
        markers = replace_cues(
            markers,
            [Cue(slot=cue.slot, position_ms=cue.position_ms, colour=cue.colour) for cue in cues],
        )
        updates["Serato Markers2"] = encode_markers(
            markers, payload_size=len(existing) if existing else None
        )
    if updates:
        write_geob(audio_path, updates)


def _sync_analysis(
    mount: Path,
    index_path: Path | None,
    contents: dict[str, Any],
    paths: set[str],
    lookups: RekordboxLookups,
    write_context: WriteContext,
    on_progress: Callable[[int, int], None] | None = None,
) -> AnalysisSyncResult:
    """
    Write beatgrids and hot cues from Rekordbox ANLZ data into Serato tags.

    Only a track that gets a real beatgrid updates the library index, so the
    list stays in step with what the deck now reads from the file. A track
    this pass could not write is left exactly as Serato had it, rather than
    guessed at from Rekordbox's own BPM.

    Args:
        mount: Mount root.
        index_path: Path to location.sqlite, or None when absent.
        contents: Rekordbox path to content row, for every track in the library.
        paths: Rekordbox track paths to process; each must resolve in ``contents``
            and carry Rekordbox analysis data.
        lookups: Id-to-name tables, for key lookups.
        write_context: Validated backup context (required before any write).
        on_progress: Optional callback invoked as ``(tracks_done, total)`` after
            each track, whether or not it produced a write -- this is the slow,
            per-track part of a sync, so it is what a progress bar should track.

    Returns:
        Counts of what was written, and one message per track that failed.
    """
    _ = write_context  # validated in WriteContext.__post_init__
    grids = 0
    cues_written = 0
    errors: list[str] = []
    updates: dict[str, TrackAnalysis] = {}

    ordered = sorted(paths)
    for done, raw in enumerate(ordered, start=1):
        try:
            content = contents.get(raw)
            if content is None:
                continue
            audio_path = mount / serato_path(raw)
            dat_path = _analysis_dat_path(mount, content)
            if dat_path is None or not audio_path.is_file():
                continue

            try:
                beats = read_beats(dat_path)
                cues = read_hot_cues(extended_path(dat_path))
                if not beats and not cues:
                    continue
                _write_track_tags(audio_path, beats, cues)
            except (AnlzError, TagFormatError, OSError) as exc:
                errors.append(f"{raw}: {exc}")
                continue

            if beats:
                grids += 1
                updates[serato_path(raw)] = TrackAnalysis(
                    bpm=beats[0].bpm, key=lookups.keys.get(content.key_id)
                )
            if cues:
                cues_written += 1
        finally:
            if on_progress is not None:
                on_progress(done, len(ordered))

    rows_updated = 0
    if updates and index_path is not None:
        rows_updated = update_track_analysis(index_path, updates)

    logger.info(
        "analysis_sync_completed",
        grids_written=grids,
        cues_written=cues_written,
        index_rows_updated=rows_updated,
        errors=len(errors),
    )
    return AnalysisSyncResult(
        grids_written=grids,
        cues_written=cues_written,
        index_rows_updated=rows_updated,
        errors=tuple(errors),
    )


def sync_playlists(
    library: UsbLibrary,
    playlist_ids: Sequence[int],
    *,
    dry_run: bool = False,
    backup_root: str | Path | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> SyncReport:
    """
    Mirror the selected Rekordbox playlists into Serato crates.

    Takes one backup for the whole run, adds any track records Serato is
    missing in a single pass, writes one crate per playlist and updates the
    crate order, then writes each track's Rekordbox beatgrid and hot cues into
    its audio tags and refreshes ``location.sqlite`` so the library list
    matches. A track's analysis is skipped, not aborted, when its audio or
    ANLZ data cannot be read.

    Args:
        library: Opened session handle.
        playlist_ids: Rekordbox playlist ids to sync, in selection order.
        dry_run: Plan only; take no backup and write nothing.
        backup_root: Optional backups parent directory.
        on_progress: Optional callback invoked as ``(tracks_done, total)``
            while writing analysis -- the slow, per-track part of a sync, so
            it is what a caller driving a progress bar should watch. Not
            called for a dry run, and not called at all when there is
            nothing with Rekordbox analysis data to write.

    Returns:
        SyncReport describing what was written.

    Raises:
        SeratoLibraryRequiredError: The mount has no Serato library.
        PlaylistNotFoundError: A selected id is missing or is a folder.
    """
    serato_root = library.serato_root
    database_path = library.serato_database
    if serato_root is None or database_path is None:
        raise SeratoLibraryRequiredError(f"No Serato library under {library.mount}")

    by_id = {p.id: p for p in library.rekordbox.list_playlists()}
    selected = []
    for playlist_id in playlist_ids:
        playlist = by_id.get(playlist_id)
        if playlist is None or playlist.is_folder:
            raise PlaylistNotFoundError(f"Playlist not found: {playlist_id}")
        selected.append(playlist)

    tracks_by_playlist = {p.id: library.rekordbox.get_playlist_track_paths(p.id) for p in selected}
    indexed = _database_index(database_path)
    missing = []
    seen: set[str] = set()
    all_paths: set[str] = set()
    for paths in tracks_by_playlist.values():
        for raw in paths:
            all_paths.add(raw)
            key = normalize_track_path(raw)
            if key not in indexed and key not in seen:
                seen.add(key)
                missing.append(raw)

    if dry_run:
        return SyncReport(
            mount=library.mount,
            dry_run=True,
            backup_id=None,
            records_added=len(missing),
            results=tuple(
                PlaylistSyncResult(
                    playlist_id=p.id,
                    playlist_name=p.name,
                    crate_name=crate_name_for(p, by_id),
                    tracks=len(tracks_by_playlist[p.id]),
                )
                for p in selected
            ),
        )

    lookups = load_lookups(library.rekordbox.database)
    by_path = {c.path: c for c in library.rekordbox.database.get_contents()}
    analysis_targets = {
        raw for raw in all_paths if _analysis_dat_path(library.mount, by_path.get(raw)) is not None
    }

    backup = backup_mount_for_migration(
        library.mount,
        backup_root=backup_root,
        extra_files=[library.mount / serato_path(raw) for raw in analysis_targets],
    )
    context = WriteContext(backup_path=backup.backup_dir)

    records_added = 0
    if missing:
        records = [build_track_record(by_path[raw], lookups) for raw in missing if raw in by_path]
        records_added = append_database_tracks(
            database_path=database_path, records=records, write_context=context
        )

    index_path = library_db_path(serato_root)
    analysis = _sync_analysis(
        library.mount,
        index_path if index_path.is_file() else None,
        by_path,
        analysis_targets,
        lookups,
        context,
        on_progress,
    )

    results: list[PlaylistSyncResult] = []
    for playlist in selected:
        crate_name = crate_name_for(playlist, by_id)
        paths = [serato_path(raw) for raw in tracks_by_playlist[playlist.id]]
        try:
            write_crate(
                serato_root=serato_root,
                crate_name=crate_name,
                track_paths=paths,
                write_context=context,
                overwrite=True,
            )
        except (CrateExistsError, OSError) as exc:
            results.append(
                PlaylistSyncResult(
                    playlist_id=playlist.id,
                    playlist_name=playlist.name,
                    crate_name=crate_name,
                    tracks=0,
                    error=str(exc),
                )
            )
            continue
        results.append(
            PlaylistSyncResult(
                playlist_id=playlist.id,
                playlist_name=playlist.name,
                crate_name=crate_name,
                tracks=len(paths),
            )
        )

    write_crate_order(
        serato_root,
        merge_crate_order(serato_root, [r.crate_name for r in results if r.error is None]),
    )

    logger.info(
        "sync_completed",
        playlists=len(results),
        records_added=records_added,
        grids_written=analysis.grids_written,
        cues_written=analysis.cues_written,
        index_rows_updated=analysis.index_rows_updated,
        backup_id=backup.backup_id,
    )
    return SyncReport(
        mount=library.mount,
        dry_run=False,
        backup_id=backup.backup_id,
        records_added=records_added,
        results=tuple(results),
        grids_written=analysis.grids_written,
        cues_written=analysis.cues_written,
        index_rows_updated=analysis.index_rows_updated,
        analysis_errors=analysis.errors,
    )


@dataclass(frozen=True)
class IndexCorrectionResult:
    """
    Outcome of correcting BPM values already wrong in the Serato library index.

    Attributes:
        candidates: Tracks with both a Rekordbox beatgrid and an existing
            index row, i.e. tracks this pass could judge.
        rows_updated: Rows whose stored BPM did not match the first beat's
            tempo and were corrected. Zero on a dry run.
        backup_id: Backup taken before writing, None on a dry run or when
            nothing needed correcting.
    """

    candidates: int
    rows_updated: int
    backup_id: str | None


def correct_index_bpm(
    library: UsbLibrary,
    *,
    dry_run: bool = False,
    backup_root: str | Path | None = None,
) -> IndexCorrectionResult:
    """
    Correct Serato library index rows whose BPM disagrees with Rekordbox's grid.

    Applies the same rule ``sync_playlists`` uses when it writes a fresh grid:
    the index BPM is the track's first beat's tempo, not Rekordbox's headline
    average and not whatever Serato originally analysed. Unlike
    ``sync_playlists``, this looks at every track in the library with
    Rekordbox analysis data and an existing index row, not only tracks in a
    playlist being synced -- it is how the rows a partial sync never reached
    get fixed: constant-tempo tracks sitting at half or double tempo, and any
    variable-tempo track Serato anchored on the wrong section.

    Never writes to the audio files themselves, and never inserts a row --
    only tracks Serato has already indexed are eligible, matching
    ``update_track_analysis``'s own behaviour.

    Args:
        library: Opened session handle.
        dry_run: Plan only; take no backup and write nothing.
        backup_root: Optional backups parent directory.

    Returns:
        IndexCorrectionResult describing what would be, or was, corrected.

    Raises:
        SeratoLibraryRequiredError: The mount has no Serato library, or no
            ``location.sqlite`` index yet.
    """
    serato_root = library.serato_root
    if serato_root is None:
        raise SeratoLibraryRequiredError(f"No Serato library under {library.mount}")
    index_path = library_db_path(serato_root)
    if not index_path.is_file():
        raise SeratoLibraryRequiredError(f"No location.sqlite under {serato_root}")

    indexed = read_track_analysis(index_path)
    updates: dict[str, TrackAnalysis] = {}
    candidates = 0
    for content in library.rekordbox.database.get_contents():
        dat_path = _analysis_dat_path(library.mount, content)
        if dat_path is None:
            continue
        path = serato_path(content.path)
        stored = indexed.get(path)
        if stored is None:
            continue
        beats = read_beats(dat_path)
        if not beats:
            continue
        candidates += 1
        correct_bpm = beats[0].bpm
        if stored.bpm != correct_bpm:
            updates[path] = TrackAnalysis(bpm=correct_bpm)

    if dry_run or not updates:
        return IndexCorrectionResult(
            candidates=candidates, rows_updated=len(updates), backup_id=None
        )

    backup = backup_mount_for_migration(library.mount, backup_root=backup_root)
    context = WriteContext(backup_path=backup.backup_dir)
    _ = context  # validated in WriteContext.__post_init__
    rows_updated = update_track_analysis(index_path, updates)

    logger.info(
        "index_bpm_corrected",
        candidates=candidates,
        rows_updated=rows_updated,
        backup_id=backup.backup_id,
    )
    return IndexCorrectionResult(
        candidates=candidates, rows_updated=rows_updated, backup_id=backup.backup_id
    )
