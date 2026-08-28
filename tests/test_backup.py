"""Tests for backup copy and manifest."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.adapters.serato.library_db import library_db_path
from app.services.backup_service import (
    backup_mount_for_migration,
    backup_mount_libraries,
    rekordbox_files_on_mount,
    serato_files_on_mount,
)
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


def _serato_mount(tmp_path: Path, *, with_index: bool) -> Path:
    """A mount with a minimal Serato library, optionally with location.sqlite."""
    mount = tmp_path / "usb"
    serato = mount / "_Serato_"
    serato.mkdir(parents=True)
    (serato / "database V2").write_bytes(b"vrsn\x00\x00\x00\x00")
    if with_index:
        index = library_db_path(serato)
        index.parent.mkdir(parents=True)
        index.write_bytes(b"sqlite-stub")
    return mount


def test_serato_files_on_mount_includes_the_library_index(tmp_path: Path) -> None:
    """location.sqlite is backed up alongside database V2 when present."""
    mount = _serato_mount(tmp_path, with_index=True)

    files = serato_files_on_mount(mount)

    assert library_db_path(mount / "_Serato_") in files


def test_serato_files_on_mount_tolerates_no_index(tmp_path: Path) -> None:
    """A stick with no location.sqlite yet is not an error."""
    mount = _serato_mount(tmp_path, with_index=False)

    files = serato_files_on_mount(mount)

    assert (mount / "_Serato_" / "database V2") in files
    assert not any(f.name == "location.sqlite" for f in files)


def test_backup_mount_for_migration_includes_extra_files(tmp_path: Path) -> None:
    """Extra files, such as audio about to be tagged, join the backup set."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"x")
    audio = mount / "Contents" / "track.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"audio")

    result = backup_mount_for_migration(
        mount, extra_files=[audio], backup_root=tmp_path / "host-backups"
    )

    assert any(f.relative_path == "Contents/track.wav" for f in result.manifest.files)


def test_create_backup_disambiguates_a_same_second_collision(tmp_path: Path) -> None:
    """Two auto-id backups within the same second get distinct directories."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"content")
    backups_root = tmp_path / "backups"
    # Pre-occupy the id this second would generate, forcing the collision
    # deterministically rather than relying on two real calls landing in the
    # same wall-clock second.
    stem = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (backups_root / stem).mkdir(parents=True)

    result = create_backup(source_mount=mount, files=[db], backup_root=backups_root)

    assert result.backup_id == f"{stem}-2"
    assert result.backup_dir == backups_root / f"{stem}-2"


def test_create_backup_with_an_explicit_id_still_raises_on_collision(tmp_path: Path) -> None:
    """An explicit backup_id is caller intent -- a collision there is a real error."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    db = rb / "exportLibrary.db"
    db.write_bytes(b"content")
    backups_root = tmp_path / "backups"

    create_backup(source_mount=mount, files=[db], backup_root=backups_root, backup_id="fixed")

    with pytest.raises(FileExistsError):
        create_backup(source_mount=mount, files=[db], backup_root=backups_root, backup_id="fixed")


def test_backup_mount_for_migration_ignores_missing_extra_files(tmp_path: Path) -> None:
    """An extra file that does not exist is skipped rather than failing the backup."""
    mount = tmp_path / "usb"
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"x")

    result = backup_mount_for_migration(
        mount,
        extra_files=[mount / "Contents" / "ghost.wav"],
        backup_root=tmp_path / "host-backups",
    )

    assert len(result.manifest.files) == 1
