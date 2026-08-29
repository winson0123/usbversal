"""Progress samples for a backup bar, then a sync bar."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

ProgressPhase = Literal["backup", "index", "analysis", "crates"]


@dataclass(frozen=True)
class SyncProgress:
    """
    One progress sample from a backup or sync write step.

    Attributes:
        phase: Which write step this sample belongs to.
        done: Units on the current bar (backup bytes, or sync items).
        total: Units on the current bar.
        item: Track path or crate name. Empty during backup.
        error: That item's failure message, or None.
        playlist: Playlist being written, or empty during backup.
        playlist_done: Track or crate index within that playlist run.
        playlist_total: Tracks or crates in that playlist run.
    """

    phase: ProgressPhase
    done: int
    total: int
    item: str
    error: str | None = None
    playlist: str = ""
    playlist_done: int = 0
    playlist_total: int = 0


SyncProgressCallback = Callable[[SyncProgress], None]


def emit_progress(
    on_progress: SyncProgressCallback | None,
    phase: ProgressPhase,
    done: int,
    total: int,
    item: str,
    error: str | None = None,
    playlist: str = "",
    playlist_done: int = 0,
    playlist_total: int = 0,
) -> None:
    """
    Invoke ``on_progress`` when a caller supplied one.

    Args:
        on_progress: Caller callback, or None.
        phase: Which write step this sample belongs to.
        done: Units completed on the current bar.
        total: Units on the current bar.
        item: Track path or crate name. Empty during backup.
        error: That item's failure message, or None.
        playlist: Playlist being written, or empty during backup.
        playlist_done: Track or crate index within that playlist run.
        playlist_total: Tracks or crates in that playlist run.
    """
    if on_progress is not None:
        on_progress(
            SyncProgress(
                phase=phase,
                done=done,
                total=total,
                item=item,
                error=error,
                playlist=playlist,
                playlist_done=playlist_done,
                playlist_total=playlist_total,
            )
        )


def rebase_progress(
    on_progress: SyncProgressCallback | None, offset: int, run_total: int
) -> SyncProgressCallback | None:
    """
    Remap a phase's 1-based counts onto one sync-wide bar.

    Args:
        on_progress: Caller callback, or None.
        offset: Items already counted from earlier sync phases.
        run_total: Index + analysis + crate items for this run.

    Returns:
        A callback that emits run-wide ``done``/``total``, or None.
    """
    if on_progress is None:
        return None
    return lambda sample: on_progress(
        SyncProgress(
            sample.phase,
            offset + sample.done,
            run_total,
            sample.item,
            sample.error,
            sample.playlist,
            sample.playlist_done,
            sample.playlist_total,
        )
    )


def attach_playlist(
    on_progress: SyncProgressCallback | None,
    by_path: dict[str, tuple[str, int, int]],
) -> SyncProgressCallback | None:
    """
    Fill playlist ``x/x`` on samples whose item is a track path.

    Args:
        on_progress: Caller callback, or None.
        by_path: Track path -> (playlist name, done, total).

    Returns:
        A callback that copies playlist fields from ``by_path``, or None.
    """
    if on_progress is None:
        return None

    def wrapped(sample: SyncProgress) -> None:
        name, done, total = by_path.get(sample.item, ("", 0, 0))
        on_progress(
            SyncProgress(
                sample.phase,
                sample.done,
                sample.total,
                sample.item,
                sample.error,
                name,
                done,
                total,
            )
        )

    return wrapped


def playlist_path_meta(
    playlists: Sequence[tuple[str, Sequence[str]]],
    wanted: set[str],
) -> tuple[list[str], dict[str, tuple[str, int, int]]]:
    """
    Order wanted paths by playlist, and map each to ``name, x, y``.

    Args:
        playlists: (playlist name, track paths) in selection order.
        wanted: Paths that will emit progress in this phase.

    Returns:
        Those paths in playlist order, and playlist ``x/y`` per path.
    """
    ordered: list[str] = []
    meta: dict[str, tuple[str, int, int]] = {}
    for name, paths in playlists:
        targets = [path for path in paths if path in wanted]
        count = len(targets)
        for index, path in enumerate(targets, start=1):
            if path not in meta:
                meta[path] = (name, index, count)
                ordered.append(path)
    for path in wanted:
        if path not in meta:
            ordered.append(path)
    return ordered, meta


def display_title(path: str) -> str:
    """
    Return a short title for a track path.

    Args:
        path: Rekordbox or Serato track path.

    Returns:
        The filename without its directory. Empty input stays empty.
    """
    if not path:
        return ""
    name = path.rsplit("/", 1)[-1]
    return name.rsplit("\\", 1)[-1]
