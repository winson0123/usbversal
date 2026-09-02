"""Tests for mount enumeration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.domain import MountPoint
from app.storage.mounts import (
    ChildDirectoryScanner,
    EnvMountScanner,
    MountScanner,
    WindowsMountScanner,
    _CompositeScanner,
    get_mount_scanner,
    mount_label_name,
)


def test_child_directory_scanner_lists_visible_children(tmp_path: Path) -> None:
    """Immediate child directories are mounts; hidden names are skipped."""
    (tmp_path / "MY_USB").mkdir()
    (tmp_path / ".hidden").mkdir()

    mounts = ChildDirectoryScanner(tmp_path, "linux_media").list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path.name == "MY_USB"
    assert mounts[0].source == "linux_media"


def test_child_directory_scanner_returns_empty_when_root_is_absent() -> None:
    """A missing root (no auto-mounter, or not this OS) is not an error."""
    scanner = ChildDirectoryScanner(Path("/nonexistent-root-xyz"), "linux_media")

    assert scanner.list_mounts() == []


def test_child_directory_scanner_skips_excluded_names(tmp_path: Path) -> None:
    """macOS /Volumes listing drops the boot volume the same way."""
    (tmp_path / "MY_USB").mkdir()
    (tmp_path / "Macintosh HD").mkdir()
    (tmp_path / ".hidden").mkdir()

    mounts = ChildDirectoryScanner(
        tmp_path,
        "macos_volumes",
        exclude=frozenset({"Macintosh HD"}),
    ).list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path.name == "MY_USB"
    assert mounts[0].source == "macos_volumes"


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


@pytest.mark.parametrize(
    ("system", "child_source", "windows"),
    [
        ("Linux", "linux_media", False),
        ("Darwin", "macos_volumes", False),
        ("Windows", None, True),
    ],
)
def test_get_mount_scanner_matches_the_platform(
    system: str, child_source: str | None, windows: bool
) -> None:
    """Each OS combines its removable-media roots with the env override."""
    with patch("app.storage.mounts.platform.system", return_value=system):
        scanner = get_mount_scanner()
    assert isinstance(scanner, _CompositeScanner)
    kinds = {type(item) for item in scanner._scanners}
    if windows:
        assert kinds == {WindowsMountScanner, EnvMountScanner}
        return
    assert kinds == {ChildDirectoryScanner, EnvMountScanner}
    child = next(item for item in scanner._scanners if isinstance(item, ChildDirectoryScanner))
    assert child._source == child_source
    if system == "Darwin":
        assert "Macintosh HD" in child._exclude


def test_env_mount_scanner_reads_the_configured_variable(tmp_path: Path, monkeypatch) -> None:
    """A directory named by USBVERSAL_MOUNT is reported as a mount."""
    monkeypatch.setenv("USBVERSAL_MOUNT", str(tmp_path))

    mounts = EnvMountScanner().list_mounts()

    assert len(mounts) == 1
    assert mounts[0].path == tmp_path.resolve()
    assert mounts[0].source == "env_override"


def test_env_mount_scanner_is_empty_when_unset(monkeypatch) -> None:
    """No variable set is not an error, just nothing to report."""
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


def test_mount_label_name_prefers_the_folder_name(tmp_path: Path) -> None:
    """Linux and macOS mounts already expose the label as the folder name."""
    mount = tmp_path / "MY_USB"
    mount.mkdir()

    assert mount_label_name(mount) == "MY_USB"


def test_mount_label_name_reads_windows_volume_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows drive letters ask the filesystem for the volume label."""
    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "app.storage.mounts._windows_mount_label",
        lambda mount: "MY_USB",
    )

    assert mount_label_name(Path("E:/")) == "MY_USB"
