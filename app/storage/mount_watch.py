"""Watching for removable media appearing and disappearing.

Built for a UI poll loop, where `storage.discovery.LibraryDiscovery`'s walk of
up to 25,000 nodes per mount is far too heavy to run every tick.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.storage.mounts import MountScanner, get_mount_scanner


class MountChangeKind(StrEnum):
    """Whether a mount point appeared or disappeared since the last poll."""

    APPEARED = "appeared"
    DISAPPEARED = "disappeared"


@dataclass(frozen=True)
class MountChange:
    """
    One mount point transition observed between two polls.

    Attributes:
        path: The mount path that changed.
        kind: Whether it appeared or disappeared.
    """

    path: Path
    kind: MountChangeKind


class MountWatcher:
    """
    Tracks which mount points are present, one cheap poll at a time.

    Each poll costs exactly one directory listing
    (``MountScanner.list_mounts``) and nothing else. No library detection,
    no database opens. What a newly appeared mount actually is (a valid DJ
    USB or not) is for the caller to find out with ``services.library.probe_mount``,
    which is itself stat-only and cheap; this class only tracks presence.
    """

    def __init__(self, scanner: MountScanner | None = None) -> None:
        """
        Args:
            scanner: Mount enumerator to poll; defaults to the platform's.
        """
        self._scanner = scanner or get_mount_scanner()
        self._known: set[Path] = set()

    def poll(self) -> tuple[MountChange, ...]:
        """
        Check which mount points appeared or disappeared since the last poll.

        The first call reports every currently present mount as appeared --
        there is no prior state to diff against.

        Returns:
            Changes observed this poll: every appearance, then every
            disappearance, each sorted by path for a stable order.
        """
        current = {mount.path for mount in self._scanner.list_mounts()}
        appeared = current - self._known
        disappeared = self._known - current
        self._known = current
        return tuple(
            MountChange(path=path, kind=MountChangeKind.APPEARED) for path in sorted(appeared)
        ) + tuple(
            MountChange(path=path, kind=MountChangeKind.DISAPPEARED) for path in sorted(disappeared)
        )
