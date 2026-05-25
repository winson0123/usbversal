"""Backup orchestration for DJ library files on a mount."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from app.storage.backup import BackupResult, create_backup

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
    mount_path = Path(mount).resolve()
    files = rekordbox_files_on_mount(mount_path)
    if extra_files:
        for item in extra_files:
            path = Path(item)
            if not path.is_absolute():
                path = mount_path / path
            if path.is_file() and path not in files:
                files.append(path.resolve())

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
