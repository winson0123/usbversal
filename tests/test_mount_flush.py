"""Tests for flushing a USB mount after writes."""

from __future__ import annotations

import os
from pathlib import Path

from app.adapters.serato.atomic import replace_flushed
from app.storage.mounts import flush_mount


def test_flush_mount_syncs_the_directory(tmp_path: Path, monkeypatch) -> None:
    """On Linux, flush_mount calls os.syncfs when the attribute exists."""
    seen: list[int] = []

    def _syncfs(fd: int) -> None:
        seen.append(fd)

    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Linux")
    monkeypatch.setattr(os, "syncfs", _syncfs, raising=False)
    flush_mount(tmp_path)
    assert seen, "syncfs must run on the mount directory"


def test_flush_mount_uses_libc_when_os_has_no_syncfs(tmp_path: Path, monkeypatch) -> None:
    """Linux without os.syncfs still calls libc.syncfs, not a PyPI package."""
    seen: list[int] = []

    class _Libc:
        def syncfs(self, fd: int) -> int:
            seen.append(fd)
            return 0

    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Linux")
    monkeypatch.delattr(os, "syncfs", raising=False)
    monkeypatch.setattr(
        "ctypes.CDLL",
        lambda name, use_errno=True: _Libc(),
    )
    flush_mount(tmp_path)
    assert seen, "libc.syncfs must run when os.syncfs is missing"


def test_flush_mount_uses_fullfsync_on_macos(tmp_path: Path, monkeypatch) -> None:
    """macOS flush is F_FULLFSYNC, not Linux syncfs."""
    seen: list[int] = []

    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Darwin")

    def _fcntl(fd: int, cmd: int) -> int:
        seen.append(cmd)
        return 0

    fake_fcntl = type("fcntl", (), {"F_FULLFSYNC": 51, "fcntl": staticmethod(_fcntl)})
    monkeypatch.setitem(__import__("sys").modules, "fcntl", fake_fcntl)
    flush_mount(tmp_path)
    assert seen == [51]


def test_flush_mount_dispatches_to_the_windows_volume_flush(tmp_path: Path, monkeypatch) -> None:
    """Windows uses the volume FlushFileBuffers path, not libc.syncfs."""
    called: list[Path] = []
    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Windows")
    monkeypatch.setattr("app.storage.mounts._flush_windows", called.append)
    flush_mount(tmp_path)
    assert called == [tmp_path]


def test_flush_windows_opens_the_volume_device(tmp_path: Path, monkeypatch) -> None:
    """The Windows helper fsyncs \\\\.\\E: (FlushFileBuffers)."""
    opened: list[str] = []
    from app.storage.mounts import _flush_windows

    monkeypatch.setattr(
        Path,
        "resolve",
        lambda self: type("Resolved", (), {"drive": "E:"})(),
    )

    def _open(path, flags, *args):
        opened.append(str(path))
        return 99

    monkeypatch.setattr(os, "open", _open)
    monkeypatch.setattr(os, "fsync", lambda fd: None)
    monkeypatch.setattr(os, "close", lambda fd: None)
    _flush_windows(tmp_path)
    assert opened == ["\\\\.\\E:"]


def test_replace_flushed_fsyncs_the_parent_directory(tmp_path: Path, monkeypatch) -> None:
    """The directory entry from replace must be fsynced, not only the file."""
    target = tmp_path / "database V2"
    fsynced: list[int] = []
    real_fsync = os.fsync

    def _fsync(fd: int) -> None:
        fsynced.append(fd)
        real_fsync(fd)

    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Linux")
    monkeypatch.setattr("app.adapters.serato.atomic.platform.system", lambda: "Linux")
    monkeypatch.setattr(os, "fsync", _fsync)
    replace_flushed(target, b"payload")
    assert target.read_bytes() == b"payload"
    assert len(fsynced) >= 2


def test_fsync_replaced_on_windows_skips_the_parent_directory(tmp_path: Path, monkeypatch) -> None:
    """Windows flushes the live file only; volume flush covers the directory."""
    target = tmp_path / "child.crate"
    target.write_bytes(b"crate")
    opened: list[str] = []

    def _open(path, flags, *args):
        opened.append(str(path))
        return 99

    monkeypatch.setattr("app.adapters.serato.atomic.platform.system", lambda: "Windows")
    monkeypatch.setattr(os, "open", _open)
    monkeypatch.setattr(os, "fsync", lambda fd: None)
    monkeypatch.setattr(os, "close", lambda fd: None)

    from app.adapters.serato.atomic import fsync_replaced

    fsync_replaced(target)
    assert opened == []
