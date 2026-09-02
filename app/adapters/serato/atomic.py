"""Flushed replace for small Serato metadata files."""

from __future__ import annotations

import os
import platform
import threading
from pathlib import Path

_FSYNC_LOCK = threading.Lock()


def fsync_fd(fd: int) -> None:
    """
    Flush an open file descriptor to the device.

    On Windows, ``os.fsync`` can raise ``[Errno 9] Bad file descriptor``
    when several threads flush USB files at once (crate writes beside
    analysis tag writes). A process lock keeps those calls serial.
    Callers must hold an open handle opened for writing or read/write.

    Args:
        fd: Descriptor returned by ``open``, ``Path.open``, or ``os.open``.

    Raises:
        OSError: The flush failed.
    """
    if platform.system() == "Windows":
        with _FSYNC_LOCK:
            os.fsync(fd)
        return
    os.fsync(fd)


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
            fsync_fd(handle.fileno())
        if temporary.stat().st_size != len(data):
            raise OSError("temporary write was truncated")
        temporary.replace(target)
        fsync_replaced(target)
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


def fsync_replaced(path: Path) -> None:
    """
    Fsync ``path`` and its parent after a replace.

    On exFAT the swap is not atomic. The new file and the directory
    entry must both reach the device. On Windows the parent directory
    is skipped; ``flush_mount`` handles the volume.

    Args:
        path: File that was just replaced.
    """
    if platform.system() == "Windows":
        with path.open("r+b") as handle:
            handle.flush()
            fsync_fd(handle.fileno())
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        fsync_fd(fd)
    finally:
        os.close(fd)
    try:
        parent = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        fsync_fd(parent)
    except OSError:
        return
    finally:
        os.close(parent)


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
        fsync_fd(handle.fileno())
