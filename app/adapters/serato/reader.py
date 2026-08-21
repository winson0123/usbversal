"""Serato read adapter using serato-tools."""

from __future__ import annotations

from pathlib import Path

import structlog
from serato_tools.crate import Crate
from serato_tools.database_v2 import DatabaseV2

from app.adapters.base import SeratoLibraryNotFoundError, SeratoReadAdapter
from app.adapters.serato.paths import list_crate_files, resolve_serato_library
from app.core.domain import SeratoCrate, SeratoLibrary

logger = structlog.get_logger(__name__)


class SeratoToolsAdapter(SeratoReadAdapter):
    """Read Serato database V2 and crate files via serato-tools."""

    def __init__(self, library: SeratoLibrary, db: DatabaseV2) -> None:
        """
        Initialize adapter with opened serato-tools handles.

        Args:
            library: Resolved Serato library metadata.
            db: Open DatabaseV2 instance.
        """
        self._library = library
        self._db = db

    @property
    def library(self) -> SeratoLibrary:
        """Return Serato library metadata."""
        return self._library

    def list_crates(self) -> list[SeratoCrate]:
        """
        List all .crate files under Subcrates with track counts.

        Returns:
            Sorted SeratoCrate list by name.
        """
        crates: list[SeratoCrate] = []
        for crate_path in list_crate_files(self._library.serato_root):
            crate = Crate(str(crate_path))
            track_count = len(list(crate.get_track_paths()))
            crates.append(
                SeratoCrate(
                    name=crate_path.stem,
                    path=crate_path,
                    track_count=track_count,
                ),
            )
            logger.debug(
                "serato_crate_loaded",
                name=crate_path.stem,
                track_count=track_count,
            )
        crates.sort(key=lambda c: c.name.lower())
        logger.info("serato_crates_loaded", count=len(crates))
        return crates


def read_database_track_paths(database_path: Path) -> list[str]:
    """
    Read raw track paths from a Serato database V2 file.

    Keeps the serato-tools dependency inside the adapter layer so callers can
    build path indexes without importing vendor code.

    Args:
        database_path: Path to the `database V2` file.

    Returns:
        Track paths exactly as stored by Serato (drive-relative, no leading slash).
    """
    return list(DatabaseV2(file=str(database_path)).get_track_paths())


def open_serato_library(mount_path: Path) -> SeratoToolsAdapter:
    """
    Open a Serato library on a mount for read-only access.

    Args:
        mount_path: Mount root containing _Serato_.

    Returns:
        Configured SeratoToolsAdapter.

    Raises:
        SeratoLibraryNotFoundError: When _Serato_ or database V2 is missing.
    """
    resolved = resolve_serato_library(mount_path)
    if resolved is None:
        raise SeratoLibraryNotFoundError(
            f"No Serato library under {mount_path} (expected _Serato_/database V2)"
        )

    serato_root, database_path = resolved
    mount = mount_path.resolve()
    logger.info("opening_serato_library", path=str(database_path))
    db = DatabaseV2(file=str(database_path))
    track_count = len(list(db.get_track_paths()))
    library = SeratoLibrary(
        mount_path=mount,
        serato_root=serato_root,
        database_path=database_path,
        database_track_count=track_count,
    )
    return SeratoToolsAdapter(library, db)
