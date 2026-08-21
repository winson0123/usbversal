"""Adapter protocols and shared errors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.core.domain import Playlist, RekordboxLibrary, SeratoCrate, SeratoLibrary
from app.storage.backup import BackupManifest
from app.storage.rollback import verify_backup_integrity


class AdapterError(Exception):
    """Base error for adapter operations."""


class UnsupportedDatabaseError(AdapterError):
    """Raised when the on-disk format is not supported for the requested operation."""


class DatabaseNotFoundError(AdapterError):
    """Raised when no vendor database file can be resolved."""


class SeratoLibraryNotFoundError(DatabaseNotFoundError):
    """Raised when no _Serato_ library exists on the mount."""


@dataclass(frozen=True)
class WriteContext:
    """
    Proof that a verified backup exists, required for any write operation.

    Construction is the gate: a context cannot be built unless ``backup_path`` is
    a real backup directory whose manifest loads and whose recorded files match
    on the filesystem. Holding an instance therefore means a rollback is possible.

    Attributes:
        backup_path: Backup directory containing manifest.json and file copies.
        verify_contents: Re-hash every manifest entry (default). Set False only
            where the caller has already verified the same directory.

    Raises:
        ValueError: If backup_path is not a directory or has no readable manifest.
        BackupVerificationError: If a manifest entry is missing or fails
            checksum/size verification.
    """

    backup_path: Path
    verify_contents: bool = True

    def __post_init__(self) -> None:
        """Verify that backup_path is a usable, intact backup."""
        if not self.backup_path.is_dir():
            msg = f"WriteContext requires an existing backup directory: {self.backup_path}"
            raise ValueError(msg)

        manifest_path = self.backup_path / "manifest.json"
        if not manifest_path.is_file():
            msg = f"WriteContext requires a backup manifest: {manifest_path}"
            raise ValueError(msg)

        try:
            manifest = BackupManifest.load(self.backup_path)
        except (OSError, ValueError, KeyError) as exc:
            msg = f"WriteContext could not read backup manifest {manifest_path}: {exc}"
            raise ValueError(msg) from exc

        if not manifest.files:
            msg = f"WriteContext requires a non-empty backup manifest: {manifest_path}"
            raise ValueError(msg)

        if self.verify_contents:
            verify_backup_integrity(self.backup_path, manifest)


class RekordboxReadAdapter(ABC):
    """Read-only Rekordbox adapter interface."""

    @abstractmethod
    def list_playlists(self) -> list[Playlist]:
        """
        Return all playlist and folder nodes from the library.

        Returns:
            Flat list of Playlist entries with parent_id linkage.
        """

    @property
    @abstractmethod
    def library(self) -> RekordboxLibrary:
        """Return metadata about the opened library."""


class SeratoReadAdapter(ABC):
    """Read-only Serato adapter interface."""

    @abstractmethod
    def list_crates(self) -> list[SeratoCrate]:
        """
        List crate files and their track counts.

        Returns:
            SeratoCrate entries for each .crate under Subcrates/.
        """

    @property
    @abstractmethod
    def library(self) -> SeratoLibrary:
        """Return metadata about the opened Serato library."""
