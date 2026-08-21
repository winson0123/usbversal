"""Tests for atomic file copy cleanup behaviour."""

from pathlib import Path

import pytest

from app.storage import backup as backup_module
from app.storage.backup import atomic_copy_file


def test_replaces_existing_destination(tmp_path: Path) -> None:
    """A successful copy overwrites the destination and leaves no temp file."""
    source = tmp_path / "src"
    source.write_bytes(b"new")
    destination = tmp_path / "dst"
    destination.write_bytes(b"old")

    atomic_copy_file(source, destination)

    assert destination.read_bytes() == b"new"
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_copy_leaves_no_temp_when_destination_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A failed copy must not litter a .tmp beside a pre-existing destination.

    This is the rollback case: restoring over a live database file. The earlier
    cleanup guard skipped exactly this path.
    """
    source = tmp_path / "src"
    source.write_bytes(b"new")
    destination = tmp_path / "dst"
    destination.write_bytes(b"old")

    def exploding_copy(src, dst, *args, **kwargs):
        Path(dst).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(backup_module.shutil, "copy2", exploding_copy)

    with pytest.raises(OSError, match="disk full"):
        atomic_copy_file(source, destination)

    assert destination.read_bytes() == b"old"
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_copy_leaves_no_temp_when_destination_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same cleanup applies when the destination did not exist."""
    source = tmp_path / "src"
    source.write_bytes(b"new")
    destination = tmp_path / "dst"

    def exploding_copy(src, dst, *args, **kwargs):
        Path(dst).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(backup_module.shutil, "copy2", exploding_copy)

    with pytest.raises(OSError, match="disk full"):
        atomic_copy_file(source, destination)

    assert not destination.exists()
    assert not list(tmp_path.glob("*.tmp"))
