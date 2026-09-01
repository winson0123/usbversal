"""Per-track crate and analysis verdict used by the Library screen."""

from __future__ import annotations

from pathlib import Path

from app.adapters.rekordbox.anlz import AnlzError, extended_path, read_beats, read_hot_cues
from app.adapters.serato.tags import TagFormatError, read_geob
from app.core.domain import SyncState
from app.core.track_paths import normalize_track_path
from app.services.track_records import RekordboxContent, RekordboxDatabase, serato_path


def contents_by_path(database: RekordboxDatabase) -> dict[str, RekordboxContent]:
    """
    Map normalized and drive-relative paths to Rekordbox content rows.

    ``MagicMock`` adapters do not stub ``get_contents``; treating a mock
    as an iterable would hang. Only a real list or tuple is walked.

    Args:
        database: Rekordbox database handle, or a test double.

    Returns:
        Path string to content row. Empty when the adapter has no contents.
    """
    fetch = getattr(database, "get_contents", None)
    if not callable(fetch):
        return {}
    try:
        rows = fetch()
    except TypeError:
        return {}
    if not isinstance(rows, (list, tuple)):
        return {}
    by_path: dict[str, RekordboxContent] = {}
    for content in rows:
        raw = getattr(content, "path", None)
        if not raw:
            continue
        by_path[normalize_track_path(str(raw))] = content
        by_path[serato_path(str(raw))] = content
    return by_path


def analysis_dat_path(mount: Path, content: RekordboxContent | None) -> Path | None:
    """
    Resolve a Rekordbox track's ANLZ ``.DAT`` path on the mount.

    Args:
        mount: Mount root.
        content: rbox content row for the track, or None.

    Returns:
        Path to the ``.DAT`` file, or None when Rekordbox has not analysed it.
    """
    if content is None:
        return None
    raw = getattr(content, "analysis_data_file_path", None)
    if not raw:
        return None
    return mount / serato_path(str(raw))


def analysis_is_ported(
    mount: Path,
    raw: str,
    content: RekordboxContent | None,
    cache: dict[str, bool],
) -> bool:
    """
    Return whether Rekordbox has nothing left to write onto the audio file.

    No ANLZ, an unreadable ANLZ, or an ANLZ with neither beats nor cues
    means there is nothing to port. Otherwise the file must already carry
    ``Serato BeatGrid`` and/or ``Serato Markers2`` for what ANLZ has.

    Args:
        mount: Mount root.
        raw: Rekordbox track path (used to find the audio file).
        content: Rekordbox content row, or None.
        cache: Path-string to a previous verdict, filled by this call.

    Returns:
        True when the file is finished or there was nothing to write.
    """
    dat_path = analysis_dat_path(mount, content)
    audio_path = mount / serato_path(raw)
    cache_key = f"{dat_path!s}|{audio_path}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    ported = _analysis_is_ported(dat_path, audio_path)
    cache[cache_key] = ported
    return ported


def track_sync_state(
    *,
    in_crate: bool,
    mount: Path,
    raw: str,
    content: RekordboxContent | None,
    cache: dict[str, bool],
) -> SyncState:
    """
    Return the traffic-light colour for one playlist track.

    Red when the track is not in the crate. Yellow when it is in the
    crate but Rekordbox analysis is not on the file. Green when it is
    in the crate and analysis is on the file, or Rekordbox had nothing
    to port.

    Args:
        in_crate: Whether the crate already lists this path.
        mount: Mount root.
        raw: Rekordbox track path.
        content: Rekordbox content row, or None.
        cache: Shared analysis-ported cache.

    Returns:
        ``NOT_SYNCED``, ``PARTIAL``, or ``SYNCED``.
    """
    if not in_crate:
        return SyncState.NOT_SYNCED
    if analysis_is_ported(mount, raw, content, cache):
        return SyncState.SYNCED
    return SyncState.PARTIAL


def _analysis_is_ported(dat_path: Path | None, audio_path: Path) -> bool:
    """
    Return whether expected Serato frames are already on ``audio_path``.

    Args:
        dat_path: ANLZ ``.DAT``, or None when Rekordbox has no analysis.
        audio_path: Audio file on the mount.

    Returns:
        True when there is nothing left to write.
    """
    if dat_path is None or not dat_path.is_file():
        return True
    try:
        beats = read_beats(dat_path)
    except (AnlzError, OSError):
        return True
    try:
        cues = read_hot_cues(extended_path(dat_path))
    except (AnlzError, OSError):
        cues = []
    if not beats and not cues:
        return True
    if not audio_path.is_file():
        return False
    try:
        frames = read_geob(audio_path)
    except (TagFormatError, OSError):
        return False
    if beats and "Serato BeatGrid" not in frames:
        return False
    if cues and "Serato Markers2" not in frames:
        return False
    return True
