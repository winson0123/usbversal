"""Tests for backup copy and manifest."""

import json
from pathlib import Path

import pytest

from app.services.backup_service import backup_mount_libraries, rekordbox_files_on_mount
from app.storage.backup import (
    BackupManifest,
    atomic_copy_file,
    create_backup,
    sha256_file,
)


def test_sha256_and_atomic_copy(tmp_path: Path) -> None:
    """atomic_copy_file produces identical content and hash."""
    source = tmp_path / "src.txt"
    source.write_text("hello backup", encoding="utf-8")
    destination = tmp_path / "nested" / "dst.txt"
    atomic_copy_file(source, destination)
    assert destination.read_text(encoding="utf-8") == "hello backup"
    assert sha256_file(source) == sha256_file(destination)


def test_create_backup_writes_manifest(tmp_path: Path) -> None:
    """create_backup copies files and writes manifest.json."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"test-db-content")

    result = create_backup(source_mount=mount, files=[db], backup_root=tmp_path / "backups")
    manifest_path = result.backup_dir / "manifest.json"
    assert manifest_path.is_file()
    loaded = BackupManifest.load(result.backup_dir)
    assert loaded.backup_id == result.backup_id
    assert len(loaded.files) == 1
    assert loaded.files[0].relative_path == "PIONEER/rekordbox/exportLibrary.db"
    assert (result.backup_dir / loaded.files[0].relative_path).read_bytes() == b"test-db-content"


def test_backup_mount_libraries(tmp_path: Path) -> None:
    """backup_mount_libraries backs up all present Rekordbox export files."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"one")
    (rb / "export.pdb").write_bytes(b"two")

    result = backup_mount_libraries(mount, backup_root=tmp_path / "store")
    assert len(result.manifest.files) == 2
    data = json.loads((result.backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert data["source_mount"] == str(mount.resolve())


def test_backup_mount_raises_when_no_files(tmp_path: Path) -> None:
    """backup_mount_libraries fails when no Rekordbox databases exist."""
    with pytest.raises(FileNotFoundError):
        backup_mount_libraries(tmp_path)


def test_rekordbox_files_on_mount_filters_missing(tmp_path: Path) -> None:
    """rekordbox_files_on_mount returns only existing paths."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"x")
    files = rekordbox_files_on_mount(mount)
    assert len(files) == 1
    assert files[0].name == "exportLibrary.db"
