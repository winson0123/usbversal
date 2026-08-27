"""Playlist sync state: how much of each Rekordbox playlist reached Serato."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.adapters.base import WriteContext
from app.adapters.serato import (
    crate_name_for,
    read_crate_track_paths,
    read_database_track_paths,
)
from app.adapters.serato.library_db import library_db_path
from app.adapters.serato.neworder import merge_crate_order, write_crate_order
from app.adapters.serato.paths import list_crate_files
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
from app.services.sync_analysis import (
    IndexCorrectionResult as IndexCorrectionResult,
)
from app.services.sync_analysis import (
    analysis_dat_path,
    sync_analysis,
)
from app.services.sync_analysis import (
    correct_index_bpm as correct_index_bpm,
)
from app.services.track_records import (
    RekordboxLookups,
    build_track_record,
    load_lookups,
    serato_path,
)

logger = structlog.get_logger(__name__)

# Called once per track during the analysis pass, as
# (tracks_done, total, track_path, error_or_none) -- error_or_none is the
# failure message when that specific track's analysis could not be written,
# and None when it was (or when it simply had nothing to write).
SyncProgressCallback = Callable[[int, int, str, str | None], None]


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
        leaf_ids: Playlist ids of every non-folder descendant, including
            this node when it is itself a playlist.
        children: Nested tree-sync-state nodes, mirroring ``node.children``.
    """

    node: PlaylistNode
    state: SyncState
    synced: int
    total: int
    leaf_ids: tuple[int, ...]
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
    return tuple(_walk_playlist_tree(node, leaf_states) for node in roots)


def _leaf_tree_state(
    node: PlaylistNode, leaf_states: dict[int, PlaylistSyncState]
) -> PlaylistTreeSyncState:
    """Build a tree node from a playlist's own sync counts."""
    leaf = leaf_states.get(node.playlist.id)
    if leaf is None:
        return PlaylistTreeSyncState(
            node=node,
            state=SyncState.NOT_SYNCED,
            synced=0,
            total=0,
            leaf_ids=(node.playlist.id,),
        )
    return PlaylistTreeSyncState(
        node=node,
        state=leaf.state,
        synced=leaf.in_crate,
        total=leaf.total,
        leaf_ids=(node.playlist.id,),
    )


def _folder_tree_state(
    node: PlaylistNode, children: tuple[PlaylistTreeSyncState, ...]
) -> PlaylistTreeSyncState:
    """Roll a folder's children into one tree node."""
    return PlaylistTreeSyncState(
        node=node,
        state=combine_sync_states([child.state for child in children]),
        synced=sum(child.synced for child in children),
        total=sum(child.total for child in children),
        leaf_ids=tuple(i for child in children for i in child.leaf_ids),
        children=children,
    )


def _walk_playlist_tree(
    node: PlaylistNode, leaf_states: dict[int, PlaylistSyncState]
) -> PlaylistTreeSyncState:
    """Roll up one playlist-tree node and its descendants."""
    children = tuple(_walk_playlist_tree(child, leaf_states) for child in node.children)
    if node.playlist.is_folder:
        return _folder_tree_state(node, children)
    return _leaf_tree_state(node, leaf_states)


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


def _require_serato_library(library: UsbLibrary) -> tuple[Path, Path]:
    """
    Return ``(_Serato_ root, database V2 path)``, or raise if either is missing.

    Args:
        library: Opened session handle.
    """
    serato_root = library.serato_root
    database_path = library.serato_database
    if serato_root is None or database_path is None:
        raise SeratoLibraryRequiredError(f"No Serato library under {library.mount}")
    return serato_root, database_path


def _leaf_playlists(
    library: UsbLibrary, playlist_ids: Sequence[int]
) -> tuple[dict[int, Playlist], list[Playlist]]:
    """
    Resolve selected ids to non-folder playlists, in selection order.

    Args:
        library: Opened session handle.
        playlist_ids: Rekordbox playlist ids to sync.

    Returns:
        The full id map, and the selected leaf playlists.
    """
    by_id = {p.id: p for p in library.rekordbox.list_playlists()}
    selected: list[Playlist] = []
    for playlist_id in playlist_ids:
        playlist = by_id.get(playlist_id)
        if playlist is None or playlist.is_folder:
            raise PlaylistNotFoundError(f"Playlist not found: {playlist_id}")
        selected.append(playlist)
    return by_id, selected


def _unindexed_tracks(
    tracks_by_playlist: dict[int, Sequence[str]], indexed: set[str]
) -> tuple[list[str], set[str]]:
    """
    Collect every selected track, and those Serato has not indexed yet.

    Args:
        tracks_by_playlist: Rekordbox paths per playlist id.
        indexed: Normalized paths already in database V2.

    Returns:
        Missing raw paths in first-seen order, plus the set of all raw paths.
    """
    missing: list[str] = []
    seen: set[str] = set()
    all_paths: set[str] = set()
    for paths in tracks_by_playlist.values():
        for raw in paths:
            all_paths.add(raw)
            key = normalize_track_path(raw)
            if key not in indexed and key not in seen:
                seen.add(key)
                missing.append(raw)
    return missing, all_paths


