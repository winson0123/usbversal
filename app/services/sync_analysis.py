"""Write Rekordbox analysis into Serato tags and the library index."""

from __future__ import annotations

from collections.abc import Callable
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
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.library_db import (
    TrackAnalysis,
    library_db_path,
    read_track_analysis,
    update_track_analysis,
)
from app.adapters.serato.markers2 import Cue, decode_markers, encode_markers, replace_cues
from app.adapters.serato.tags import TagFormatError, read_geob, write_geob
from app.services.backup_service import backup_mount_for_migration
from app.services.library import UsbLibrary
from app.services.migration_service import SeratoLibraryRequiredError
from app.services.track_records import RekordboxLookups, serato_path

logger = structlog.get_logger(__name__)

AnalysisProgress = Callable[[int, int, str, str | None], None]


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


def analysis_dat_path(mount: Path, content: Any) -> Path | None:
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


def _beatgrid_update(beats: list[Beat]) -> dict[str, bytes]:
    """
    Encode a BeatGrid tag when the track has beats.

    Args:
        beats: Beats to encode, empty to skip.

    Returns:
        A one-entry update dict, or empty when there is nothing to write.
    """
    grid = encode_beatgrid(beats) if beats else None
    if grid is None:
        return {}
    return {"Serato BeatGrid": grid}


def _markers_update(audio_path: Path, cues: list[HotCue]) -> dict[str, bytes]:
    """
    Encode a Markers2 tag when the track has hot cues.

    Args:
        audio_path: Path to the audio file, for reading an existing payload.
        cues: Hot cues to encode, empty to skip.

    Returns:
        A one-entry update dict, or empty when there is nothing to write.
    """
    if not cues:
        return {}
    existing = read_geob(audio_path).get("Serato Markers2")
    markers = replace_cues(
        decode_markers(existing) if existing else [],
        [Cue(slot=cue.slot, position_ms=cue.position_ms, colour=cue.colour) for cue in cues],
    )
    return {
        "Serato Markers2": encode_markers(markers, payload_size=len(existing) if existing else None)
    }


def write_track_tags(audio_path: Path, beats: list[Beat], cues: list[HotCue]) -> None:
    """
    Write a track's beatgrid and hot cues into its audio tags.

    Args:
        audio_path: Path to the .mp3 or .wav file.
        beats: Beats to encode as a Serato BeatGrid, empty to leave it alone.
        cues: Hot cues to encode as Serato Markers2, empty to leave them alone.
    """
    updates = {**_beatgrid_update(beats), **_markers_update(audio_path, cues)}
    if updates:
        write_geob(audio_path, updates)


def _analysis_inputs(mount: Path, content: Any, raw: str) -> tuple[Path, Path] | None:
    """
    Return ``(audio_path, dat_path)`` for one track, or None to skip.

    Args:
        mount: Mount root.
        content: Rekordbox content row, or None when the path is unknown.
        raw: Rekordbox track path.

    Returns:
        Audio and ANLZ paths when both are usable, otherwise None.
    """
    if content is None:
        return None
    audio_path = mount / serato_path(raw)
    dat_path = analysis_dat_path(mount, content)
    if dat_path is None or not audio_path.is_file():
        return None
    return audio_path, dat_path


def _write_analysis_tags(
    audio_path: Path, dat_path: Path
) -> tuple[list[Beat], list[HotCue]] | None:
    """Write Serato tags from ANLZ data. None when the track has neither grid nor cues."""
    beats = read_beats(dat_path)
    cues = read_hot_cues(extended_path(dat_path))
    if not beats and not cues:
        return None
    write_track_tags(audio_path, beats, cues)
    return beats, cues


def _record_one_analysis_track(
    mount: Path,
    contents: dict[str, Any],
    raw: str,
    lookups: RekordboxLookups,
) -> tuple[str | None, TrackAnalysis | None, bool]:
    """
    Write one track's analysis tags.

    Args:
        mount: Mount root.
        contents: Rekordbox path to content row.
        raw: Rekordbox track path.
        lookups: Id-to-name tables, for the index key column.

    Returns:
        ``(error, index_update, wrote_cues)``.
    """
    content = contents.get(raw)
    inputs = _analysis_inputs(mount, content, raw)
    if inputs is None:
        return None, None, False
    try:
        written = _write_analysis_tags(*inputs)
    except (AnlzError, TagFormatError, OSError) as exc:
        return str(exc), None, False
    if written is None:
        return None, None, False
    beats, cues = written
    update = None
    if beats:
        update = TrackAnalysis(bpm=beats[0].bpm, key=lookups.keys.get(content.key_id))
    return None, update, bool(cues)


