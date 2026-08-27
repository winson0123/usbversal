"""Serato BeatGrid / Markers2 on FLAC Vorbis comments."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.adapters.rekordbox.anlz import Beat
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.tags import TagFormatError, read_geob, write_geob

_GRID = encode_beatgrid([Beat(number=1, bpm=128.0, time_ms=0)])
_MARKERS = b"\x01\x01"
_AUDIO = b"\xff\xf8\x68\x02" + b"\x00" * 16


def _streaminfo() -> bytes:
    """Build a 34-byte STREAMINFO for 44.1 kHz mono 16-bit silence."""
    word = (44100 << 44) | (0 << 41) | (15 << 36) | 0
    return struct.pack(">HH", 4096, 4096) + b"\x00" * 6 + struct.pack(">Q", word) + b"\x00" * 16


def _block(last: bool, block_type: int, body: bytes) -> bytes:
    """Build one FLAC metadata block including its header."""
    first = (0x80 if last else 0) | block_type
    return bytes([first]) + len(body).to_bytes(3, "big") + body


def _vorbis_comment(pairs: list[tuple[str, str]]) -> bytes:
    """Serialise a Vorbis comment body with an empty vendor string."""
    body = bytearray()
    body += struct.pack("<I", 0)
    body += struct.pack("<I", len(pairs))
    for key, value in pairs:
        raw = f"{key}={value}".encode()
        body += struct.pack("<I", len(raw)) + raw
    return bytes(body)


def _flac(tmp_path: Path, pairs: list[tuple[str, str]] | None = None) -> Path:
    """
    Write a minimal FLAC: STREAMINFO, optional comments, dummy audio.

    Args:
        tmp_path: Pytest temp directory.
        pairs: Vorbis comments to include; omit the comment block when None.

    Returns:
        Path to the written file.
    """
    path = tmp_path / "t.flac"
    if pairs is None:
        data = b"fLaC" + _block(True, 0, _streaminfo()) + _AUDIO
    else:
        data = (
            b"fLaC"
            + _block(False, 0, _streaminfo())
            + _block(True, 4, _vorbis_comment(pairs))
            + _AUDIO
        )
    path.write_bytes(data)
    return path


def _audio_tail(data: bytes) -> bytes:
    """Return everything after the last FLAC metadata block."""
    offset = 4
    while offset + 4 <= len(data):
        last = bool(data[offset] & 0x80)
        length = int.from_bytes(data[offset + 1 : offset + 4], "big")
        offset += 4 + length
        if last:
            return data[offset:]
    raise AssertionError("no last metadata block")


def test_flac_round_trips_beatgrid_and_markers(tmp_path: Path) -> None:
    """Writing Serato fields on a comment-less FLAC reads them back."""
    path = _flac(tmp_path)
    before = _audio_tail(path.read_bytes())

    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    frames = read_geob(path)
    assert frames["Serato BeatGrid"] == _GRID
    assert frames["Serato Markers2"] == _MARKERS
    after = path.read_bytes()
    assert after[:4] == b"fLaC"
    assert _audio_tail(after) == before


def test_flac_preserves_a_foreign_comment(tmp_path: Path) -> None:
    """A comment we do not own stays byte-identical in meaning."""
    path = _flac(tmp_path, [("TITLE", "Leave me"), ("ARTIST", "Someone")])

    write_geob(path, {"Serato BeatGrid": _GRID})

    data = path.read_bytes()
    assert b"TITLE=Leave me" in data
    assert b"ARTIST=Someone" in data
    assert read_geob(path)["Serato BeatGrid"] == _GRID


def test_flac_audio_hash_is_unchanged(tmp_path: Path) -> None:
    """STREAMINFO and the audio frames do not move or change."""
    path = _flac(tmp_path, [("TITLE", "x")])
    original = path.read_bytes()

    write_geob(path, {"Serato Markers2": _MARKERS})

    rebuilt = path.read_bytes()
    assert original[4:42] == rebuilt[4:42]
    assert _audio_tail(original) == _audio_tail(rebuilt)


def test_flac_remove_drops_only_the_named_field(tmp_path: Path) -> None:
    """Removing Markers2 leaves BeatGrid and foreign comments."""
    path = _flac(tmp_path, [("TITLE", "keep")])
    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    write_geob(path, {}, remove_geob={"Serato Markers2"})

    frames = read_geob(path)
    assert "Serato Markers2" not in frames
    assert frames["Serato BeatGrid"] == _GRID
    assert b"TITLE=keep" in path.read_bytes()


def test_flac_rejects_a_non_flac_file(tmp_path: Path) -> None:
    """A file that is not FLAC, MP3, or WAV fails rather than being mangled."""
    junk = tmp_path / "x.flac"
    junk.write_bytes(b"OggS" + b"\x00" * 20)

    with pytest.raises(TagFormatError):
        read_geob(junk)
