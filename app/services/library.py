"""Mount probing and the per-session library handle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.adapters.base import RekordboxReadAdapter, UnsupportedDatabaseError
from app.adapters.rekordbox import open_rekordbox_library
from app.adapters.rekordbox.paths import resolve_rekordbox_database
from app.adapters.serato.paths import resolve_serato_library
from app.core.domain import RekordboxDbFormat
from app.services.bootstrap_service import bootstrap_serato_library
from app.storage.mount_watch import MountChange, MountChangeKind, MountWatcher
from app.storage.mounts import resolve_mount_path

__all__ = [
    "MountChange",
    "MountChangeKind",
    "MountProbe",
    "MountWatcher",
    "UsbLibrary",
    "open_library",
    "prepare_library",
    "probe_mount",
]

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class MountProbe:
    """
    Cheap, stat-only verdict about what sits on a mount.

    Attributes:
        mount: Resolved mount root.
        rekordbox_database: Path to the Rekordbox export, when present.
        rekordbox_format: Detected Rekordbox database format.
        serato_root: Path to _Serato_, when present.
        serato_database: Path to database V2, when present.
    """

    mount: Path
    rekordbox_database: Path | None
    rekordbox_format: RekordboxDbFormat | None
    serato_root: Path | None
    serato_database: Path | None

    @property
    def is_dj_usb(self) -> bool:
        """Whether a Rekordbox export was found."""
        return self.rekordbox_database is not None

    @property
    def is_supported(self) -> bool:
        """Whether the Rekordbox format can be read."""
        return self.rekordbox_format is RekordboxDbFormat.ONE_LIBRARY

    @property
    def has_serato(self) -> bool:
        """Whether a Serato library already exists on the mount."""
        return self.serato_database is not None

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the probe for JSON output.

        Returns:
            JSON-friendly dict describing the mount.
        """
        return {
            "mount": str(self.mount),
            "is_dj_usb": self.is_dj_usb,
            "is_supported": self.is_supported,
            "has_serato": self.has_serato,
            "rekordbox_database": (
                str(self.rekordbox_database) if self.rekordbox_database else None
            ),
            "rekordbox_format": (self.rekordbox_format.value if self.rekordbox_format else None),
            "serato_root": str(self.serato_root) if self.serato_root else None,
            "serato_database": str(self.serato_database) if self.serato_database else None,
        }


def probe_mount(mount: str | Path) -> MountProbe | None:
    """
    Identify what DJ library sits on a mount without opening any database.

    Only stats a handful of known paths, so it is cheap enough to poll while
    waiting for a stick to appear.

    Args:
        mount: Mount path to inspect.

    Returns:
        MountProbe, or None when the path is absent or holds nothing -- an
        unplugged stick leaves its mount point behind as an empty directory.
    """
    path = Path(mount).resolve()
    if not path.is_dir() or not any(path.iterdir()):
        return None

    rekordbox = resolve_rekordbox_database(path)
    serato = resolve_serato_library(path)
    return MountProbe(
        mount=path,
        rekordbox_database=rekordbox[0] if rekordbox else None,
        rekordbox_format=rekordbox[1] if rekordbox else None,
        serato_root=serato[0] if serato else None,
        serato_database=serato[1] if serato else None,
    )


@dataclass
class UsbLibrary:
    """
    An opened DJ library, held for the lifetime of a session.

    Opening the Rekordbox export dominates load time, so callers open once and
    pass this handle around rather than re-resolving a mount path per operation.

    Attributes:
        probe: The mount verdict this handle was opened from.
        rekordbox: Opened read-only Rekordbox adapter.
    """

    probe: MountProbe
    rekordbox: RekordboxReadAdapter

    @property
    def mount(self) -> Path:
        """Resolved mount root."""
        return self.probe.mount

    @property
    def serato_root(self) -> Path | None:
        """Path to _Serato_, or None when the stick has no Serato library yet."""
        return self.probe.serato_root

    @property
    def serato_database(self) -> Path | None:
        """Path to database V2, or None when absent."""
        return self.probe.serato_database


def open_library(mount: str | Path) -> UsbLibrary:
    """
    Open the DJ library on a mount for the duration of a session.

    Args:
        mount: Mount path containing a Rekordbox export.

    Returns:
        UsbLibrary holding an opened Rekordbox adapter.

    Raises:
        FileNotFoundError: Mount path does not exist.
        NotADirectoryError: Mount path is not a directory.
        DatabaseNotFoundError: No Rekordbox database on the mount.
        UnsupportedDatabaseError: Rekordbox format cannot be read.
    """
    path = resolve_mount_path(mount)
    probe = probe_mount(path)
    if probe is None or not probe.is_dj_usb:
        raise FileNotFoundError(f"No Rekordbox database under {path}")
    if not probe.is_supported:
        raise UnsupportedDatabaseError(
            "Classic export.pdb (DeviceSQL) is not supported. "
            "Rekordbox One Library (exportLibrary.db) is required."
        )
    logger.info("opening_library", mount=str(path), serato=probe.has_serato)
    return UsbLibrary(probe=probe, rekordbox=open_rekordbox_library(path))


def prepare_library(mount: str | Path) -> UsbLibrary:
    """
    Bootstrap Serato if needed, open the session handle, and prove it reads.

    This is the TUI session-open path: a rekordbox-only stick must get an
    empty Serato library before sync can write anywhere, and a database that
    opens but cannot list playlists must fail here rather than after the
    Library screen has already taken over. CLI callers that only need a
    read stay on ``open_library`` -- they must not create ``_Serato_``.

    Args:
        mount: Mount path containing a Rekordbox export.

    Returns:
        UsbLibrary holding an opened Rekordbox adapter, with playlists
        already listed once so a later read is not the first one.

    Raises:
        FileNotFoundError: Mount path does not exist, or no Rekordbox
            database is present to back up / open.
        NotADirectoryError: Mount path is not a directory.
        DatabaseNotFoundError: No Rekordbox database on the mount.
        UnsupportedDatabaseError: Rekordbox format cannot be read.
        OSError: The mount or database could not be read.
    """
    bootstrap_serato_library(mount)
    library = open_library(mount)
    library.rekordbox.list_playlists()
    return library
