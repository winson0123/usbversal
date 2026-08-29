"""Shared test fixtures."""

import os
from pathlib import Path

import pytest

from app.services.library import UsbLibrary, probe_mount


@pytest.fixture(autouse=True)
def isolate_host_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep host logs off the real user data directory.

    Production writes to ~/.local/share/usbversal (or USBVERSAL_DATA_ROOT).
    Tests must not pollute that tree.
    """
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host-data"))


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
