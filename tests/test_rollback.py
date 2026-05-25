"""Tests for rollback from backup manifest."""

from pathlib import Path

import pytest

from app.services.rollback_service import rollback_mount_libraries
from app.storage.backup import BackupManifest, create_backup, sha256_file
from app.storage.rollback import (
    BackupNotFoundError,
    BackupVerificationError,
    MountMismatchError,
    resolve_backup_dir,
    rollback_from_backup,
    verify_backup_integrity,
)


def test_resolve_backup_dir(tmp_path: Path) -> None:
    """resolve_backup_dir finds backup folder with manifest."""
    backup_dir = tmp_path / "backups" / "20260101T120000Z"
    backup_dir.mkdir(parents=True)
    (backup_dir / "manifest.json").write_text("{}", encoding="utf-8")
    resolved = resolve_backup_dir(backup_id="20260101T120000Z", backup_root=tmp_path / "backups")
    assert resolved == backup_dir.resolve()


def test_resolve_backup_dir_missing_raises(tmp_path: Path) -> None:
    """resolve_backup_dir raises when backup id is unknown."""
    with pytest.raises(BackupNotFoundError):
        resolve_backup_dir(backup_id="missing", backup_root=tmp_path / "backups")


def test_verify_backup_integrity_detects_tampering(tmp_path: Path) -> None:
    """verify_backup_integrity fails when backup file content changes."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"original")
    result = create_backup(source_mount=mount, files=[db], backup_root=tmp_path / "backups")
    manifest = BackupManifest.load(result.backup_dir)
    tampered = result.backup_dir / manifest.files[0].relative_path
    tampered.write_bytes(b"tampered")
    with pytest.raises(BackupVerificationError):
        verify_backup_integrity(result.backup_dir, manifest)


def test_rollback_restores_files(tmp_path: Path) -> None:
    """rollback_from_backup overwrites modified files with backup copies."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"version-one")
    result = create_backup(source_mount=mount, files=[db], backup_root=tmp_path / "backups")

    db.write_bytes(b"corrupted")
    rollback = rollback_from_backup(
        source_mount=mount,
        backup_dir=result.backup_dir,
        pre_rollback=False,
    )
    assert db.read_bytes() == b"version-one"
    assert rollback.restored_paths == ("PIONEER/rekordbox/exportLibrary.db",)


def test_rollback_pre_rollback_creates_safety_copy(tmp_path: Path) -> None:
    """rollback creates an extra backup of current files when pre_rollback is enabled."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"v1")
    result = create_backup(source_mount=mount, files=[db], backup_root=tmp_path / "backups")
    db.write_bytes(b"v2-before-restore")

    rollback = rollback_from_backup(
        source_mount=mount,
        backup_dir=result.backup_dir,
        pre_rollback=True,
        backup_root=tmp_path / "backups",
    )
    assert rollback.pre_rollback_backup_dir is not None
    assert rollback.pre_rollback_backup_dir.is_dir()
    pre_manifest = BackupManifest.load(rollback.pre_rollback_backup_dir)
    pre_path = rollback.pre_rollback_backup_dir / pre_manifest.files[0].relative_path
    assert pre_path.read_bytes() == b"v2-before-restore"
    assert db.read_bytes() == b"v1"


def test_rollback_mount_mismatch_raises(tmp_path: Path) -> None:
    """rollback refuses when manifest source_mount differs from target mount."""
    mount_a = tmp_path / "usb-a"
    mount_b = tmp_path / "usb-b"
    rb = mount_a / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"x")
    result = create_backup(source_mount=mount_a, files=[db], backup_root=tmp_path / "backups")

    with pytest.raises(MountMismatchError):
        rollback_from_backup(source_mount=mount_b, backup_dir=result.backup_dir, pre_rollback=False)


def test_rollback_mount_libraries_service(tmp_path: Path) -> None:
    """rollback_mount_libraries resolves backup by id under mount/backups."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"good")
    backup = create_backup(source_mount=mount, files=[db], backup_root=mount / "backups")
    db.write_bytes(b"bad")

    rollback_mount_libraries(mount, backup.backup_id, pre_rollback=False)
    assert db.read_bytes() == b"good"
    assert sha256_file(db) == backup.manifest.files[0].sha256
