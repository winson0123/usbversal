"""Rollback utilities: verify backups and restore files from manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from app.storage.backup import (
    BackupManifest,
    atomic_copy_file,
    create_backup,
    sha256_file,
)

logger = structlog.get_logger(__name__)


class RollbackError(Exception):
    """Base error for rollback operations."""


class BackupNotFoundError(RollbackError):
    """Raised when the requested backup directory or manifest is missing."""


class BackupVerificationError(RollbackError):
    """Raised when backup files fail checksum or size verification."""


class MountMismatchError(RollbackError):
    """Raised when manifest source_mount does not match the target mount."""


@dataclass(frozen=True)
class RollbackResult:
    """
    Outcome of a rollback operation.

    Attributes:
        backup_id: Identifier of the backup used for restore.
        backup_dir: Directory containing the backup copies.
        restored_paths: Relative paths restored onto the mount.
        pre_rollback_backup_dir: Optional safety backup of current files before restore.
    """

    backup_id: str
    backup_dir: Path
    restored_paths: tuple[str, ...]
    pre_rollback_backup_dir: Path | None = None


def resolve_backup_dir(
    *,
    backup_id: str,
    backup_root: Path,
) -> Path:
    """
    Resolve the backup directory for a backup identifier.

    Args:
        backup_id: Timestamp-based backup id (directory name).
        backup_root: Parent directory containing backup subfolders.

    Returns:
        Absolute path to the backup directory.

    Raises:
        BackupNotFoundError: If the directory does not exist.
    """
    backup_dir = backup_root.resolve() / backup_id
    if not backup_dir.is_dir():
        raise BackupNotFoundError(f"Backup not found: {backup_dir}")
    if not (backup_dir / "manifest.json").is_file():
        raise BackupNotFoundError(f"manifest.json missing in {backup_dir}")
    return backup_dir


def verify_backup_integrity(backup_dir: Path, manifest: BackupManifest) -> None:
    """
    Verify every manifest entry exists in the backup dir with matching hash and size.

    Args:
        backup_dir: Directory containing copied files and manifest.json.
        manifest: Loaded backup manifest.

    Raises:
        BackupVerificationError: If a file is missing or checksum/size mismatch.
    """
    for entry in manifest.files:
        path = backup_dir / entry.relative_path
        if not path.is_file():
            raise BackupVerificationError(f"Backup file missing: {path}")
        actual_size = path.stat().st_size
        if actual_size != entry.size:
            raise BackupVerificationError(
                f"Size mismatch for {entry.relative_path}: "
                f"expected {entry.size}, got {actual_size}",
            )
        actual_hash = sha256_file(path)
        if actual_hash != entry.sha256:
            raise BackupVerificationError(
                f"Checksum mismatch for {entry.relative_path}",
            )
    logger.info(
        "backup_integrity_verified",
        backup_id=manifest.backup_id,
        file_count=len(manifest.files),
    )


def _manifest_targets_on_mount(mount: Path, manifest: BackupManifest) -> list[Path]:
    """
    Resolve absolute paths on the mount for each manifest entry.

    Args:
        mount: Mount root path.
        manifest: Backup manifest with relative paths.

    Returns:
        List of absolute file paths (may or may not exist yet).
    """
    root = mount.resolve()
    return [root / entry.relative_path for entry in manifest.files]


def rollback_from_backup(
    *,
    source_mount: Path,
    backup_dir: Path,
    pre_rollback: bool = True,
    backup_root: Path | None = None,
) -> RollbackResult:
    """
    Restore files from a verified backup directory onto the source mount.

    Args:
        source_mount: Mount root where files should be restored.
        backup_dir: Timestamped backup directory with manifest and copies.
        pre_rollback: When True, copy current mount files to pre-rollback-<ts> first.
        backup_root: Parent for pre-rollback backup; defaults to mount/backups.

    Returns:
        RollbackResult describing restored paths and optional pre-rollback dir.

    Raises:
        BackupNotFoundError: If manifest.json is missing.
        BackupVerificationError: If backup copies fail verification.
        MountMismatchError: If manifest source_mount differs from source_mount.
        FileNotFoundError: If a backup copy file is missing during restore.
    """
    mount = source_mount.resolve()
    resolved_backup = backup_dir.resolve()
    manifest = BackupManifest.load(resolved_backup)

    if Path(manifest.source_mount).resolve() != mount:
        raise MountMismatchError(
            f"Manifest mount {manifest.source_mount!r} does not match {mount!r}",
        )

    verify_backup_integrity(resolved_backup, manifest)

    pre_dir: Path | None = None
    if pre_rollback:
        existing = [path for path in _manifest_targets_on_mount(mount, manifest) if path.is_file()]
        if existing:
            root = (backup_root or (mount / "backups")).resolve()
            pre_result = create_backup(
                source_mount=mount,
                files=existing,
                backup_root=root,
                backup_id=f"pre-rollback-{manifest.backup_id}",
            )
            pre_dir = pre_result.backup_dir
            logger.info(
                "pre_rollback_backup_created",
                backup_dir=str(pre_dir),
                file_count=len(existing),
            )

    restored: list[str] = []
    for entry in manifest.files:
        backup_copy = resolved_backup / entry.relative_path
        if not backup_copy.is_file():
            raise FileNotFoundError(f"Backup copy missing: {backup_copy}")
        target = mount / entry.relative_path
        logger.info("rollback_restore", relative=entry.relative_path, target=str(target))
        atomic_copy_file(backup_copy, target)
        restored.append(entry.relative_path)

    logger.info(
        "rollback_completed",
        backup_id=manifest.backup_id,
        restored_count=len(restored),
    )
    return RollbackResult(
        backup_id=manifest.backup_id,
        backup_dir=resolved_backup,
        restored_paths=tuple(restored),
        pre_rollback_backup_dir=pre_dir,
    )
