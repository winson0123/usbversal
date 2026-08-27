"""Serato crate listing orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.adapters.serato import open_serato_library
from app.core.domain import SeratoCrate, SeratoLibrary
from app.storage.mounts import resolve_mount_path

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CrateListResult:
    """
    Result of a Serato crate list operation.

    Attributes:
        library: Opened Serato library metadata.
        crates: Crate files with track counts.
    """

    library: SeratoLibrary
    crates: tuple[SeratoCrate, ...]

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize to a JSON-friendly dictionary.

        Returns:
            Dict with library info and crate entries.
        """
        return {
            "library": {
                "mount_path": str(self.library.mount_path),
                "serato_root": str(self.library.serato_root),
                "database_path": str(self.library.database_path),
                "database_track_count": self.library.database_track_count,
            },
            "crates": [
                {
                    "name": c.name,
                    "path": str(c.path),
                    "track_count": c.track_count,
                }
                for c in self.crates
            ],
            "crate_count": len(self.crates),
        }


def list_serato_crates(mount: str | Path) -> CrateListResult:
    """
    List Serato crates on a mount (read-only).

    Independent of the Rekordbox session handle: reading crates is cheap and
    needs no open Rekordbox database.

    Args:
        mount: Mount path (e.g. /media/$USER/MY_USB).

    Returns:
        CrateListResult with library metadata and crates.

    Raises:
        SeratoLibraryNotFoundError: The mount has no Serato library.
    """
    adapter = open_serato_library(resolve_mount_path(mount))
    crates = tuple(adapter.list_crates())
    logger.info("list_crates_completed", crate_count=len(crates))
    return CrateListResult(library=adapter.library, crates=crates)
