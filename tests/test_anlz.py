"""Tests for reading Rekordbox ANLZ analysis files."""

import struct
from pathlib import Path

import pytest

from app.adapters.rekordbox.anlz import (
    AnlzError,
    extended_path,
    read_beats,
    read_hot_cues,
)


def _section(tag: bytes, header_extra: bytes, body: bytes) -> bytes:
    """Build one ANLZ section with its header and total lengths."""
    header_len = 12 + len(header_extra)
    total_len = header_len + len(body)
    return tag + struct.pack(">II", header_len, total_len) + header_extra + body


def _anlz(sections: bytes) -> bytes:
    """Wrap sections in a PMAI container."""
    return b"PMAI" + struct.pack(">II", 28, 28 + len(sections)) + b"\x00" * 16 + sections


def _pqtz(beats: list[tuple[int, float, int]]) -> bytes:
    """Build a PQTZ beat grid section."""
    body = b"".join(struct.pack(">HHI", n, int(bpm * 100), t) for n, bpm, t in beats)
    return _section(b"PQTZ", b"\x00" * 12, body)


def _cue(number: int, time_ms: int, colour: tuple[int, int, int]) -> bytes:
    """Build one PCP2 entry matching a real Rekordbox 72-byte cue body."""
    body = bytearray(72)
    body[0:4] = b"\x01\x00\x03\xe8"
    struct.pack_into(">I", body, 4, time_ms)
    body[8:12] = b"\xff\xff\xff\xff"
    body[12:16] = b"\x00\x01\x00\x00"
    body[28:31] = bytes(colour)
    header = struct.pack(">II", 16, 16 + len(body)) + struct.pack(">I", number)
    return b"PCP2" + header + bytes(body)


def _pco2(kind: int, cues: list[bytes]) -> bytes:
    """Build a PCO2 cue-list section; kind 1 is hot cues."""
    extra = struct.pack(">IHH", kind, len(cues), 0)
    return _section(b"PCO2", extra, b"".join(cues))


def test_extended_path_swaps_the_suffix() -> None:
    """Extended cue data lives in the .EXT sibling."""
    assert extended_path("/PIONEER/USBANLZ/P001/ANLZ0000.DAT").name == "ANLZ0000.EXT"


def test_missing_file_yields_nothing(tmp_path: Path) -> None:
    """An absent analysis file is not an error."""
    assert read_beats(tmp_path / "nope.DAT") == []
    assert read_hot_cues(tmp_path / "nope.EXT") == []


def test_rejects_a_non_anlz_file(tmp_path: Path) -> None:
    """A file without the PMAI magic is refused rather than misread."""
    bad = tmp_path / "x.DAT"
    bad.write_bytes(b"NOPE" + b"\x00" * 64)

    with pytest.raises(AnlzError):
        read_beats(bad)


def test_reads_beats_with_tempo_and_time(tmp_path: Path) -> None:
    """Each PQTZ entry carries a bar position, a tempo and a time."""
    f = tmp_path / "a.DAT"
    f.write_bytes(_anlz(_pqtz([(1, 128.0, 0), (2, 128.0, 469), (3, 127.5, 938)])))

    beats = read_beats(f)

    assert [b.number for b in beats] == [1, 2, 3]
    assert [b.time_ms for b in beats] == [0, 469, 938]
    assert beats[0].bpm == 128.0
    assert beats[2].bpm == 127.5


def test_reads_hot_cues_with_slot_position_and_colour(tmp_path: Path) -> None:
    """Rekordbox numbers hot cues from one; Serato slots start at zero."""
    f = tmp_path / "a.EXT"
    f.write_bytes(
        _anlz(_pco2(1, [_cue(1, 0, (0xFF, 0x00, 0x17)), _cue(2, 441, (0x00, 0xC4, 0xFF))]))
    )

    cues = read_hot_cues(f)

    assert [(c.slot, c.position_ms, c.colour) for c in cues] == [
        (0, 0, "#FF0017"),
        (1, 441, "#00C4FF"),
    ]


def test_cue_colour_is_not_the_trailing_padding(tmp_path: Path) -> None:
    """Comment NULs after the RGB must not be read as black."""
    f = tmp_path / "a.EXT"
    f.write_bytes(_anlz(_pco2(1, [_cue(1, 15532, (0xFF, 0x00, 0x17))])))

    assert read_hot_cues(f)[0].colour == "#FF0017"


def test_memory_cues_are_ignored(tmp_path: Path) -> None:
    """Only hot cues occupy Serato's cue slots."""
    f = tmp_path / "a.EXT"
    f.write_bytes(_anlz(_pco2(0, [_cue(1, 1000, (0, 0, 0))])))

    assert read_hot_cues(f) == []


def test_cues_come_back_in_slot_order(tmp_path: Path) -> None:
    """Cues are ordered by slot regardless of their order in the file."""
    f = tmp_path / "a.EXT"
    f.write_bytes(_anlz(_pco2(1, [_cue(3, 900, (1, 2, 3)), _cue(1, 100, (4, 5, 6))])))

    assert [c.slot for c in read_hot_cues(f)] == [0, 2]


def test_other_sections_are_skipped(tmp_path: Path) -> None:
    """Unrelated sections do not disturb the walk."""
    f = tmp_path / "a.DAT"
    f.write_bytes(_anlz(_section(b"PPTH", b"", b"\x00" * 40) + _pqtz([(1, 120.0, 10)])))

    assert [b.time_ms for b in read_beats(f)] == [10]
