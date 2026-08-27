"""Tests for mount enumeration."""

from pathlib import Path
from unittest.mock import patch

from app.core.domain import MountPoint
from app.storage.mounts import (
    EnvMountScanner,
    LinuxMediaScanner,
    MacVolumesScanner,
    MountScanner,
    WindowsMountScanner,
    _CompositeScanner,
    get_mount_scanner,
)


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


def test_mac_volumes_scanner_lists_child_directories(tmp_path: Path, monkeypatch) -> None:
    """MacVolumesScanner returns resolved child directories under /Volumes,
    excluding the boot volume."""
    (tmp_path / "MY_USB").mkdir()
    (tmp_path / "Macintosh HD").mkdir()
    (tmp_path / ".hidden").mkdir()

    monkeypatch.setattr(
        "app.storage.mounts.Path", lambda p: tmp_path if p == "/Volumes" else Path(p)
    )

    scanner = MacVolumesScanner()
    mounts = scanner.list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path.name == "MY_USB"
    assert mounts[0].source == "macos_volumes"


def test_mac_volumes_scanner_returns_empty_when_volumes_root_is_absent(monkeypatch) -> None:
    """No /Volumes at all is not an error (not actually reachable on real
    macOS, but the scanner shouldn't assume it)."""
    monkeypatch.setattr("app.storage.mounts.Path", lambda p: Path("/nonexistent-root-xyz"))

    assert MacVolumesScanner().list_mounts() == []


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
    """get_mount_scanner checks /media/$USER and the env override on Linux."""
    with patch("app.storage.mounts.platform.system", return_value="Linux"):
        scanner = get_mount_scanner()
    assert isinstance(scanner, _CompositeScanner)
    kinds = {type(s) for s in scanner._scanners}
    assert kinds == {LinuxMediaScanner, EnvMountScanner}


def test_get_mount_scanner_returns_a_composite_on_macos() -> None:
    """get_mount_scanner checks /Volumes and the env override on macOS."""
    with patch("app.storage.mounts.platform.system", return_value="Darwin"):
        scanner = get_mount_scanner()
    assert isinstance(scanner, _CompositeScanner)
    kinds = {type(s) for s in scanner._scanners}
    assert kinds == {MacVolumesScanner, EnvMountScanner}


def test_get_mount_scanner_returns_a_composite_on_windows() -> None:
    """get_mount_scanner checks drive letters and the env override on Windows."""
    with patch("app.storage.mounts.platform.system", return_value="Windows"):
        scanner = get_mount_scanner()
    assert isinstance(scanner, _CompositeScanner)
    kinds = {type(s) for s in scanner._scanners}
    assert kinds == {WindowsMountScanner, EnvMountScanner}


def test_env_mount_scanner_reads_the_configured_variable(tmp_path: Path, monkeypatch) -> None:
    """A directory named by USBVERSAL_MOUNT is reported as a mount."""
    monkeypatch.setenv("USBVERSAL_MOUNT", str(tmp_path))

    mounts = EnvMountScanner().list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path == tmp_path.resolve()
    assert mounts[0].source == "env_override"


def test_env_mount_scanner_is_empty_when_unset(monkeypatch) -> None:
    """No variable set is not an error -- just nothing to report."""
    monkeypatch.delenv("USBVERSAL_MOUNT", raising=False)

    assert EnvMountScanner().list_mounts() == []


def test_env_mount_scanner_ignores_a_path_that_does_not_exist(tmp_path: Path, monkeypatch) -> None:
    """A stale or typo'd path is silently skipped, not raised."""
    monkeypatch.setenv("USBVERSAL_MOUNT", str(tmp_path / "does-not-exist"))

    assert EnvMountScanner().list_mounts() == []


def test_env_mount_scanner_uses_a_custom_variable_name(tmp_path: Path, monkeypatch) -> None:
    """The environment variable name is configurable, not hardcoded."""
    monkeypatch.setenv("MY_CUSTOM_VAR", str(tmp_path))

    mounts = EnvMountScanner(env_var="MY_CUSTOM_VAR").list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path == tmp_path.resolve()
