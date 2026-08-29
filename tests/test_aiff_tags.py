"""AIFF / AIFC ID3 GEOB write/read."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.adapters.rekordbox.anlz import Beat
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.tags import TagFormatError, read_geob, write_geob

_GEOB_MIME = b"application/octet-stream"
_RATE_44100 = bytes.fromhex("400eac44000000000000")
_SOUND = b"\x00\x01" * 32
_GRID = encode_beatgrid([Beat(number=1, bpm=128.0, time_ms=0)])
_MARKERS = b"\x01\x01"


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _geob_frame(description: str, payload: bytes) -> bytes:
    """Build one ID3v2.4 GEOB frame."""
    body = b"\x00" + _GEOB_MIME + b"\x00\x00" + description.encode("latin1") + b"\x00" + payload
    return b"GEOB" + _synchsafe(len(body)) + b"\x00\x00" + body


def _id3(frames: list[bytes], *, padding: int) -> bytes:
    """
    Build an ID3v2.4 tag.

    Args:
        frames: Raw frame bytes.
        padding: Trailing zeros inside the tag.

    Returns:
        A complete ID3 tag.
    """
    body = b"".join(frames) + b"\x00" * padding
    return b"ID3" + bytes([4, 0, 0]) + _synchsafe(len(body)) + body


def _iff_chunk(name: bytes, body: bytes) -> bytes:
    """
    Build one big-endian IFF chunk.

    Args:
        name: Four-byte chunk id.
        body: Payload.

    Returns:
        Header, payload, and pad byte when needed.
    """
    pad = b"\x00" if len(body) & 1 else b""
    return name + struct.pack(">I", len(body)) + body + pad


def _aiff(*, sound: bytes, id3: bytes | None, form_type: bytes = b"AIFF") -> bytes:
    """
    Build a minimal FORM file with COMM, SSND, and optional ID3.

    Args:
        sound: PCM bytes stored after the SSND offset/blockSize header.
        id3: Full ID3 tag, or None to omit the chunk.
        form_type: ``AIFF`` or ``AIFC``.

    Returns:
        A complete FORM file.
    """
    comm = struct.pack(">hIh", 1, len(sound) // 2, 16) + _RATE_44100
    ssnd = struct.pack(">II", 0, 0) + sound
    chunks = [_iff_chunk(b"COMM", comm), _iff_chunk(b"SSND", ssnd)]
    if id3 is not None:
        chunks.append(_iff_chunk(b"ID3 ", id3))
    body = form_type + b"".join(chunks)
    return b"FORM" + struct.pack(">I", len(body)) + body


def _ssnd_sound(data: bytes) -> bytes:
    """Return the PCM bytes inside the SSND chunk."""
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = int.from_bytes(data[offset + 4 : offset + 8], "big")
        if chunk == b"SSND":
            return data[offset + 16 : offset + 8 + size]
        offset += 8 + size + (size & 1)
    raise AssertionError("no SSND chunk")


def _tagged_aiff(tmp_path: Path, *, suffix: str = ".aiff", form_type: bytes = b"AIFF") -> Path:
    """
    Write a padding-rich AIFF that already carries both Serato frames.

    Args:
        tmp_path: Pytest temp directory.
        suffix: File suffix (``.aiff`` or ``.aif``).
        form_type: ``AIFF`` or ``AIFC``.

    Returns:
        Path to the written file.
    """
    path = tmp_path / f"t{suffix}"
    frames = [
        _geob_frame("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00\x00"),
        _geob_frame("Serato Markers2", b"\x01\x01"),
    ]
    path.write_bytes(_aiff(sound=_SOUND, id3=_id3(frames, padding=256), form_type=form_type))
    return path


def test_aiff_round_trips_beatgrid_and_markers(tmp_path: Path) -> None:
    """v2.4 GEOB frames write and read back on an AIFF."""
    path = _tagged_aiff(tmp_path)
    before = _ssnd_sound(path.read_bytes())

    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    frames = read_geob(path)
    assert frames["Serato BeatGrid"] == _GRID
    assert frames["Serato Markers2"] == _MARKERS
    assert _ssnd_sound(path.read_bytes()) == before
    assert path.read_bytes()[:4] == b"FORM"
    assert path.read_bytes()[8:12] == b"AIFF"


def test_aif_suffix_round_trips(tmp_path: Path) -> None:
    """The same FORM bytes work under a .aif name."""
    path = _tagged_aiff(tmp_path, suffix=".aif")

    write_geob(path, {"Serato BeatGrid": _GRID})

    assert read_geob(path)["Serato BeatGrid"] == _GRID


def test_aifc_round_trips(tmp_path: Path) -> None:
    """AIFC uses the same ID3 chunk as AIFF."""
    path = _tagged_aiff(tmp_path, form_type=b"AIFC")

    write_geob(path, {"Serato Markers2": _MARKERS})

    assert read_geob(path)["Serato Markers2"] == _MARKERS
    assert path.read_bytes()[8:12] == b"AIFC"


def test_aiff_without_id3_gains_a_chunk(tmp_path: Path) -> None:
    """A tag-less AIFF gets an ID3 chunk; SSND stays the same."""
    path = tmp_path / "bare.aiff"
    path.write_bytes(_aiff(sound=_SOUND, id3=None))
    before = _ssnd_sound(path.read_bytes())

    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    assert read_geob(path)["Serato BeatGrid"] == _GRID
    assert read_geob(path)["Serato Markers2"] == _MARKERS
    assert _ssnd_sound(path.read_bytes()) == before
    assert b"ID3 " in path.read_bytes()


def test_aiff_preserves_sibling_geob(tmp_path: Path) -> None:
    """Updating BeatGrid leaves other GEOB descriptions untouched."""
    frames = [
        _geob_frame("Serato Overview", b"\x01\x05"),
        _geob_frame("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00\x00"),
        _geob_frame("Serato Markers2", b"\x01\x01"),
    ]
    path = tmp_path / "sib.aiff"
    path.write_bytes(_aiff(sound=_SOUND, id3=_id3(frames, padding=256)))

    write_geob(path, {"Serato BeatGrid": _GRID})

    after = read_geob(path)
    assert after["Serato Overview"] == b"\x01\x05"
    assert after["Serato BeatGrid"] == _GRID
    assert after["Serato Markers2"] == b"\x01\x01"


def test_non_aiff_form_is_rejected(tmp_path: Path) -> None:
    """A FORM that is not AIFF/AIFC fails rather than being mangled."""
    junk = tmp_path / "x.aiff"
    junk.write_bytes(b"FORM" + struct.pack(">I", 4) + b"WAVE")

    with pytest.raises(TagFormatError):
        read_geob(junk)
