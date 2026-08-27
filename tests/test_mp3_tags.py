"""ID3v2.3 and ID3v2.4 MP3 GEOB write/read."""

from __future__ import annotations

import struct
from pathlib import Path

from app.adapters.rekordbox.anlz import Beat
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.tags import read_geob, write_geob

_GEOB_MIME = b"application/octet-stream"
_AUDIO = b"\xff\xfb" + b"\x00" * 64
_GRID = encode_beatgrid([Beat(number=1, bpm=128.0, time_ms=0)])
_MARKERS = b"\x01\x01"


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _encode_frame_size(size: int, version: int) -> bytes:
    """Encode a frame size for the tag's ID3 version."""
    return _synchsafe(size) if version >= 4 else struct.pack(">I", size)


def _geob_frame(description: str, payload: bytes, version: int) -> bytes:
    """Build one raw GEOB frame for the given ID3 version."""
    body = b"\x00" + _GEOB_MIME + b"\x00\x00" + description.encode("latin1") + b"\x00" + payload
    return b"GEOB" + _encode_frame_size(len(body), version) + b"\x00\x00" + body


def _mp3(version: int, frames: list[bytes], *, padding: int) -> bytes:
    """
    Build a minimal MP3 with an ID3 tag of ``version`` and dummy audio.

    Args:
        version: ID3 major version (3 or 4).
        frames: Raw frame bytes already sized for that version.
        padding: Trailing zero bytes inside the tag, so a write can grow frames
            without moving the audio.

    Returns:
        File bytes: ID3 tag then a dummy MPEG frame.
    """
    body = b"".join(frames) + b"\x00" * padding
    tag = b"ID3" + bytes([version, 0, 0]) + _synchsafe(len(body)) + body
    return tag + _AUDIO


def _write_mp3(tmp_path: Path, version: int) -> Path:
    """
    Write a padding-rich MP3 that already carries both Serato frames.

    Args:
        tmp_path: Pytest temp directory.
        version: ID3 major version.

    Returns:
        Path to the written file.
    """
    path = tmp_path / f"v2{version}.mp3"
    frames = [
        _geob_frame("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00\x00", version),
        _geob_frame("Serato Markers2", b"\x01\x01", version),
    ]
    path.write_bytes(_mp3(version, frames, padding=256))
    return path


def _audio_after_tag(data: bytes) -> bytes:
    """Return everything after the ID3 tag (the dummy MPEG frame)."""
    size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
    return data[10 + size :]


def test_id3v24_mp3_round_trips_beatgrid_and_markers(tmp_path: Path) -> None:
    """v2.4 synchsafe frame sizes write and read back on an MP3."""
    path = _write_mp3(tmp_path, 4)
    before_audio = _audio_after_tag(path.read_bytes())

    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    frames = read_geob(path)
    assert frames["Serato BeatGrid"] == _GRID
    assert frames["Serato Markers2"] == _MARKERS
    assert _audio_after_tag(path.read_bytes()) == before_audio
    assert path.read_bytes()[:3] == b"ID3"
    assert path.read_bytes()[3] == 4


def test_id3v23_mp3_round_trips_beatgrid_and_markers(tmp_path: Path) -> None:
    """v2.3 raw 32-bit frame sizes write and read back on an MP3."""
    path = _write_mp3(tmp_path, 3)
    before_audio = _audio_after_tag(path.read_bytes())

    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    frames = read_geob(path)
    assert frames["Serato BeatGrid"] == _GRID
    assert frames["Serato Markers2"] == _MARKERS
    assert _audio_after_tag(path.read_bytes()) == before_audio
    assert path.read_bytes()[3] == 3
