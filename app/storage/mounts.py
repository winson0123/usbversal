"""Cross-platform mount point enumeration."""

import getpass
import os
import platform
import string
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.domain import MountPoint

# Manual override for a setup none of the automatic scanners cover -- an
# unusual auto-mount daemon, a container, a path the user just prefers.
MOUNT_ENV_VAR = "USBVERSAL_MOUNT"


def resolve_mount_path(mount: str | Path) -> Path:
    """
    Resolve and validate a user-supplied mount path.

    Args:
        mount: Mount path as given by the caller (e.g. /media/$USER/MY_USB).

    Returns:
        Resolved absolute path to an existing directory.

    Raises:
        FileNotFoundError: The path does not exist.
        NotADirectoryError: The path exists but is not a directory.
    """
    path = Path(mount).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Mount path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Mount path is not a directory: {path}")
    return path


class MountScanner(ABC):
    """Abstract mount enumeration strategy."""

    @abstractmethod
    def list_mounts(self) -> list[MountPoint]:
        """
        List available mount points on this system.

        Returns:
            Sorted list of MountPoint instances with normalized paths.
        """


class LinuxMediaScanner(MountScanner):
    """Enumerate auto-mounted removable media under /media/$USER.

    This is where udisks2/gvfs -- the auto-mount machinery behind most
    desktop Linux distros (GNOME, KDE, ...) -- puts a USB stick the moment
    it's plugged in, one subdirectory per device.
    """

    def list_mounts(self) -> list[MountPoint]:
        """
        Scan /media/$USER/* for directory mounts.

        Returns:
            MountPoint entries for each immediate child directory of
            /media/$USER, or an empty list if that directory doesn't exist
            (no desktop auto-mounter, or nothing currently mounted).
        """
        media_root = Path("/media") / getpass.getuser()
        if not media_root.is_dir():
            return []

        mounts: list[MountPoint] = []
        for entry in sorted(media_root.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                mounts.append(
                    MountPoint(path=entry.resolve(), source="linux_media"),
                )
        return mounts


class MacVolumesScanner(MountScanner):
    """Enumerate mounted volumes under /Volumes (macOS).

    macOS mounts every disk, including a plugged-in USB stick, as an
    immediate child of /Volumes -- no per-user subdirectory the way
    /media/$USER has one on Linux.
    """

    def list_mounts(self) -> list[MountPoint]:
        """
        Scan /Volumes/* for directory mounts.

        Returns:
            MountPoint entries for each immediate child directory of
            /Volumes, excluding the boot volume ("Macintosh HD").
        """
        volumes_root = Path("/Volumes")
        if not volumes_root.is_dir():
            return []

        mounts: list[MountPoint] = []
        for entry in sorted(volumes_root.iterdir()):
            if entry.is_dir() and not entry.name.startswith(".") and entry.name != "Macintosh HD":
                mounts.append(
                    MountPoint(path=entry.resolve(), source="macos_volumes"),
                )
        return mounts


class WindowsMountScanner(MountScanner):
    """Enumerate Windows drive letters."""

    def list_mounts(self) -> list[MountPoint]:
        """
        Return existing drive letters as mount points.

        Returns:
            MountPoint per letter A-Z where the path exists.
        """
        mounts: list[MountPoint] = []
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists():
                mounts.append(MountPoint(path=drive, source="windows_drive"))
        return mounts


class EnvMountScanner(MountScanner):
    """Mount path from the `USBVERSAL_MOUNT` environment variable.

    An escape hatch for whatever the automatic scanners don't cover --
    exists as a real, ordinary MountScanner rather than special-cased
    elsewhere, so it goes through the exact same discover-probe-open path
    (MountWatcher, then services.library.probe_mount) as anything the
    other scanners find.
    """

    def __init__(self, env_var: str = MOUNT_ENV_VAR) -> None:
        self._env_var = env_var

    def list_mounts(self) -> list[MountPoint]:
        """
        Read the configured environment variable, if set.

        Returns:
            A single MountPoint for its value, or an empty list if the
            variable is unset or doesn't point at an existing directory.
        """
        value = os.environ.get(self._env_var)
        if not value:
            return []
        path = Path(value)
        if not path.is_dir():
            return []
        return [MountPoint(path=path.resolve(), source="env_override")]


class _CompositeScanner(MountScanner):
    """Merges mount points from several scanners into one list."""

    def __init__(self, scanners: list[MountScanner]) -> None:
        self._scanners = scanners

    def list_mounts(self) -> list[MountPoint]:
        mounts: list[MountPoint] = []
        for scanner in self._scanners:
            mounts.extend(scanner.list_mounts())
        return mounts


def get_mount_scanner() -> MountScanner:
    """
    Return the platform-appropriate mount scanner.

    `USBVERSAL_MOUNT` is checked on every platform, alongside whatever the
    platform's automatic scanner finds -- for a setup it doesn't cover.

    Returns:
        MountScanner implementation for the current platform.
    """
    system = platform.system()
    if system == "Windows":
        platform_scanner: MountScanner = WindowsMountScanner()
    elif system == "Darwin":
        platform_scanner = MacVolumesScanner()
    else:
        platform_scanner = LinuxMediaScanner()
    return _CompositeScanner([platform_scanner, EnvMountScanner()])
