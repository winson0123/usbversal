"""Bootstrapping an empty Serato library on a rekordbox-only stick.

Closes the gap `docs/planning/serato-index-bootstrap.md` names: on a plain
Rekordbox stick with no `_Serato_` at all, `sync_playlists` and friends raise
`SeratoLibraryRequiredError` and can do nothing. This creates the minimum a
fresh Serato install would have -- an empty index -- so the rest of the sync
path has somewhere to write.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from app.adapters.base import WriteContext
from app.adapters.serato.neworder import write_crate_order
from app.adapters.serato.paths import (
    database_v2_path,
    resolve_serato_library,
    serato_root_for,
    subcrates_dir,
)
from app.adapters.serato.writer import create_empty_database_v2
from app.services.backup_service import rekordbox_files_on_mount
from app.storage.backup import BackupResult, create_backup
from app.storage.mounts import resolve_mount_path

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BootstrapResult:
    """
    Outcome of a bootstrap attempt.

    Attributes:
        serato_root: Path to _Serato_ (created by this call, or already present).
        created: True when this call actually created a new library.
        backup_id: Backup taken before writing, None when nothing was created.
    """

    serato_root: Path
    created: bool
    backup_id: str | None


def bootstrap_serato_library(
    mount: str | Path,
    *,
    backup_root: str | Path | None = None,
) -> BootstrapResult:
    """
    Create an empty, valid Serato library on a mount that has none yet.

    Writes only inside ``_Serato_/``: the directory itself, ``Subcrates/``, an
    empty ``database V2`` (just the ``vrsn`` header), and an empty
    ``neworder.pref``. Nothing under ``PIONEER/`` or ``Contents/`` is ever
    touched. A mount that already has a Serato library is left completely
    alone and reported as not created -- this only fills a gap, it never
    merges into or replaces something that exists.

    Args:
        mount: Mount path containing a Rekordbox export.
        backup_root: Optional backups parent directory.

    Returns:
        BootstrapResult describing what happened.

    Raises:
        FileNotFoundError: No Rekordbox database files exist to back up, so
            there is nothing to build a verified ``WriteContext`` from.
    """
    mount_path = resolve_mount_path(mount)
    if resolve_serato_library(mount_path) is not None:
        logger.info("serato_library_already_present", mount=str(mount_path))
        return BootstrapResult(
            serato_root=serato_root_for(mount_path), created=False, backup_id=None
        )

    backup = _backup_rekordbox_files(mount_path, backup_root)
    context = WriteContext(backup_path=backup.backup_dir)
    _ = context  # validated in WriteContext.__post_init__

    serato_root = serato_root_for(mount_path)
    subcrates_dir(serato_root).mkdir(parents=True, exist_ok=True)
    create_empty_database_v2(database_v2_path(serato_root))
    write_crate_order(serato_root, [])

    logger.info(
        "serato_library_bootstrapped",
        serato_root=str(serato_root),
        backup_id=backup.backup_id,
    )
    return BootstrapResult(serato_root=serato_root, created=True, backup_id=backup.backup_id)


def _backup_rekordbox_files(mount_path: Path, backup_root: str | Path | None) -> BackupResult:
    """Back up the Rekordbox files bootstrap must never touch."""
    files = rekordbox_files_on_mount(mount_path)
    if not files:
        raise FileNotFoundError(f"No Rekordbox database files found under {mount_path}")
    root = Path(backup_root).resolve() if backup_root else None
    return create_backup(source_mount=mount_path, files=files, backup_root=root)