def _dry_run_report(
    library: UsbLibrary,
    selected: Sequence[Playlist],
    by_id: dict[int, Playlist],
    tracks_by_playlist: dict[int, Sequence[str]],
    missing: Sequence[str],
) -> SyncReport:
    """
    Build the dry-run SyncReport -- nothing is written.

    Args:
        library: Opened session handle.
        selected: Leaf playlists in selection order.
        by_id: Every playlist on the stick, for crate-name ancestry.
        tracks_by_playlist: Rekordbox paths per playlist id.
        missing: Tracks Serato has not indexed yet.
    """
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


def _tracks_with_analysis(mount: Path, all_paths: set[str], by_path: dict[str, Any]) -> set[str]:
    """
    Return selected paths that have a Rekordbox ``.DAT`` file.

    Args:
        mount: Mount root.
        all_paths: Rekordbox track paths in the selection.
        by_path: Content row per Rekordbox path.
    """
    return {raw for raw in all_paths if analysis_dat_path(mount, by_path.get(raw)) is not None}


def _index_missing_tracks(
    database_path: Path,
    missing: Sequence[str],
    by_path: dict[str, Any],
    lookups: RekordboxLookups,
    context: WriteContext,
) -> int:
    """
    Append database V2 rows for ``missing``. Returns how many were written.

    Args:
        database_path: Path to database V2.
        missing: Rekordbox paths not yet indexed.
        by_path: Content row per Rekordbox path.
        lookups: Id-to-name tables for ``build_track_record``.
        context: Validated backup context.
    """
    if not missing:
        return 0
    records = [build_track_record(by_path[raw], lookups) for raw in missing if raw in by_path]
    return append_database_tracks(
        database_path=database_path, records=records, write_context=context
    )


def _existing_index_path(serato_root: Path) -> Path | None:
    """
    Return ``location.sqlite`` if it exists, else None.

    Args:
        serato_root: Path to ``_Serato_``.
    """
    index_path = library_db_path(serato_root)
    if not index_path.is_file():
        return None
    return index_path


def _written_crate_names(results: Sequence[PlaylistSyncResult]) -> list[str]:
    """
    Crate stems whose write succeeded, in result order.

    Args:
        results: Per-playlist outcomes from ``_write_playlist_crates``.
    """
    return [result.crate_name for result in results if result.error is None]


def _write_playlist_crates(
    serato_root: Path,
    selected: Sequence[Playlist],
    by_id: dict[int, Playlist],
    tracks_by_playlist: dict[int, Sequence[str]],
    context: WriteContext,
) -> list[PlaylistSyncResult]:
    """
    Write one crate per selected playlist. Failed writes set ``error``.

    Args:
        serato_root: Path to ``_Serato_``.
        selected: Leaf playlists in selection order.
        by_id: Every playlist on the stick, for crate-name ancestry.
        tracks_by_playlist: Rekordbox paths per playlist id.
        context: Validated backup context.
    """
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
    return results


def sync_playlists(
    library: UsbLibrary,
    playlist_ids: Sequence[int],
    *,
    dry_run: bool = False,
    backup_root: str | Path | None = None,
    on_progress: SyncProgressCallback | None = None,
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
        on_progress: Optional callback invoked as ``(tracks_done, total,
            track, error)`` while writing analysis -- the slow, per-track
            part of a sync, so it is what a caller driving a progress bar
            should watch. ``error`` carries that one track's own failure
            message when it has one, otherwise None. Not called for a dry
            run, and not called at all when there is nothing with Rekordbox
            analysis data to write.

    Returns:
        SyncReport describing what was written.

    Raises:
        SeratoLibraryRequiredError: The mount has no Serato library.
        PlaylistNotFoundError: A selected id is missing or is a folder.
    """
    serato_root, database_path = _require_serato_library(library)
    by_id, selected = _leaf_playlists(library, playlist_ids)
    tracks_by_playlist = {p.id: library.rekordbox.get_playlist_track_paths(p.id) for p in selected}
    missing, all_paths = _unindexed_tracks(tracks_by_playlist, _database_index(database_path))
    if dry_run:
        return _dry_run_report(library, selected, by_id, tracks_by_playlist, missing)

    lookups = load_lookups(library.rekordbox.database)
    by_path = {c.path: c for c in library.rekordbox.database.get_contents()}
    analysis_targets = _tracks_with_analysis(library.mount, all_paths, by_path)
    backup = backup_mount_for_migration(
        library.mount,
        backup_root=backup_root,
        extra_files=[library.mount / serato_path(raw) for raw in analysis_targets],
    )
    context = WriteContext(backup_path=backup.backup_dir)
    records_added = _index_missing_tracks(database_path, missing, by_path, lookups, context)
    analysis = sync_analysis(
        library.mount,
        _existing_index_path(serato_root),
        by_path,
        analysis_targets,
        lookups,
        context,
        on_progress,
    )
    results = _write_playlist_crates(serato_root, selected, by_id, tracks_by_playlist, context)
    write_crate_order(serato_root, merge_crate_order(serato_root, _written_crate_names(results)))

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
