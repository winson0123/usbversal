"""Shared test fixtures."""

from collections.abc import Callable
from pathlib import Path

import pytest

from app.storage.backup import BackupResult, create_backup


@pytest.fixture
def make_backup(tmp_path: Path) -> Callable[..., BackupResult]:
    """
    Build a real, verifiable backup for WriteContext construction.

    WriteContext verifies the manifest and re-hashes every entry, so tests that
    exercise write paths need a genuine backup directory.

    Returns:
        Callable taking an optional mount root and returning a BackupResult.
    """

    def _make(mount: Path | None = None) -> BackupResult:
        root = mount or (tmp_path / "usb")
        source = root / "PIONEER" / "rekordbox"
        source.mkdir(parents=True, exist_ok=True)
        db = source / "exportLibrary.db"
        if not db.is_file():
            db.write_bytes(b"rekordbox database contents")
        return create_backup(
            source_mount=root,
            files=[db],
            backup_root=root / "backups",
        )

    return _make
