"""Cross-platform mount point enumeration."""

from __future__ import annotations

import getpass
import os
import platform
import string
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.domain import MountPoint

# Linux BLKFLSBUF: flush the block layer so USB mass-storage finishes.
_BLKFLSBUF = 0x1261

# Manual override for a setup none of the automatic scanners cover.
# An unusual auto-mount daemon, a container, a path the user just prefers.
MOUNT_ENV_VAR = "USBVERSAL_MOUNT"


def mount_label_name(mount: Path) -> str:
    """
    Return the thumbdrive display name before Serato sanitization.

    Linux and macOS use the mount folder name (``/media/$USER/MY_USB``,
    ``/Volumes/MY_USB``). Windows reads the volume label from the
    filesystem, then falls back to the drive letter when the stick is
    unlabeled.

    Args:
        mount: Mount root of the stick.

    Returns:
        Label string, or empty when nothing could be resolved.
    """
    resolved = mount.resolve()
    if platform.system() == "Windows":
        label = _windows_mount_label(resolved)
        if label:
            return label
    folder = resolved.name.strip()
    if folder:
        return folder
    return ""


def _windows_mount_label(mount: Path) -> str:
    """
    Read a Windows drive's volume label, or its letter when unlabeled.

    Args:
        mount: Mount root such as ``E:\\``.

    Returns:
        Volume label, drive letter, or empty string when unknown.
    """
    drive = mount.resolve().drive
    if not drive:
        return ""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_errno=True)
    volume_name = ctypes.create_unicode_buffer(261)
    filesystem = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    root = f"{drive}\\"
    if kernel32.GetVolumeInformationW(
        root,
        volume_name,
        len(volume_name),
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        filesystem,
        len(filesystem),
    ):
        label = volume_name.value.strip()
        if label:
            return label
    return drive.rstrip(":").strip()


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


def flush_mount(mount: Path) -> None:
    """
    Push every dirty page on ``mount`` all the way to the device.

    File-level fsync does not flush FAT, directory, or boot-sector updates.
    Each OS has its own whole-volume flush; none of them is libc-only:

    * Linux: ``os.syncfs``, or libc ``syncfs`` when this Python build
      lacks it, then ``BLKFLSBUF`` on the block device.
    * macOS: ``F_FULLFSYNC`` on the mount directory.
    * Windows: ``FlushFileBuffers`` on the volume (``os.fsync`` of ``\\\\.\\E:``).

    Args:
        mount: Mount root that was written.

    Raises:
        OSError: The directory could not be opened or flushed.
    """
    system = platform.system()
    if system == "Windows":
        _flush_windows(Path(mount))
        return
    fd = os.open(mount, os.O_RDONLY)
    try:
        if system == "Darwin":
            _flush_macos(fd)
        else:
            _flush_linux(fd, Path(mount))
        os.fsync(fd)
    finally:
        os.close(fd)


def _flush_linux(fd: int, mount: Path) -> None:
    """
    syncfs the mount, then flush the USB block device.

    Args:
        fd: Open descriptor on the mount directory.
        mount: Mount root, used to find ``/dev/sdXN``.
    """
    _linux_syncfs(fd)
    device = _block_device_for(mount)
    if device:
        _flush_block_device(device)


def _linux_syncfs(fd: int) -> None:
    """
    Run Linux ``syncfs`` on ``fd`` via ``os`` or libc.

    Args:
        fd: Open file descriptor on the mount.
    """
    syncfs = getattr(os, "syncfs", None)
    if syncfs is not None:
        syncfs(fd)
        return
    import ctypes

    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.syncfs(fd) == 0:
        return
    os.sync()


def _flush_macos(fd: int) -> None:
    """
    Flush ``fd`` to the physical device with ``F_FULLFSYNC``.

    Args:
        fd: Open descriptor on the mount directory.
    """
    import fcntl

    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        fcntl.fcntl(fd, full)
        return
    os.fsync(fd)
    if hasattr(os, "sync"):
        os.sync()


def _flush_windows(mount: Path) -> None:
    """
    Flush the Windows volume that contains ``mount``.

    Args:
        mount: Mount root such as ``E:\\``.
    """
    drive = mount.resolve().drive
    volume = f"\\\\.\\{drive}" if drive else ""
    if not volume:
        return
    try:
        fd = os.open(volume, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        return
    finally:
        os.close(fd)


def _block_device_for(path: Path) -> str | None:
    """
    Return the block device mounted at ``path``, if any.

    Args:
        path: Directory that may be a mount point.

    Returns:
        Device path such as ``/dev/sde1``, or None.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return None
    try:
        with open("/proc/self/mounts", encoding="utf-8") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) < 2:
                    continue
                try:
                    dest = Path(parts[1]).resolve()
                except OSError:
                    continue
                if dest == resolved:
                    return parts[0]
    except OSError:
        return None
    return None


def _flush_block_device(device: str) -> None:
    """
    Ask the Linux block layer to flush ``device``.

    Args:
        device: Path such as ``/dev/sde1``. Ignored when it cannot be opened.
    """
    import fcntl

    try:
        fd = os.open(device, os.O_RDONLY)
    except OSError:
        return
    try:
        fcntl.ioctl(fd, _BLKFLSBUF)
    except OSError:
        return
    finally:
        os.close(fd)


class MountScanner(ABC):
    """Abstract mount enumeration strategy."""

    @abstractmethod
    def list_mounts(self) -> list[MountPoint]:
        """
        List available mount points on this system.

        Returns:
            Sorted list of MountPoint instances with normalized paths.
        """


class ChildDirectoryScanner(MountScanner):
    """Enumerate immediate child directories of a mount root.

    Linux auto-mounts sticks under /media/$USER; macOS uses /Volumes.
    Both are the same listing, with different roots and exclude sets.
    """

    def __init__(
        self,
        root: Path,
        source: str,
        exclude: frozenset[str] = frozenset(),
    ) -> None:
        """
        Args:
            root: Directory whose immediate children are candidate mounts.
            source: Scanner identifier stored on each MountPoint.
            exclude: Child names to skip (e.g. the macOS boot volume).
        """
        self._root = root
        self._source = source
        self._exclude = exclude

    def list_mounts(self) -> list[MountPoint]:
        """
        List child directories of ``root``, skipping hidden names and excludes.

        Returns:
            MountPoint entries, or an empty list if ``root`` is not a directory.
        """
        if not self._root.is_dir():
            return []

        mounts: list[MountPoint] = []
        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir() or entry.name.startswith(".") or entry.name in self._exclude:
                continue
            mounts.append(MountPoint(path=entry.resolve(), source=self._source))
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
    platform's automatic scanner finds, for a setup it doesn't cover.

    Returns:
        MountScanner implementation for the current platform.
    """
    system = platform.system()
    if system == "Windows":
        platform_scanner: MountScanner = WindowsMountScanner()
    elif system == "Darwin":
        # macOS mounts every disk as a child of /Volumes.
        platform_scanner = ChildDirectoryScanner(
            Path("/Volumes"),
            "macos_volumes",
            exclude=frozenset({"Macintosh HD"}),
        )
    else:
        # udisks2/gvfs on desktop Linux: /media/$USER/<device>.
        platform_scanner = ChildDirectoryScanner(
            Path("/media") / getpass.getuser(),
            "linux_media",
        )
    return _CompositeScanner([platform_scanner, EnvMountScanner()])
