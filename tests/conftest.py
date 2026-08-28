"""Shared test fixtures."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from app.services.library import UsbLibrary, probe_mount
from app.storage.backup import BackupResult, create_backup


@pytest.fixture(autouse=True)
def isolate_host_backups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep test backups off the real user data directory.

    Production writes to ~/.local/share/usbversal/backups (or
    USBVERSAL_BACKUP_ROOT). Tests must not pollute that tree.
    """
    monkeypatch.setenv("USBVERSAL_BACKUP_ROOT", str(tmp_path / "host-backups"))


INTEGRATION_MOUNT_ENV = "USBVERSAL_TEST_MOUNT"

_DB_V2_VERSION = "2.0/Serato Scratch LIVE Database".encode("utf-16-be")
EMPTY_DATABASE_V2 = b"vrsn" + len(_DB_V2_VERSION).to_bytes(4, "big") + _DB_V2_VERSION


def integration_mount() -> Path:
    """
    Return the mount integration tests run against.

    Set ``USBVERSAL_TEST_MOUNT`` to the stick root. There is no default path.

    Returns:
        Path to the mount root, or a nonexistent path if the env var is unset
        so the integration tests skip instead of probing a hardcoded location.
    """
    raw = os.environ.get(INTEGRATION_MOUNT_ENV)
    if raw:
        return Path(raw)
    return Path("/var/empty/usbversal-no-test-mount")


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


def make_library(mount: Path, adapter: object) -> UsbLibrary:
    """
    Build a UsbLibrary around a stubbed Rekordbox adapter.

    Args:
        mount: Mount root that already contains the expected vendor paths.
        adapter: Object standing in for the Rekordbox read adapter.

    Returns:
        UsbLibrary usable by services that take a session handle.
    """
    probe = probe_mount(mount)
    assert probe is not None, f"probe found nothing at {mount}"
    return UsbLibrary(probe=probe, rekordbox=adapter)  # type: ignore[arg-type]
