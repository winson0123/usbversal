"""Reading hot cues from Rekordbox ANLZ analysis files."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_MAGIC = b"PMAI"
_EXTENDED_CUES = "PCO2"
_HOT_CUE_LIST = 1


class AnlzError(ValueError):
    """Raised when an ANLZ file cannot be parsed."""


@dataclass(frozen=True)
class HotCue:
    """
    One Rekordbox hot cue.

    Attributes:
        slot: Zero-based cue slot, as Serato numbers them.
        position_ms: Cue position in milliseconds.
        colour: Rekordbox cue colour as #RRGGBB, black when unset.
    """

    slot: int
    position_ms: int
    colour: str


def extended_path(analysis_path: str | Path) -> Path:
    """
    Return the .EXT sibling of an ANLZ .DAT path.

    Extended cue data, which carries colour, lives only in the .EXT file.

    Args:
        analysis_path: Rekordbox analysis_data_file_path value.

    Returns:
        Path to the .EXT file.
    """
    return Path(analysis_path).with_suffix(".EXT")


def _sections(data: bytes):
    """Yield (tag, header_len, total_len, offset) for each ANLZ section."""
    if data[:4] != _MAGIC:
        raise AnlzError(f"Not an ANLZ file: magic {data[:4]!r}")
    offset = struct.unpack(">I", data[4:8])[0]
    while offset + 12 <= len(data):
        tag = data[offset : offset + 4].decode("latin1")
        header_len, total_len = struct.unpack(">II", data[offset + 4 : offset + 12])
        if total_len <= 0:
            return
        yield tag, header_len, total_len, offset
        offset += total_len


def read_hot_cues(extended_file: str | Path) -> list[HotCue]:
    """
    Read hot cues from an ANLZ .EXT file.

    Memory cues are ignored: only hot cues occupy Serato's cue slots.

    Args:
        extended_file: Path to an ANLZ .EXT file.

    Returns:
        Hot cues ordered by slot. Empty when the track has none.

    Raises:
        AnlzError: The file is not a readable ANLZ container.
    """
    path = Path(extended_file)
    if not path.is_file():
        return []

    data = path.read_bytes()
    cues: list[HotCue] = []
    for tag, header_len, total_len, offset in _sections(data):
        cues.extend(_cues_from_section(data, tag, header_len, total_len, offset))

    cues.sort(key=lambda cue: cue.slot)
    logger.debug("anlz_hot_cues_read", path=str(path), count=len(cues))
    return cues


def _cues_from_section(
    data: bytes, tag: str, header_len: int, total_len: int, offset: int
) -> list[HotCue]:
    """
    Read hot cues from one PCO2 section, or return empty when it is not one.

    Args:
        data: Whole ANLZ file.
        tag: Section fourcc.
        header_len: Section header length.
        total_len: Section total length.
        offset: Byte index of the section.

    Returns:
        Hot cues in this section, or an empty list.
    """
    if tag != _EXTENDED_CUES or total_len <= header_len:
        return []
    kind, count = struct.unpack(">IH", data[offset + 12 : offset + 18])
    if kind != _HOT_CUE_LIST:
        return []
    cues: list[HotCue] = []
    entry = offset + header_len
    for _ in range(count):
        cue, entry = _read_one_hot_cue(data, entry)
        cues.append(cue)
    return cues


def _read_one_hot_cue(data: bytes, entry: int) -> tuple[HotCue, int]:
    """
    Read one PCOB hot-cue entry.

    Args:
        data: Whole ANLZ file.
        entry: Byte index of this cue entry.

    Returns:
        The cue and the byte index of the next entry.
    """
    entry_header, entry_total = struct.unpack(">II", data[entry + 4 : entry + 12])
    number = struct.unpack(">I", data[entry + 12 : entry + 16])[0]
    body = data[entry + entry_header : entry + entry_total]
    position = struct.unpack(">I", body[4:8])[0]
    red, green, blue = body[-3:]
    cue = HotCue(
        slot=number - 1,
        position_ms=position,
        colour=f"#{red:02X}{green:02X}{blue:02X}",
    )
    return cue, entry + entry_total


@dataclass(frozen=True)
class Beat:
    """
    One beat from a Rekordbox beat grid.

    Attributes:
        number: Beat position in the bar, 1 to 4.
        bpm: Tempo at this beat.
        time_ms: Beat position in milliseconds.
    """

    number: int
    bpm: float
    time_ms: int


def read_beats(analysis_file: str | Path) -> list[Beat]:
    """
    Read the beat grid from an ANLZ .DAT file.

    Args:
        analysis_file: Path to an ANLZ .DAT file.

    Returns:
        Beats in time order. Empty when the track has no grid.
    """
    path = Path(analysis_file)
    if not path.is_file():
        return []

    data = path.read_bytes()
    for tag, header_len, total_len, offset in _sections(data):
        beats = _beats_from_section(data, tag, header_len, total_len, offset)
        if beats is not None:
            return beats
    return []


def _beats_from_section(
    data: bytes, tag: str, header_len: int, total_len: int, offset: int
) -> list[Beat] | None:
    """
    Read a PQTZ beat grid, or return None when this section is not one.

    Args:
        data: Whole ANLZ file.
        tag: Section fourcc.
        header_len: Section header length.
        total_len: Section total length.
        offset: Byte index of the section.

    Returns:
        Beats in time order, or None when the section is not a grid.
    """
    if tag != "PQTZ" or total_len <= header_len:
        return None
    body = data[offset + header_len : offset + total_len]
    return [
        Beat(number=number, bpm=tempo / 100.0, time_ms=time)
        for number, tempo, time in (
            struct.unpack(">HHI", body[i * 8 : (i + 1) * 8]) for i in range(len(body) // 8)
        )
    ]
