"""Tests for mount enumeration."""

from pathlib import Path
from unittest.mock import patch

from app.core.domain import MountPoint
from app.storage.mounts import (
    LinuxMediaScanner,
    LinuxMntScanner,
    MountScanner,
    _CompositeScanner,
    get_mount_scanner,
)


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


def test_linux_media_scanner_lists_child_directories_under_current_user(
    tmp_path: Path, monkeypatch
) -> None:
    """LinuxMediaScanner returns resolved child directories under
    /media/$USER -- where udisks2/gvfs auto-mounts a stick on a real
    desktop Linux session."""
    (tmp_path / "someuser" / "MY_USB").mkdir(parents=True)
    (tmp_path / "someuser" / ".hidden").mkdir()

    monkeypatch.setattr("app.storage.mounts.getpass.getuser", lambda: "someuser")
    monkeypatch.setattr("app.storage.mounts.Path", lambda p: tmp_path if p == "/media" else Path(p))

    scanner = LinuxMediaScanner()
    mounts = scanner.list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path.name == "MY_USB"
    assert mounts[0].source == "linux_media"


def test_linux_media_scanner_returns_empty_when_media_root_is_absent(monkeypatch) -> None:
    """No /media/$USER at all (no desktop auto-mounter) is not an error."""
    monkeypatch.setattr("app.storage.mounts.getpass.getuser", lambda: "nobody-such-user")

    scanner = LinuxMediaScanner()

    assert scanner.list_mounts() == []


def test_composite_scanner_merges_all_sub_scanners() -> None:
    """_CompositeScanner concatenates every sub-scanner's mounts."""

    class _Fixed(MountScanner):
        def __init__(self, mounts):
            self._mounts = mounts

        def list_mounts(self):
            return self._mounts

    a = MountPoint(path=Path("/a"), source="one")
    b = MountPoint(path=Path("/b"), source="two")
    scanner = _CompositeScanner([_Fixed([a]), _Fixed([b])])

    assert scanner.list_mounts() == [a, b]


def test_get_mount_scanner_returns_a_composite_on_linux() -> None:
    """get_mount_scanner checks both /mnt and /media/$USER on Linux."""
    with patch("app.storage.mounts.platform.system", return_value="Linux"):
        scanner = get_mount_scanner()
    assert isinstance(scanner, _CompositeScanner)
    kinds = {type(s) for s in scanner._scanners}
    assert kinds == {LinuxMntScanner, LinuxMediaScanner}
