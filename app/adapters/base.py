"""Adapter protocols and shared errors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.domain import Playlist, RekordboxLibrary, SeratoCrate, SeratoLibrary


class AdapterError(Exception):
    """Base error for adapter operations."""


class UnsupportedDatabaseError(AdapterError):
    """Raised when the on-disk format is not supported for the requested operation."""


class DatabaseNotFoundError(AdapterError):
    """Raised when no vendor database file can be resolved."""


class SeratoLibraryNotFoundError(DatabaseNotFoundError):
    """Raised when no _Serato_ library exists on the mount."""


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
