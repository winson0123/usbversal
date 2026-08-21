"""Shared test fixtures."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from app.storage.backup import BackupResult, create_backup

INTEGRATION_MOUNT_ENV = "USBVERSAL_TEST_MOUNT"


def integration_mount() -> Path:
    """
    Return the mount integration tests run against.

    Override with ``USBVERSAL_TEST_MOUNT`` when the stick is not at /mnt/usb.

    Returns:
        Path to the mount root.
    """
    return Path(os.environ.get(INTEGRATION_MOUNT_ENV, "/mnt/usb"))


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
