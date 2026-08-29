"""Failed sync items for the Done screen and the host error.log."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.services.sync_progress import display_title
from app.services.sync_service import SyncReport
from app.storage.host import host_volume_dir

_ERROR_LOG_NAME = "error.log"


@dataclass(frozen=True)
class SyncFailure:
    """
    One failed track or crate.

    Attributes:
        title: Filename or playlist name.
        path: Rekordbox path or crate stem.
        reason: Why the write failed.
    """

    title: str
    path: str
    reason: str


def _split_analysis_error(message: str) -> tuple[str, str]:
    """
    Split a ``path: reason`` analysis error.

    Args:
        message: One ``SyncReport.analysis_errors`` entry.

    Returns:
        Path and reason. The whole message is the reason when no ``: `` is present.
    """
    path, separator, reason = message.partition(": ")
    if not separator:
        return message, message
    return path, reason


def failures_from_report(report: SyncReport) -> tuple[SyncFailure, ...]:
    """
    Collect per-track and per-crate failures from a finished sync.

    Args:
        report: Outcome of ``sync_playlists``.

    Returns:
        Failures in report order: analysis tracks first, then crate writes.
    """
    items: list[SyncFailure] = []
    for message in report.analysis_errors:
        path, reason = _split_analysis_error(message)
        items.append(SyncFailure(title=display_title(path), path=path, reason=reason))
    for result in report.results:
        if result.error is None:
            continue
        items.append(
            SyncFailure(title=result.playlist_name, path=result.crate_name, reason=result.error)
        )
    return tuple(items)


def format_failure_lines(failure: SyncFailure) -> str:
    """
    Render one failure as title, path, and reason on separate lines.

    Args:
        failure: Track or crate that did not write.

    Returns:
        Three-line block for the Done log and ``error.log``.
    """
    return f"{failure.title}\n{failure.path}\n{failure.reason}"


def write_error_log(
    mount: Path,
    failures: Sequence[SyncFailure],
) -> Path | None:
    """
    Write failures to ``error.log`` in that volume's host data directory.

    Args:
        mount: USB mount the sync ran on.
        failures: Items to record.

    Returns:
        Path written, or None when there is nothing to record.
    """
    if not failures:
        return None
    root = host_volume_dir(mount)
    root.mkdir(parents=True, exist_ok=True)
    path = root / _ERROR_LOG_NAME
    blocks = [format_failure_lines(item) for item in failures]
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path
