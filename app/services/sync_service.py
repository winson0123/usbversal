"""Playlist sync state: how much of each Rekordbox playlist reached Serato."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import structlog

from app.adapters.serato import (
    crate_name_for,
    drop_legacy_slash_names,
    read_crate_track_paths,
    read_database_track_paths,
    volume_label_for,
)
from app.adapters.serato.library_db import (
    TrackAnalysis,
    library_db_path,
    update_track_analysis,
)
from app.adapters.serato.neworder import (
    merge_crate_order,
    with_ancestors,
    with_parent_first,
    write_crate_order,
)
from app.adapters.serato.paths import list_crate_files
from app.adapters.serato.writer import (
    CrateExistsError,
    append_database_tracks,
    write_crate,
    write_volume_parent_crate,
)
from app.core.domain import Playlist, PlaylistSyncState, SyncState
from app.core.playlist_tree import PlaylistNode, build_playlist_tree
from app.core.track_paths import normalize_track_path
from app.services.errors import PlaylistNotFoundError, SeratoLibraryRequiredError
from app.services.library import UsbLibrary
from app.services.sync_analysis import AnalysisJob, AnalysisTrackResult, begin_analysis_jobs
from app.services.sync_progress import (
    SyncProgressCallback,
    attach_playlist,
    emit_progress,
    playlist_path_meta,
    rebase_progress,
)
from app.services.track_records import (
    RekordboxContent,
    RekordboxLookups,
    build_track_record,
    load_lookups,
    serato_path,
)
from app.services.track_sync import analysis_dat_path, analysis_is_ported, contents_by_path
from app.storage.mounts import flush_mount

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


def playlist_sync_states(
    library: UsbLibrary, *, check_analysis: bool = True
) -> tuple[PlaylistSyncState, ...]:
    """
    Compute sync state for every Rekordbox playlist on the stick.

    A track is green only when it is in the crate and Rekordbox analysis
    is already on the file, or Rekordbox had nothing to port. The
    numerator in ``x/y`` is that green count. ``check_analysis=False``
    skips ANLZ and tag reads so the tree can appear from crate
    membership alone.

    Args:
        library: Opened session handle.
        check_analysis: When False, ``complete`` stays 0 and no audio
            or ANLZ file is opened.

    Returns:
        PlaylistSyncState per non-folder playlist, in Rekordbox order.
    """
    crates = _crate_contents(library.serato_root)
    indexed = _database_index(library.serato_database)
    playlists = library.rekordbox.list_playlists()
    by_id = {p.id: p for p in playlists}
    contents = contents_by_path(library.rekordbox.database) if check_analysis else {}
    cache: dict[str, bool] = {}

    states: list[PlaylistSyncState] = []
    for playlist in playlists:
        if playlist.is_folder:
            continue
        crate_name = crate_name_for(playlist, by_id, volume=volume_label_for(library.mount))
        total, in_crate, complete, syncable = _playlist_track_counts(
            library,
            playlist.id,
            crates.get(crate_name, set()),
            indexed,
            contents,
            cache,
            check_analysis=check_analysis,
        )
        states.append(
            PlaylistSyncState(
                playlist_id=playlist.id,
                playlist_name=playlist.name,
                crate_name=crate_name,
                total=total,
                in_crate=in_crate,
                complete=complete,
                syncable=syncable,
            )
        )
    logger.info("sync_states_computed", playlists=len(states))
    return tuple(states)


def _playlist_track_counts(
    library: UsbLibrary,
    playlist_id: int,
    crate_paths: set[str],
    indexed: set[str],
    contents: dict[str, RekordboxContent],
    cache: dict[str, bool],
    *,
    check_analysis: bool,
) -> tuple[int, int, int, int]:
    """
    Count total, in-crate, green, and syncable tracks for one playlist.

    Args:
        library: Opened session handle.
        playlist_id: Rekordbox playlist id.
        crate_paths: Normalized paths already in the mapped crate.
        indexed: Normalized paths present in database V2.
        contents: Path to Rekordbox content row.
        cache: Shared analysis-ported cache.
        check_analysis: When False, skip ANLZ and tag reads.

    Returns:
        ``(total, in_crate, complete, syncable)``.
    """
    raws = library.rekordbox.get_playlist_track_paths(playlist_id)
    in_crate = 0
    complete = 0
    syncable = 0
    for raw in raws:
        key = normalize_track_path(raw)
        if key in indexed:
            syncable += 1
        if key not in crate_paths:
            continue
        in_crate += 1
        if not check_analysis:
            continue
        content = contents.get(key) or contents.get(serato_path(raw))
        if analysis_is_ported(library.mount, raw, content, cache):
            complete += 1
    return len(raws), in_crate, complete, syncable


@dataclass(frozen=True)
class PlaylistTreeSyncState:
    """
    One node of the playlist tree, carrying its own or its rolled-up sync state.

    Attributes:
        node: Underlying tree node (the playlist/folder plus nested children).
        state: This node's traffic-light state -- a leaf's own state, or a
            folder's rolled up from its descendants.
        synced: Green tracks -- a leaf's own ``complete``, or the sum
            across a folder's descendants.
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


