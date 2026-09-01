"""Errors raised on the TUI sync path."""

from app.adapters.base import (
    AdapterError,
    DatabaseNotFoundError,
    SeratoLibraryNotFoundError,
    UnsupportedDatabaseError,
)
from app.adapters.serato.writer import CrateExistsError

__all__ = [
    "AdapterError",
    "CrateExistsError",
    "DatabaseNotFoundError",
    "PlaylistNotFoundError",
    "SeratoLibraryNotFoundError",
    "SeratoLibraryRequiredError",
    "SyncError",
    "UnsupportedDatabaseError",
]


class SyncError(Exception):
    """Base error for playlist sync."""


class PlaylistNotFoundError(SyncError):
    """The selected playlist id is missing or is a folder."""


class SeratoLibraryRequiredError(SyncError):
    """The mount has no Serato library to write into."""