def _tally_one_analysis(
    mount: Path,
    contents: dict[str, Any],
    raw: str,
    lookups: RekordboxLookups,
    updates: dict[str, TrackAnalysis],
    errors: list[str],
) -> tuple[str | None, bool]:
    """
    Record one track's analysis write and update running tallies.

    Args:
        mount: Mount root.
        contents: Rekordbox path to content row.
        raw: Rekordbox track path.
        lookups: Id-to-name tables, for the index key column.
        updates: Index updates collected so far; mutated when a grid is written.
        errors: Failure messages collected so far; mutated on a write error.

    Returns:
        ``(error, wrote_cues)`` for this track.
    """
    track_error, update, wrote_cues = _record_one_analysis_track(mount, contents, raw, lookups)
    if track_error is not None:
        errors.append(f"{raw}: {track_error}")
    if update is not None:
        updates[serato_path(raw)] = update
    return track_error, wrote_cues


def _emit_progress(
    on_progress: AnalysisProgress | None,
    done: int,
    total: int,
    raw: str,
    track_error: str | None,
) -> None:
    """Invoke ``on_progress`` when a caller supplied one."""
    if on_progress is not None:
        on_progress(done, total, raw, track_error)


def _flush_index(index_path: Path | None, updates: dict[str, TrackAnalysis]) -> int:
    """Write collected analysis updates into location.sqlite when present."""
    if not updates or index_path is None:
        return 0
    return update_track_analysis(index_path, updates)


def sync_analysis(
    mount: Path,
    index_path: Path | None,
    contents: dict[str, Any],
    paths: set[str],
    lookups: RekordboxLookups,
    write_context: WriteContext,
    on_progress: AnalysisProgress | None = None,
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
        on_progress: Optional callback invoked as ``(tracks_done, total, track,
            error)`` after each track.

    Returns:
        Counts of what was written, and one message per track that failed.
    """
    _ = write_context
    grids = 0
    cues_written = 0
    errors: list[str] = []
    updates: dict[str, TrackAnalysis] = {}

    ordered = sorted(paths)
    for done, raw in enumerate(ordered, start=1):
        track_error: str | None = None
        try:
            track_error, wrote_cues = _tally_one_analysis(
                mount, contents, raw, lookups, updates, errors
            )
            cues_written += int(wrote_cues)
        finally:
            _emit_progress(on_progress, done, len(ordered), raw, track_error)
    grids = len(updates)
    rows_updated = _flush_index(index_path, updates)

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


def _grid_bpm(mount: Path, content: Any) -> tuple[str, float] | None:
    """
    Return a track's drive-relative path and first-beat tempo.

    Args:
        mount: Mount root.
        content: Rekordbox content row.

    Returns:
        ``(serato_path, bpm)`` when the track has a readable grid, else None.
    """
    dat_path = analysis_dat_path(mount, content)
    if dat_path is None:
        return None
    beats = read_beats(dat_path)
    if not beats:
        return None
    return serato_path(content.path), beats[0].bpm


def _collect_bpm_corrections(
    library: UsbLibrary, indexed: dict[str, TrackAnalysis]
) -> tuple[dict[str, TrackAnalysis], int]:
    """
    Find index rows whose stored BPM disagrees with the first beat.

    Args:
        library: Opened session handle.
        indexed: Existing location.sqlite rows, keyed by drive-relative path.

    Returns:
        ``(updates, candidates)`` — rows to correct, and how many could be judged.
    """
    updates: dict[str, TrackAnalysis] = {}
    candidates = 0
    for content in library.rekordbox.database.get_contents():
        found = _grid_bpm(library.mount, content)
        if found is None:
            continue
        path, bpm = found
        stored = indexed.get(path)
        if stored is None:
            continue
        candidates += 1
        if stored.bpm != bpm:
            updates[path] = TrackAnalysis(bpm=bpm)
    return updates, candidates


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

    updates, candidates = _collect_bpm_corrections(library, read_track_analysis(index_path))
    if dry_run or not updates:
        return IndexCorrectionResult(
            candidates=candidates, rows_updated=len(updates), backup_id=None
        )

    backup = backup_mount_for_migration(library.mount, backup_root=backup_root)
    context = WriteContext(backup_path=backup.backup_dir)
    _ = context
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
