"""Tests for the audio-file commit path that must not leave a 0-byte song."""

from pathlib import Path

import pytest

from app.adapters.serato.tags import (
    TagFormatError,
    _commit_audio_bytes,
    read_geob,
    write_geob,
)

_GEOB_MIME = b"application/octet-stream"


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _geob_frame(description: str, payload: bytes) -> bytes:
    """Build one raw ID3v2.4 GEOB frame."""
    body = b"\x00" + _GEOB_MIME + b"\x00\x00" + description.encode("latin1") + b"\x00" + payload
    return b"GEOB" + _synchsafe(len(body)) + b"\x00\x00" + body


def _mp3(frames: list[bytes], *, padding: int) -> bytes:
    """Build a minimal ID3v2.4 MP3 carrying the given GEOB frames."""
    audio = b"\xff\xfb" + b"\x00" * 64
    body = b"".join(frames) + b"\x00" * padding
    tag = b"ID3" + bytes([4, 0, 0]) + _synchsafe(len(body)) + body
    return tag + audio


def test_write_geob_refuses_an_empty_file(tmp_path: Path) -> None:
    """An empty song is not rewritten; the path stays empty."""
    target = tmp_path / "empty.mp3"
    target.write_bytes(b"")

    with pytest.raises(TagFormatError, match="empty"):
        write_geob(target, {"Serato Markers2": b"\x01\x01"})

    assert target.stat().st_size == 0


def test_write_geob_promotes_a_leftover_tmp(tmp_path: Path) -> None:
    """A leftover .tmp is swapped onto an empty destination before the write."""
    payload = b"\x01\x01" + b"\x00" * 8
    rebuilt = _mp3([_geob_frame("Serato Markers2", payload)], padding=64)
    target = tmp_path / "t.mp3"
    target.write_bytes(b"")
    (tmp_path / "t.mp3.tmp").write_bytes(rebuilt)

    assert write_geob(target, {"Serato Markers2": payload}) is False
    assert target.read_bytes() == rebuilt
    assert read_geob(target)["Serato Markers2"] == payload
    assert not (tmp_path / "t.mp3.tmp").exists()


def test_commit_refuses_a_truncated_payload(tmp_path: Path) -> None:
    """A rebuilt file shorter than half the original is not written."""
    target = tmp_path / "t.mp3"
    original = b"x" * 1000
    target.write_bytes(original)

    with pytest.raises(TagFormatError, match="truncated"):
        _commit_audio_bytes(target, b"yy", original)

    assert target.read_bytes() == original


def test_commit_restores_original_when_replace_zeros_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If replace leaves a 0-byte destination, the original bytes are written back."""
    target = tmp_path / "t.mp3"
    original = b"x" * 1000
    new_data = b"y" * 1000
    target.write_bytes(original)

    def zero_dest(self: Path, dest: Path) -> None:
        """Truncate the destination and drop the temporary file."""
        Path(dest).write_bytes(b"")
        Path(self).unlink(missing_ok=True)

    monkeypatch.setattr(Path, "replace", zero_dest)

    with pytest.raises(TagFormatError, match="short file"):
        _commit_audio_bytes(target, new_data, original)

    assert target.read_bytes() == original
