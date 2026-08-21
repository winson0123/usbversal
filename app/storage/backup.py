"""Backup copy utilities and manifest handling."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BackupFileEntry:
    """
    One file recorded in a backup manifest.

    Attributes:
        relative_path: Path relative to source mount root.
        sha256: Hex digest of file contents after copy.
        size: File size in bytes.
    """

    relative_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class BackupManifest:
    """
    Manifest describing a point-in-time backup.

    Attributes:
        backup_id: Unique backup identifier (timestamp-based).
        created_at: ISO-8601 UTC creation time.
        source_mount: Absolute path to the source mount root.
        files: Backed-up file entries.
    """

    backup_id: str
    created_at: str
    source_mount: str
    files: tuple[BackupFileEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize manifest to a JSON-compatible dictionary.

        Returns:
            Dict suitable for json.dumps.
        """
        return {
            "backup_id": self.backup_id,
            "created_at": self.created_at,
            "source_mount": self.source_mount,
            "files": [asdict(entry) for entry in self.files],
        }

    def write(self, backup_dir: Path) -> Path:
        """
        Write manifest.json into the backup directory.

        Args:
            backup_dir: Directory containing copied files.

        Returns:
            Path to the written manifest file.
        """
        path = backup_dir / "manifest.json"
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, backup_dir: Path) -> BackupManifest:
        """
        Load manifest.json from a backup directory.

        Args:
            backup_dir: Directory containing manifest.json.

        Returns:
            Parsed BackupManifest instance.

        Raises:
            FileNotFoundError: If manifest.json is missing.
            ValueError: If manifest JSON is invalid.
        """
        path = backup_dir / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        files = tuple(
            BackupFileEntry(
                relative_path=str(item["relative_path"]),
                sha256=str(item["sha256"]),
                size=int(item["size"]),
            )
            for item in data.get("files", [])
        )
        return cls(
            backup_id=str(data["backup_id"]),
            created_at=str(data["created_at"]),
            source_mount=str(data["source_mount"]),
            files=files,
        )


@dataclass(frozen=True)
class BackupResult:
    """
    Outcome of a backup operation.

    Attributes:
        backup_id: Identifier matching manifest and directory name.
        backup_dir: Root directory holding copies and manifest.json.
        manifest: Written manifest metadata.
    """

    backup_id: str
    backup_dir: Path
    manifest: BackupManifest


def sha256_file(path: Path) -> str:
    """
    Compute SHA-256 hex digest of a file.

    Args:
        path: File to hash.

    Returns:
        Lowercase hex digest string.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_copy_file(source: Path, destination: Path) -> None:
    """
    Copy a file atomically via a temporary sibling file.

    Args:
        source: Existing source file path.
        destination: Target file path to create or replace.

    Raises:
        OSError: On copy or rename failure.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    replaced = False
    try:
        shutil.copy2(source, temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        replaced = True
    finally:
        if not replaced:
            temporary.unlink(missing_ok=True)


def create_backup(
    *,
    source_mount: Path,
    files: list[Path],
    backup_root: Path | None = None,
    backup_id: str | None = None,
) -> BackupResult:
    """
    Copy files from a mount into a timestamped backup directory.

    Args:
        source_mount: Mount root; relative paths in manifest are from here.
        files: Absolute or mount-relative file paths to copy.
        backup_root: Parent directory for backups; defaults to mount/backups.
        backup_id: Optional directory name; defaults to UTC timestamp.

    Returns:
        BackupResult with backup_dir and manifest.

    Raises:
        FileNotFoundError: If a source file does not exist.
        ValueError: If no files are provided.
    """
    if not files:
        raise ValueError("At least one file must be specified for backup")

    mount = source_mount.resolve()
    created_at = datetime.now(UTC)
    backup_id = backup_id or created_at.strftime("%Y%m%dT%H%M%SZ")
    root = (backup_root or (mount / "backups")).resolve()
    backup_dir = root / backup_id
    backup_dir.mkdir(parents=True, exist_ok=False)

    entries: list[BackupFileEntry] = []
    for file_path in files:
        source = file_path.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Backup source not found: {source}")
        try:
            relative = source.relative_to(mount).as_posix()
        except ValueError:
            relative = source.name

        destination = backup_dir / relative
        logger.info("backup_copy", source=str(source), destination=str(destination))
        atomic_copy_file(source, destination)
        entries.append(
            BackupFileEntry(
                relative_path=relative,
                sha256=sha256_file(destination),
                size=destination.stat().st_size,
            ),
        )

    manifest = BackupManifest(
        backup_id=backup_id,
        created_at=created_at.isoformat(),
        source_mount=str(mount),
        files=tuple(entries),
    )
    manifest.write(backup_dir)
    logger.info(
        "backup_completed",
        backup_id=backup_id,
        backup_dir=str(backup_dir),
        file_count=len(entries),
    )
    return BackupResult(backup_id=backup_id, backup_dir=backup_dir, manifest=manifest)
