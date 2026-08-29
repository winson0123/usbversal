"""Tests for flushing a USB mount after writes."""

from __future__ import annotations

import os
from pathlib import Path

from app.adapters.serato.atomic import replace_flushed
from app.storage.mounts import flush_mount


def test_flush_mount_syncs_the_directory(tmp_path: Path, monkeypatch) -> None:
    """flush_mount opens the mount and calls syncfs when the attribute exists."""
    seen: list[int] = []

    def _syncfs(fd: int) -> None:
        seen.append(fd)

    monkeypatch.setattr(os, "syncfs", _syncfs, raising=False)
    flush_mount(tmp_path)
    assert seen, "syncfs must run on the mount directory"


def test_replace_flushed_fsyncs_the_parent_directory(tmp_path: Path, monkeypatch) -> None:
    """The directory entry from replace must be fsynced, not only the file."""
    target = tmp_path / "database V2"
    fsynced: list[int] = []
    real_fsync = os.fsync

    def _fsync(fd: int) -> None:
        fsynced.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", _fsync)
    replace_flushed(target, b"payload")
    assert target.read_bytes() == b"payload"
    assert len(fsynced) >= 2
