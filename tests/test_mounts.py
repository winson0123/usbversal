"""Tests for mount enumeration."""

from pathlib import Path
from unittest.mock import patch

from app.storage.mounts import LinuxMntScanner, get_mount_scanner


def test_linux_mnt_scanner_lists_child_directories(tmp_path: Path, monkeypatch) -> None:
    """LinuxMntScanner returns resolved child directories under /mnt."""
    (tmp_path / "usb").mkdir()
    (tmp_path / "wsl").mkdir()

    monkeypatch.setattr("app.storage.mounts.Path", lambda p: tmp_path if p == "/mnt" else Path(p))

    scanner = LinuxMntScanner()
    mounts = scanner.list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path.name == "usb"
    assert all(m.source == "linux_mnt" for m in mounts)


def test_get_mount_scanner_returns_linux_on_linux() -> None:
    """get_mount_scanner selects LinuxMntScanner on Linux."""
    with patch("app.storage.mounts.platform.system", return_value="Linux"):
        scanner = get_mount_scanner()
    assert isinstance(scanner, LinuxMntScanner)
