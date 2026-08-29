"""Progress samples for a backup bar, then a sync bar."""

from __future__ import annotations

from collections.abc import Callable
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
    """

    phase: ProgressPhase
    done: int
    total: int
    item: str
    error: str | None = None


SyncProgressCallback = Callable[[SyncProgress], None]


def emit_progress(
    on_progress: SyncProgressCallback | None,
    phase: ProgressPhase,
    done: int,
    total: int,
    item: str,
    error: str | None = None,
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
    """
    if on_progress is not None:
        on_progress(SyncProgress(phase=phase, done=done, total=total, item=item, error=error))


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
        SyncProgress(sample.phase, offset + sample.done, run_total, sample.item, sample.error)
    )
