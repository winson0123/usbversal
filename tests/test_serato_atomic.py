"""Tests for flushed Serato metadata replaces."""

import threading
from pathlib import Path

import pytest

from app.adapters.serato.atomic import fsync_fd, replace_flushed
from app.adapters.serato.paths import resolve_serato_library
from app.adapters.serato.writer import write_crate


def test_replace_flushed_writes_the_payload(tmp_path: Path) -> None:
    """A flushed replace leaves the destination equal to the payload."""
    target = tmp_path / "neworder.pref"
    payload = b"hello-pref"

    replace_flushed(target, payload)

    assert target.read_bytes() == payload


def test_replace_flushed_refuses_empty_bytes(tmp_path: Path) -> None:
    """An empty payload is not written over a live file."""
    target = tmp_path / "database V2"
    target.write_bytes(b"keep")

    with pytest.raises(OSError, match="empty"):
        replace_flushed(target, b"")

    assert target.read_bytes() == b"keep"


def test_replace_flushed_restores_when_replace_zeros_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If replace leaves a 0-byte destination, the previous bytes come back."""
    target = tmp_path / "crate.crate"
    original = b"old-crate-bytes"
    target.write_bytes(original)

    def zero_dest(self: Path, dest: Path) -> None:
        """Truncate the destination and drop the temporary file."""
        Path(dest).write_bytes(b"")
        Path(self).unlink(missing_ok=True)

    monkeypatch.setattr(Path, "replace", zero_dest)

    with pytest.raises(OSError, match="short file"):
        replace_flushed(target, b"new-crate-bytes")

    assert target.read_bytes() == original


def test_resolve_serato_library_ignores_an_empty_database(tmp_path: Path) -> None:
    """A zero-byte database V2 is not a Serato library."""
    serato = tmp_path / "_Serato_"
    serato.mkdir()
    (serato / "database V2").write_bytes(b"")

    assert resolve_serato_library(tmp_path) is None


def test_write_crate_overwrites_a_zero_byte_leftover(tmp_path: Path) -> None:
    """A dirty-unmount 0-byte crate is replaced even without overwrite."""
    serato = tmp_path / "_Serato_"
    sub = serato / "Subcrates"
    sub.mkdir(parents=True)
    leftover = sub / "Pocket.crate"
    leftover.write_bytes(b"")

    crate_path = write_crate(
        serato_root=serato,
        crate_name="Pocket",
        track_paths=["Contents/a.mp3"],
        overwrite=False,
    )

    assert crate_path == leftover
    assert crate_path.stat().st_size > 0


def test_fsync_fd_serializes_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrent Windows fsync calls must not overlap."""
    active = {"n": 0}
    peak = {"n": 0}
    lock = threading.Lock()

    def _fsync(fd: int) -> None:
        with lock:
            active["n"] += 1
            peak["n"] = max(peak["n"], active["n"])
            active["n"] -= 1

    monkeypatch.setattr("app.adapters.serato.atomic.platform.system", lambda: "Windows")
    monkeypatch.setattr("app.adapters.serato.atomic.os.fsync", _fsync)

    threads = [threading.Thread(target=fsync_fd, args=(idx,)) for idx in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak["n"] == 1
