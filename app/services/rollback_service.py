"""Rollback orchestration for DJ library files on a mount."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from app.storage.rollback import (
    RollbackResult,
    resolve_backup_dir,
    rollback_from_backup,
)

logger = structlog.get_logger(__name__)


def rollback_mount_libraries(
    mount: str | Path,
    backup_id: str,
    *,
    backup_root: str | Path | None = None,
    pre_rollback: bool = True,
) -> RollbackResult:
    """
    Restore library files on a mount from a prior backup.

    Args:
        mount: Mount path (e.g. /mnt/usb).
        backup_id: Backup directory name under backups/ (e.g. 20260525T075946Z).
        backup_root: Parent of backup dirs; default <mount>/backups.
        pre_rollback: Copy current files before overwriting.

    Returns:
        RollbackResult with restored relative paths.

    Raises:
        BackupNotFoundError: If backup_id directory or manifest is missing.
        BackupVerificationError: If backup integrity check fails.
        MountMismatchError: If manifest was created for a different mount.
    """
    mount_path = Path(mount).resolve()
    root = Path(backup_root).resolve() if backup_root else (mount_path / "backups")
    logger.info(
        "rollback_mount_started",
        mount=str(mount_path),
        backup_id=backup_id,
        backup_root=str(root),
    )
    backup_dir = resolve_backup_dir(backup_id=backup_id, backup_root=root)
    result = rollback_from_backup(
        source_mount=mount_path,
        backup_dir=backup_dir,
        pre_rollback=pre_rollback,
        backup_root=root,
    )
    logger.info(
        "rollback_mount_completed",
        backup_id=result.backup_id,
        restored_count=len(result.restored_paths),
    )
    return result


def rollback_result_to_dict(result: RollbackResult) -> dict[str, Any]:
    """
    Convert RollbackResult to a JSON-serializable dict.

    Args:
        result: Completed rollback operation.

    Returns:
        Dict with backup_id, paths, and restore summary.
    """
    return {
        "backup_id": result.backup_id,
        "backup_dir": str(result.backup_dir),
        "restored_count": len(result.restored_paths),
        "restored_paths": list(result.restored_paths),
        "pre_rollback_backup_dir": (
            str(result.pre_rollback_backup_dir) if result.pre_rollback_backup_dir else None
        ),
    }
