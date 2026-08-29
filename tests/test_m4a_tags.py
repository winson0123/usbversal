"""MP4 / M4A Serato freeform-atom write/read."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.adapters.rekordbox.anlz import Beat
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.tags import TagFormatError, read_geob, verify_geob_rewrite, write_geob

_GRID = encode_beatgrid([Beat(number=1, bpm=128.0, time_ms=0)])
_MARKERS = b"\x01\x01"
_AUDIO = b"\x11" * 64


def _box(kind: bytes, payload: bytes) -> bytes:
    """
    Build one 32-bit-size MP4 box.

    Args:
        kind: Four-byte type.
        payload: Box body.

    Returns:
        Size, type, and payload.
    """
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _stco(offset: int) -> bytes:
    """
    Build an ``stco`` box with one chunk offset.

    Args:
        offset: Absolute file offset of the sample.

    Returns:
        A complete ``stco`` box.
    """
    return _box(b"stco", bytes(4) + struct.pack(">II", 1, offset))


def _mdat_payload_offset(data: bytes) -> int:
    """Return the file offset of the first mdat payload byte."""
    offset = 0
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        if kind == b"mdat":
            return offset + 8
        offset += size
    raise AssertionError("no mdat")


def _stco_offset(data: bytes) -> int:
    """Return the first sample offset stored in stco."""
    offset = data.find(b"stco")
    if offset < 0:
        raise AssertionError("no stco")
    return struct.unpack(">I", data[offset + 12 : offset + 16])[0]


def _mdat_payload(data: bytes) -> bytes:
    """Return the first mdat payload."""
    start = _mdat_payload_offset(data)
    size = int.from_bytes(data[start - 8 : start - 4], "big")
    return data[start : start - 8 + size]


def _m4a(*, audio: bytes, ilst: bytes = b"") -> bytes:
    """
    Build a minimal MP4 with moov (stco + optional ilst) and mdat.

    Args:
        audio: ``mdat`` payload.
        ilst: Raw ``ilst`` children (``----`` items), or empty.

    Returns:
        A complete file whose ``stco`` points at ``mdat``.
    """
    ftyp = _box(b"ftyp", b"M4A " + struct.pack(">I", 0) + b"M4A isom")
    hdlr = _box(b"hdlr", bytes(4) + b"mdir" + bytes(12) + b"\x00")
    meta = _box(b"meta", bytes(4) + hdlr + _box(b"ilst", ilst))
    udta = _box(b"udta", meta)

    def assemble(chunk_offset: int) -> bytes:
        """
        Build ftyp + moov + mdat for a guessed sample offset.

        Args:
            chunk_offset: Value written into ``stco``.

        Returns:
            File bytes.
        """
        stbl = _box(b"stbl", _stco(chunk_offset))
        trak = _box(b"trak", _box(b"mdia", _box(b"minf", stbl)))
        moov = _box(b"moov", trak + udta)
        return ftyp + moov + _box(b"mdat", audio)

    guess = len(ftyp) + 64
    for _ in range(6):
        data = assemble(guess)
        actual = _mdat_payload_offset(data)
        if actual == guess:
            return data
        guess = actual
    raise AssertionError("stco did not converge")


def _write_m4a(tmp_path: Path, *, suffix: str = ".m4a", ilst: bytes = b"") -> Path:
    """
    Write a minimal M4A to ``tmp_path``.

    Args:
        tmp_path: Pytest temp directory.
        suffix: ``.m4a`` or ``.mp4``.
        ilst: Optional existing freeform items.

    Returns:
        Path to the written file.
    """
    path = tmp_path / f"t{suffix}"
    path.write_bytes(_m4a(audio=_AUDIO, ilst=ilst))
    return path


def test_m4a_round_trips_beatgrid_and_markers(tmp_path: Path) -> None:
    """Serato atoms write and read back; mdat and stco stay consistent."""
    path = _write_m4a(tmp_path)
    original = path.read_bytes()

    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    frames = read_geob(path)
    assert frames["Serato BeatGrid"] == _GRID
    assert frames["Serato Markers2"] == _MARKERS
    rebuilt = path.read_bytes()
    assert _mdat_payload(rebuilt) == _AUDIO
    assert rebuilt[_stco_offset(rebuilt) : _stco_offset(rebuilt) + len(_AUDIO)] == _AUDIO
    assert _stco_offset(rebuilt) != _stco_offset(original)


def test_mp4_suffix_round_trips(tmp_path: Path) -> None:
    """The same boxes work under a .mp4 name."""
    path = _write_m4a(tmp_path, suffix=".mp4")

    write_geob(path, {"Serato BeatGrid": _GRID})

    assert read_geob(path)["Serato BeatGrid"] == _GRID


def test_m4a_preserves_foreign_ilst_items(tmp_path: Path) -> None:
    """A non-Serato ilst item is left in place."""
    title = _box(b"\xa9nam", _box(b"data", struct.pack(">II", 1, 0) + b"Song"))
    path = _write_m4a(tmp_path, ilst=title)

    write_geob(path, {"Serato BeatGrid": _GRID})

    assert b"Song" in path.read_bytes()
    assert read_geob(path)["Serato BeatGrid"] == _GRID


def test_m4a_remove_geob(tmp_path: Path) -> None:
    """A named atom is gone after remove_geob."""
    path = _write_m4a(tmp_path)
    write_geob(path, {"Serato BeatGrid": _GRID, "Serato Markers2": _MARKERS})

    write_geob(path, {}, remove_geob={"Serato BeatGrid"})

    frames = read_geob(path)
    assert "Serato BeatGrid" not in frames
    assert frames["Serato Markers2"] == _MARKERS


def test_verify_rejects_an_altered_mdat(tmp_path: Path) -> None:
    """Corrupting mdat fails verification even if the atoms look fine."""
    path = _write_m4a(tmp_path)
    write_geob(path, {"Serato BeatGrid": _GRID})
    original = path.read_bytes()
    start = _mdat_payload_offset(original)
    corrupted = bytearray(original)
    corrupted[start] ^= 0xFF

    with pytest.raises(TagFormatError, match="audio stream"):
        verify_geob_rewrite(original, bytes(corrupted), {"Serato BeatGrid": _GRID})


def test_non_mp4_is_rejected(tmp_path: Path) -> None:
    """A file that only looks like an m4a by suffix is not parsed as MP4."""
    junk = tmp_path / "x.m4a"
    junk.write_bytes(b"not-an-mp4-file")

    with pytest.raises(TagFormatError):
        read_geob(junk)
