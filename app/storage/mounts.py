"""Cross-platform mount point enumeration."""

import platform
import string
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.domain import MountPoint

# WSL/system binds that are not DJ USB targets (avoids full-drive walks).
_DEFAULT_EXCLUDED_MNT_NAMES = frozenset({"wsl", "wslg", "c"})


def resolve_mount_path(mount: str | Path) -> Path:
    """
    Resolve and validate a user-supplied mount path.

    Every mount-taking entry point routes through here so that a bad path fails
    at the boundary with a clear message, rather than surfacing later as an
    empty result or a confusing vendor-specific "database not found".

    Args:
        mount: Mount path as given by the caller (e.g. /mnt/usb).

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


class LinuxMntScanner(MountScanner):
    """Enumerate mount points under /mnt (Linux and WSL)."""

    def __init__(self, excluded_names: frozenset[str] | None = None) -> None:
        """
        Initialize scanner with optional excluded mount directory names.

        Args:
            excluded_names: Basenames under /mnt to skip (defaults to WSL/system binds).
        """
        self._excluded = (
            excluded_names if excluded_names is not None else _DEFAULT_EXCLUDED_MNT_NAMES
        )

    def list_mounts(self) -> list[MountPoint]:
        """
        Scan /mnt/* for directory mounts.

        Returns:
            MountPoint entries for each immediate child directory of /mnt,
            excluding configured system bind names.
        """
        mnt_root = Path("/mnt")
        if not mnt_root.is_dir():
            return []

        mounts: list[MountPoint] = []
        for entry in sorted(mnt_root.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                if entry.name in self._excluded:
                    continue
                mounts.append(
                    MountPoint(path=entry.resolve(), source="linux_mnt"),
                )
        return mounts


class WindowsMountScannerStub(MountScanner):
    """Stub scanner for Windows drive letters."""

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


class MacOSMountScannerStub(MountScanner):
    """Stub scanner for macOS /Volumes."""

    def list_mounts(self) -> list[MountPoint]:
        """
        List directories under /Volumes.

        Returns:
            MountPoint per volume directory.
        """
        volumes = Path("/Volumes")
        if not volumes.is_dir():
            return []

        mounts: list[MountPoint] = []
        for entry in sorted(volumes.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                mounts.append(
                    MountPoint(path=entry.resolve(), source="macos_volumes"),
                )
        return mounts


def get_mount_scanner() -> MountScanner:
    """
    Return the platform-appropriate mount scanner.

    Returns:
        MountScanner implementation for Linux, Windows, or macOS.
    """
    system = platform.system()
    if system == "Linux":
        return LinuxMntScanner()
    if system == "Windows":
        return WindowsMountScannerStub()
    if system == "Darwin":
        return MacOSMountScannerStub()
    return LinuxMntScanner()
