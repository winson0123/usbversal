"""Parallel per-track analysis tag writes.

Rekordbox objects must not be touched here. Callers extract paths and key
names on the dedicated rekordbox thread, then this module reads ANLZ files
and writes audio tags on a worker pool.
"""

from __future__ import annotations

import binascii
import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from app.adapters.rekordbox.anlz import (
    AnlzError,
    Beat,
    HotCue,
    extended_path,
    read_beats,
    read_hot_cues,
)
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.library_db import TrackAnalysis
from app.adapters.serato.markers import encode_markers_v1
from app.adapters.serato.markers2 import Cue, decode_markers, encode_markers, replace_cues
from app.adapters.serato.mp4_tags import is_mp4, m4a_encoder_delay_ms
from app.adapters.serato.tags import TagFormatError, read_geob, write_geob
from app.services.sync_progress import SyncProgressCallback, emit_progress

SYNC_WORKERS_ENV = "USBVERSAL_SYNC_WORKERS"
_DEFAULT_WORKERS = 4
_MAX_WORKERS = 8


@dataclass(frozen=True)
class AnalysisJob:
    """
    One track ready for a worker, with no rekordbox objects.

    Attributes:
        raw: Rekordbox track path, for progress and error messages.
        audio_path: Audio file on the mount.
        dat_path: ANLZ ``.DAT`` path, or None when the track has no analysis.
        key: Rekordbox key name, or None.
    """

    raw: str
    audio_path: Path
    dat_path: Path | None
    key: str | None


@dataclass(frozen=True)
class AnalysisTrackResult:
    """
    Outcome of one analysis job.

    Attributes:
        raw: Rekordbox track path.
        error: Failure message, or None.
        analysis: Index row to write when a beatgrid was rewritten.
        cues_written: True when Markers2 was rewritten.
    """

    raw: str
    error: str | None
    analysis: TrackAnalysis | None
    cues_written: bool


def analysis_worker_count(job_count: int) -> int:
    """
    Return how many threads write analysis tags.

    Uses ``USBVERSAL_SYNC_WORKERS`` when set, otherwise four, capped at
    eight and at the number of jobs.

    Args:
        job_count: Tracks about to be processed.

    Returns:
        Worker count of at least 1 when there is work, else 1.
    """
    raw = os.environ.get(SYNC_WORKERS_ENV)
    if raw:
        try:
            wanted = int(raw)
        except ValueError:
            wanted = _DEFAULT_WORKERS
    else:
        wanted = min(_DEFAULT_WORKERS, os.cpu_count() or _DEFAULT_WORKERS)
    wanted = max(1, min(_MAX_WORKERS, wanted))
    return min(wanted, max(1, job_count))


def write_track_tags(audio_path: Path, beats: list[Beat], cues: list[HotCue]) -> bool:
    """
    Write a track's beatgrid and hot cues into its audio tags.

    Args:
        audio_path: Path to the audio file.
        beats: Beats to encode as a Serato BeatGrid, empty to leave it alone.
        cues: Hot cues to encode as Serato Markers2 and Markers_, empty
            to leave them alone.

    Returns:
        True when tags were rewritten, False when they already matched.
    """
    beats, cues = _shift_analysis_times(audio_path, beats, cues)
    updates: dict[str, bytes] = {}
    if beats:
        grid = encode_beatgrid(beats)
        if grid is not None:
            updates["Serato BeatGrid"] = grid
    if cues:
        existing = read_geob(audio_path).get("Serato Markers2")
        cue_rows = [
            Cue(slot=cue.slot, position_ms=cue.position_ms, colour=cue.colour) for cue in cues
        ]
        markers = replace_cues(decode_markers(existing) if existing else [], cue_rows)
        updates["Serato Markers2"] = encode_markers(
            markers, payload_size=len(existing) if existing else None
        )
        updates["Serato Markers_"] = encode_markers_v1(cue_rows)
    if not updates:
        return False
    return write_geob(audio_path, updates)


def _shift_analysis_times(
    audio_path: Path, beats: list[Beat], cues: list[HotCue]
) -> tuple[list[Beat], list[HotCue]]:
    """
    Subtract AAC encoder delay from M4A times so Serato lines up.

    Rekordbox times include priming samples. Serato's M4A waveform starts
    at the first decoded sample, so an unshifted grid sits to the right
    of the first beat.

    Args:
        audio_path: Audio file on the mount.
        beats: Rekordbox beats.
        cues: Rekordbox hot cues.

    Returns:
        Beats and cues, shifted when the file is MP4 / M4A.
    """
    if audio_path.suffix.lower() not in {".m4a", ".mp4"}:
        return beats, cues
    data = audio_path.read_bytes()
    if not is_mp4(data):
        return beats, cues
    delay = m4a_encoder_delay_ms(data)
    if delay <= 0:
        return beats, cues
    shifted_beats = [
        Beat(number=beat.number, bpm=beat.bpm, time_ms=max(0, beat.time_ms - delay))
        for beat in beats
    ]
    shifted_cues = [
        HotCue(
            slot=cue.slot,
            position_ms=max(0, cue.position_ms - delay),
            colour=cue.colour,
        )
        for cue in cues
    ]
    return shifted_beats, shifted_cues


def process_analysis_track(job: AnalysisJob) -> AnalysisTrackResult:
    """
    Read one track's ANLZ data and write Serato tags.

    Safe on a worker thread: only filesystem paths and plain values.

    Args:
        job: Track paths and key name prepared on the rekordbox thread.

    Returns:
        What was written, or the error if the track failed.
    """
    if job.dat_path is None or not job.audio_path.is_file():
        return AnalysisTrackResult(job.raw, None, None, False)
    try:
        beats = read_beats(job.dat_path)
        cues = read_hot_cues(extended_path(job.dat_path))
        if not beats and not cues:
            return AnalysisTrackResult(job.raw, None, None, False)
        wrote = write_track_tags(job.audio_path, beats, cues)
    except (AnlzError, TagFormatError, OSError, binascii.Error) as exc:
        return AnalysisTrackResult(job.raw, str(exc), None, False)
    analysis = None
    if wrote and beats:
        analysis = TrackAnalysis(bpm=beats[0].bpm, key=job.key)
    return AnalysisTrackResult(job.raw, None, analysis, bool(wrote and cues))


def run_analysis_jobs(
    jobs: Sequence[AnalysisJob],
    on_progress: SyncProgressCallback | None = None,
) -> list[AnalysisTrackResult]:
    """
    Process analysis jobs, several tracks at a time.

    Progress is emitted on this thread as each job finishes, so the TUI
    callback stays single-threaded. Completion order follows the workers,
    not playlist order.

    Args:
        jobs: Tracks to process, in playlist order.
        on_progress: Optional callback after each track finishes.

    Returns:
        One result per job, in completion order.
    """
    if not jobs:
        return []
    workers = analysis_worker_count(len(jobs))
    results: list[AnalysisTrackResult] = []
    if workers == 1:
        ordered = [process_analysis_track(job) for job in jobs]
        for done, result in enumerate(ordered, start=1):
            results.append(result)
            emit_progress(on_progress, "analysis", done, len(jobs), result.raw, result.error)
        return results

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process_analysis_track, job): job.raw for job in jobs}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done += 1
            emit_progress(on_progress, "analysis", done, len(jobs), result.raw, result.error)
    return results