def playlist_tree_sync_states(
    library: UsbLibrary, *, check_analysis: bool = True
) -> tuple[PlaylistTreeSyncState, ...]:
    """
    Build the playlist tree with a red/yellow/green state at every node.

    A leaf's state and counts come straight from ``playlist_sync_states``. A
    folder's state is rolled up from its children -- which, for a nested
    folder, is already itself a rollup, so the same three-way rule composes
    correctly at every depth without re-walking descendants -- and its counts
    are simply the sum of its children's.

    Args:
        library: Opened session handle.
        check_analysis: Forwarded to ``playlist_sync_states``.

    Returns:
        Root-level tree-sync-state nodes, in Rekordbox order.
    """
    leaf_states = {
        state.playlist_id: state
        for state in playlist_sync_states(library, check_analysis=check_analysis)
    }
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
        synced=leaf.complete,
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
    only in characters ``sanitize_crate_name`` turns into ``_``
    (``"Trance:2024"`` and ``"Trance?2024"`` both become ``"Trance_2024"``).
    A ``/`` is escaped the way Serato writes it and does not collide with those.

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
        records_added: Track records added to the Serato database.
        results: Per-playlist outcomes in selection order.
        grids_written: Tracks that received a Serato BeatGrid tag.
        cues_written: Tracks that received Serato Markers2 hot cues.
        index_rows_updated: location.sqlite rows updated to match.
        analysis_errors: One message per track whose analysis could not be written.
    """

    mount: Path
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


def _analysis_jobs(
    mount: Path,
    contents: dict[str, RekordboxContent],
    paths: Sequence[str],
    lookups: RekordboxLookups,
) -> list[AnalysisJob]:
    """
    Build worker jobs from rekordbox content rows.

    Must run on the dedicated rekordbox thread: it reads content attributes.

    Args:
        mount: Mount root.
        contents: Rekordbox path to content row.
        paths: Rekordbox track paths to process.
        lookups: Id-to-name tables, for key lookups.

    Returns:
        One job per path, with only filesystem paths and key names.
    """
    jobs: list[AnalysisJob] = []
    for raw in paths:
        content = contents.get(raw)
        dat_path = analysis_dat_path(mount, content)
        key = lookups.keys.get(content.key_id) if content is not None else None
        jobs.append(
            AnalysisJob(
                raw=raw,
                audio_path=mount / serato_path(raw),
                dat_path=dat_path,
                key=key,
            )
        )
    return jobs


def _analysis_from_results(
    results: Sequence[AnalysisTrackResult],
    index_path: Path | None,
) -> AnalysisSyncResult:
    """
    Update ``location.sqlite`` from finished analysis jobs.

    A track with a beatgrid updates the library index even when the tags
    were already on disk, so the list can be marked analyzed. A track
    this pass could not write is left exactly as Serato had it.

    Args:
        results: Per-track outcomes from the analysis pool.
        index_path: Path to location.sqlite, or None when absent.

    Returns:
        Counts of what was written, and one message per track that failed.
    """
    cues_written = 0
    grids_written = 0
    errors: list[str] = []
    updates: dict[str, TrackAnalysis] = {}
    for result in results:
        if result.error is not None:
            errors.append(f"{result.raw}: {result.error}")
            continue
        if result.analysis is not None:
            updates[serato_path(result.raw)] = result.analysis
            if result.tags_written:
                grids_written += 1
        if result.cues_written:
            cues_written += 1

    rows_updated = 0
    if updates and index_path is not None:
        rows_updated = update_track_analysis(index_path, updates)

    logger.info(
        "analysis_sync_completed",
        grids_written=grids_written,
        cues_written=cues_written,
        index_rows_updated=rows_updated,
        errors=len(errors),
    )
    return AnalysisSyncResult(
        grids_written=grids_written,
        cues_written=cues_written,
        index_rows_updated=rows_updated,
        errors=tuple(errors),
    )


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


def _tracks_with_analysis(
    mount: Path, all_paths: set[str], by_path: dict[str, RekordboxContent]
) -> set[str]:
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
    by_path: dict[str, RekordboxContent],
    lookups: RekordboxLookups,
    on_progress: SyncProgressCallback | None = None,
) -> int:
    """
    Append database V2 rows for ``missing``. Returns how many were written.

    Args:
        database_path: Path to database V2.
        missing: Rekordbox paths not yet indexed.
        by_path: Content row per Rekordbox path.
        lookups: Id-to-name tables for ``build_track_record``.
        on_progress: Optional callback after each missing path is prepared.
    """
    if not missing:
        return 0
    records = []
    total = len(missing)
    for done, raw in enumerate(missing, start=1):
        if raw in by_path:
            records.append(build_track_record(by_path[raw], lookups))
        emit_progress(on_progress, "index", done, total, raw)
    return append_database_tracks(database_path=database_path, records=records)


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


def _publish_crate_order(
    serato_root: Path,
    results: Sequence[PlaylistSyncResult],
    volume: str,
) -> None:
    """
    Write the empty volume parent crate and refresh ``neworder.pref``.

    Children keep ``{volume}%%…`` names. The parent is listed first so Serato
    shows the thumbdrive folder at the top of the crate list. Every ``%%``
    ancestor stem is listed too; Serato will not show a nested crate whose
    folder nodes are missing from ``neworder.pref``.

    Args:
        serato_root: Path to ``_Serato_``.
        results: Per-playlist crate write outcomes.
        volume: Sanitized thumbdrive label.
    """
    written = _written_crate_names(results)
    write_volume_parent_crate(serato_root=serato_root, volume=volume)
    write_crate_order(
        serato_root,
        with_ancestors(
            with_parent_first(
                drop_legacy_slash_names(merge_crate_order(serato_root, written), written),
                volume,
            )
        ),
    )


def _write_playlist_crates(
    serato_root: Path,
    selected: Sequence[Playlist],
    by_id: dict[int, Playlist],
    tracks_by_playlist: dict[int, Sequence[str]],
    on_progress: SyncProgressCallback | None = None,
    volume: str | None = None,
) -> list[PlaylistSyncResult]:
    """
    Write one crate per selected playlist. Failed writes set ``error``.

    Args:
        serato_root: Path to ``_Serato_``.
        selected: Leaf playlists in selection order.
        by_id: Every playlist on the stick, for crate-name ancestry.
        tracks_by_playlist: Rekordbox paths per playlist id.
        on_progress: Optional callback after each crate write.
        volume: Thumbdrive label prefixed onto every crate name.
    """
    results: list[PlaylistSyncResult] = []
    total = len(selected)
    for done, playlist in enumerate(selected, start=1):
        crate_name = crate_name_for(playlist, by_id, volume=volume)
        paths = [serato_path(raw) for raw in tracks_by_playlist[playlist.id]]
        error: str | None = None
        try:
            write_crate(
                serato_root=serato_root,
                crate_name=crate_name,
                track_paths=paths,
                overwrite=True,
            )
        except (CrateExistsError, OSError) as exc:
            error = str(exc)
            results.append(
                PlaylistSyncResult(
                    playlist_id=playlist.id,
                    playlist_name=playlist.name,
                    crate_name=crate_name,
                    tracks=0,
                    error=error,
                )
            )
            emit_progress(
                on_progress,
                "crates",
                done,
                total,
                crate_name,
                error,
                playlist=playlist.name,
                playlist_done=done,
                playlist_total=total,
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
        emit_progress(
            on_progress,
            "crates",
            done,
            total,
            crate_name,
            playlist=playlist.name,
            playlist_done=done,
            playlist_total=total,
        )
    return results


def sync_playlists(
    library: UsbLibrary,
    playlist_ids: Sequence[int],
    *,
    on_progress: SyncProgressCallback | None = None,
) -> SyncReport:
    """
    Mirror the selected Rekordbox playlists into Serato crates.

    Adds any track records Serato is missing in a single pass, starts
    analysis tag writes, and while that pool runs writes one crate per
    playlist and updates the crate order. ``location.sqlite`` waits for
    the tag results so the library list matches. A track's analysis is
    skipped, not aborted, when its audio or ANLZ data cannot be read.

    Args:
        library: Opened session handle.
        playlist_ids: Rekordbox playlist ids to sync, in selection order.
        on_progress: Optional callback for each index, analysis, and crate
            step. ``error`` is that item's failure message, or None.
            A phase with nothing to do emits nothing.

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

    try:
        lookups = load_lookups(library.rekordbox.database)
        by_path = {c.path: c for c in library.rekordbox.database.get_contents()}
        analysis_targets = _tracks_with_analysis(library.mount, all_paths, by_path)
        groups = [(p.name, tracks_by_playlist[p.id]) for p in selected]
        index_paths, index_meta = playlist_path_meta(groups, set(missing))
        analysis_paths, analysis_meta = playlist_path_meta(groups, analysis_targets)
        sync_total = len(missing) + len(analysis_targets) + len(selected)
        records_added = _index_missing_tracks(
            database_path,
            index_paths,
            by_path,
            lookups,
            attach_playlist(rebase_progress(on_progress, 0, sync_total), index_meta),
        )
        session = begin_analysis_jobs(
            _analysis_jobs(library.mount, by_path, analysis_paths, lookups),
            attach_playlist(rebase_progress(on_progress, len(missing), sync_total), analysis_meta),
        )
        try:
            volume = volume_label_for(library.mount)
            results = _write_playlist_crates(
                serato_root,
                selected,
                by_id,
                tracks_by_playlist,
                rebase_progress(on_progress, len(missing) + len(analysis_targets), sync_total),
                volume=volume,
            )
            _publish_crate_order(serato_root, results, volume)
            track_results = session.wait()
        finally:
            session.close()
        analysis = _analysis_from_results(track_results, _existing_index_path(serato_root))

        logger.info(
            "sync_completed",
            playlists=len(results),
            records_added=records_added,
            grids_written=analysis.grids_written,
            cues_written=analysis.cues_written,
            index_rows_updated=analysis.index_rows_updated,
        )
        return SyncReport(
            mount=library.mount,
            records_added=records_added,
            results=tuple(results),
            grids_written=analysis.grids_written,
            cues_written=analysis.cues_written,
            index_rows_updated=analysis.index_rows_updated,
            analysis_errors=analysis.errors,
        )
    finally:
        flush_mount(library.mount)
