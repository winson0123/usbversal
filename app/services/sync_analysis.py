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


def write_track_tags(audio_path: Path, beats: list[Beat], cues: list[HotCue]) -> None:
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
        markers = replace_cues(
            decode_markers(existing) if existing else [],
            [Cue(slot=cue.slot, position_ms=cue.position_ms, colour=cue.colour) for cue in cues],
        )
        updates["Serato Markers2"] = encode_markers(
            markers, payload_size=len(existing) if existing else None
        )
    if updates:
        write_geob(audio_path, updates)


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
    cues_written = 0
    errors: list[str] = []
    updates: dict[str, TrackAnalysis] = {}
    ordered = sorted(paths)

    for done, raw in enumerate(ordered, start=1):
        track_error: str | None = None
        try:
            content = contents.get(raw)
            audio_path = mount / serato_path(raw)
            dat_path = analysis_dat_path(mount, content) if content is not None else None
            if content is None or dat_path is None or not audio_path.is_file():
                continue
            try:
                beats = read_beats(dat_path)
                cues = read_hot_cues(extended_path(dat_path))
                if not beats and not cues:
                    continue
                write_track_tags(audio_path, beats, cues)
            except (AnlzError, TagFormatError, OSError) as exc:
                track_error = str(exc)
                errors.append(f"{raw}: {track_error}")
                continue
            if beats:
                updates[serato_path(raw)] = TrackAnalysis(
                    bpm=beats[0].bpm, key=lookups.keys.get(content.key_id)
                )
            if cues:
                cues_written += 1
        finally:
            if on_progress is not None:
                on_progress(done, len(ordered), raw, track_error)

    rows_updated = 0
    if updates and index_path is not None:
        rows_updated = update_track_analysis(index_path, updates)

    logger.info(
        "analysis_sync_completed",
        grids_written=len(updates),
        cues_written=cues_written,
        index_rows_updated=rows_updated,
        errors=len(errors),
    )
    return AnalysisSyncResult(
        grids_written=len(updates),
        cues_written=cues_written,
        index_rows_updated=rows_updated,
        errors=tuple(errors),
    )


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
        dat_path = analysis_dat_path(library.mount, content)
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
        if stored.bpm != beats[0].bpm:
            updates[path] = TrackAnalysis(bpm=beats[0].bpm)

    if dry_run or not updates:
        return IndexCorrectionResult(
            candidates=candidates, rows_updated=len(updates), backup_id=None
        )

    backup = backup_mount_for_migration(library.mount, backup_root=backup_root)
    _ = WriteContext(backup_path=backup.backup_dir)
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
