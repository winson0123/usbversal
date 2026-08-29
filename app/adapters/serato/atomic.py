"""Flushed replace for small Serato metadata files."""

from __future__ import annotations

import os
from pathlib import Path


def replace_flushed(target: Path, data: bytes) -> None:
    """
    Write ``data`` onto ``target`` after a flushed temporary file.

    The bytes are written to a sibling ``.tmp``, flushed and fsynced, then
    swapped over ``target``. If the destination is missing or short after
    the swap and the previous contents were non-empty, those bytes are
    written back.

    Args:
        target: Live path to replace.
        data: Complete file contents. Must not be empty.

    Raises:
        OSError: ``data`` is empty, the temporary write was truncated, the
            swap left a short file, or the write failed.
    """
    if not data:
        raise OSError("refusing to write an empty file")
    temporary = target.with_suffix(target.suffix + ".tmp")
    original = target.read_bytes() if target.is_file() and target.stat().st_size else b""
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.stat().st_size != len(data):
            raise OSError("temporary write was truncated")
        temporary.replace(target)
        _fsync_directory(target.parent)
        if target.is_file() and target.stat().st_size == len(data):
            return
        if original:
            _write_flushed(target, original)
        raise OSError("replace left a short file")
    except OSError:
        if original and (not target.is_file() or target.stat().st_size != len(original)):
            _write_flushed(target, original)
        raise
    finally:
        if temporary.is_file():
            dest_ok = target.is_file() and target.stat().st_size in {len(data), len(original)}
            if dest_ok or temporary.stat().st_size != len(data):
                temporary.unlink()


def _fsync_directory(path: Path) -> None:
    """
    Fsync ``path`` so the directory entry from a replace reaches disk.

    Args:
        path: Parent directory of the file that was replaced.
    """
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_flushed(path: Path, data: bytes) -> None:
    """
    Write ``data`` to ``path`` and fsync the file.

    Args:
        path: Destination file.
        data: Bytes to write.
    """
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
