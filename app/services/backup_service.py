"""Backup orchestration for DJ library files on a mount."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from app.adapters.serato.paths import list_crate_files, resolve_serato_library
from app.storage.backup import BackupResult, create_backup
from app.storage.mounts import resolve_mount_path

logger = structlog.get_logger(__name__)

# Rekordbox export files to include in default USB backups.
_REKORDBOX_BACKUP_RELATIVE = (
    "PIONEER/rekordbox/exportLibrary.db",
    "PIONEER/rekordbox/export.pdb",
    "PIONEER/rekordbox/exportExt.pdb",
)


def rekordbox_files_on_mount(mount_path: Path) -> list[Path]:
    """
    Resolve existing Rekordbox database files under a mount.

    Args:
        mount_path: USB or library root (e.g. /mnt/usb).

    Returns:
        List of absolute paths that exist on disk.
    """
    mount = mount_path.resolve()
    found: list[Path] = []
    for relative in _REKORDBOX_BACKUP_RELATIVE:
        candidate = mount / relative
        if candidate.is_file():
            found.append(candidate)
    return found


def serato_files_on_mount(mount_path: Path) -> list[Path]:
    """
    Resolve Serato database and crate files under a mount for backup.

    Args:
        mount_path: USB or library root (e.g. /mnt/usb).

    Returns:
        List of absolute paths that exist on disk.
    """
    mount = mount_path.resolve()
    resolved = resolve_serato_library(mount)
    if resolved is None:
        return []
    serato_root, database_path = resolved
    found: list[Path] = [database_path]
    for crate_path in list_crate_files(serato_root):
        if crate_path.is_file() and crate_path not in found:
            found.append(crate_path)
    return found


def backup_mount_for_migration(
    mount: str | Path,
    *,
    backup_root: str | Path | None = None,
) -> BackupResult:
    """
    Back up Rekordbox and Serato library files before a cross-vendor write.

    Args:
        mount: Mount path containing both libraries.
        backup_root: Optional parent directory for backups (default: mount/backups).

    Returns:
        BackupResult with manifest covering all copied files.

    Raises:
        FileNotFoundError: If neither vendor has files to back up.
        ValueError: If the combined file list is empty.
    """
    mount_path = resolve_mount_path(mount)
    files = rekordbox_files_on_mount(mount_path) + serato_files_on_mount(mount_path)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    if not unique:
        msg = f"No Rekordbox or Serato library files found under {mount_path}"
        raise FileNotFoundError(msg)
    logger.info(
        "backup_migration_started",
        mount=str(mount_path),
        file_count=len(unique),
    )
    root = Path(backup_root).resolve() if backup_root else None
    return create_backup(source_mount=mount_path, files=unique, backup_root=root)


def backup_mount_libraries(
    mount: str | Path,
    *,
    backup_root: str | Path | None = None,
    extra_files: list[str | Path] | None = None,
) -> BackupResult:
    """
    Back up Rekordbox library files from a mount (read-only copy).

    Args:
        mount: Mount path containing PIONEER/rekordbox exports.
        backup_root: Optional parent directory for backups (default: mount/backups).
        extra_files: Additional absolute or mount-relative files to include.

    Returns:
        BackupResult with manifest and backup directory path.

    Raises:
        FileNotFoundError: If no Rekordbox files exist on the mount.
        ValueError: If the file list ends up empty.
    """
    mount_path = resolve_mount_path(mount)
    files = rekordbox_files_on_mount(mount_path)
    if extra_files:
        for item in extra_files:
            path = Path(item)
            if not path.is_absolute():
                path = mount_path / path
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved not in files:
                files.append(resolved)

    if not files:
        msg = f"No Rekordbox database files found under {mount_path}"
        raise FileNotFoundError(msg)

    logger.info("backup_mount_started", mount=str(mount_path), file_count=len(files))
    root = Path(backup_root).resolve() if backup_root else None
    return create_backup(source_mount=mount_path, files=files, backup_root=root)


def backup_result_to_dict(result: BackupResult) -> dict[str, Any]:
    """
    Convert BackupResult to JSON-serializable dict.

    Args:
        result: Completed backup operation.

    Returns:
        Dict with backup_id, paths, and manifest summary.
    """
    return {
        "backup_id": result.backup_id,
        "backup_dir": str(result.backup_dir),
        "source_mount": result.manifest.source_mount,
        "file_count": len(result.manifest.files),
        "files": [entry.relative_path for entry in result.manifest.files],
        "manifest_path": str(result.backup_dir / "manifest.json"),
    }
