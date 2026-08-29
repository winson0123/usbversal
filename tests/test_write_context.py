"""Tests for the WriteContext backup gate."""

from pathlib import Path

import pytest

from app.adapters.base import WriteContext
from app.storage.backup import BackupManifest, resolve_artifact
from app.storage.rollback import BackupVerificationError


def test_accepts_verified_backup(make_backup) -> None:
    """A real backup produced by create_backup satisfies the gate."""
    backup = make_backup()
    ctx = WriteContext(backup_path=backup.backup_dir)
    assert ctx.backup_path == backup.backup_dir


def test_rejects_regular_file(tmp_path: Path) -> None:
    """A file is not a backup directory, even though it exists."""
    target = tmp_path / "not-a-dir"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="backup directory"):
        WriteContext(backup_path=target)


def test_rejects_directory_without_manifest(tmp_path: Path) -> None:
    """An arbitrary existing directory is not a backup."""
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ValueError, match="backup manifest"):
        WriteContext(backup_path=plain)


def test_rejects_unreadable_manifest(tmp_path: Path) -> None:
    """A manifest that is not valid JSON is rejected."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="could not read backup manifest"):
        WriteContext(backup_path=backup_dir)


def test_rejects_manifest_missing_fields(tmp_path: Path) -> None:
    """A structurally invalid manifest is rejected, not silently accepted."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="could not read backup manifest"):
        WriteContext(backup_path=backup_dir)


def test_rejects_empty_manifest(tmp_path: Path) -> None:
    """A manifest recording zero files cannot support a rollback."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    BackupManifest(
        backup_id="empty",
        created_at="2026-08-21T00:00:00Z",
        source_mount=str(tmp_path),
        files=(),
    ).write(backup_dir)
    with pytest.raises(ValueError, match="non-empty backup manifest"):
        WriteContext(backup_path=backup_dir)


def test_rejects_tampered_backup(make_backup) -> None:
    """A backup whose contents do not match the manifest is rejected."""
    backup = make_backup()
    copied = resolve_artifact(backup.backup_dir, backup.manifest.files[0])
    copied.write_bytes(b"corrupted after the fact")

    with pytest.raises(BackupVerificationError):
        WriteContext(backup_path=backup.backup_dir)


def test_rejects_backup_with_missing_file(make_backup) -> None:
    """A manifest entry with no corresponding copy is rejected."""
    backup = make_backup()
    resolve_artifact(backup.backup_dir, backup.manifest.files[0]).unlink()

    with pytest.raises(BackupVerificationError):
        WriteContext(backup_path=backup.backup_dir)
