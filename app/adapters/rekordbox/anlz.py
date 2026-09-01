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
# Real Rekordbox .EXT PCP2 bodies are 72 bytes when the cue comment is
# empty: a 00 at offset 28, then RGB at 29. Reading RGB at 28 picks up
# that leading 00 and shifts the colour. An 88-byte entry stores a
# length-prefixed UTF-16 comment at offset 24; RGB moves with it.
# Shorter test bodies still keep RGB at 28 when the comment length is
# missing.
_CUE_RGB_OFFSET = 29
_CUE_RGB_OFFSET_SHORT = 28
_COMMENT_LEN_OFFSET = 24


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
        if tag != _EXTENDED_CUES or total_len <= header_len:
            continue
        kind, count = struct.unpack(">IH", data[offset + 12 : offset + 18])
        if kind != _HOT_CUE_LIST:
            continue
        entry = offset + header_len
        for _ in range(count):
            entry_header, entry_total = struct.unpack(">II", data[entry + 4 : entry + 12])
            number = struct.unpack(">I", data[entry + 12 : entry + 16])[0]
            body = data[entry + entry_header : entry + entry_total]
            position = struct.unpack(">I", body[4:8])[0]
            red, green, blue = _cue_rgb(body)
            cues.append(
                HotCue(
                    slot=number - 1,
                    position_ms=position,
                    colour=f"#{red:02X}{green:02X}{blue:02X}",
                )
            )
            entry += entry_total

    cues.sort(key=lambda cue: cue.slot)
    logger.debug("anlz_hot_cues_read", path=str(path), count=len(cues))
    return cues


def _cue_rgb(body: bytes) -> tuple[int, int, int]:
    """
    Return the RGB triple from one PCP2 cue body.

    Offset 24 is a big-endian byte length for a UTF-16BE comment.
    RGB is at offset 29 plus that length (29 when the comment is empty).
    A named cue such as ``1.1Bars`` is 16 comment bytes; reading offset
    29 then treats ``1.`` as ``#31002E``.

    Args:
        body: Bytes after the PCP2 header.

    Returns:
        ``(red, green, blue)``. Offset 29 on an empty-comment Rekordbox
        entry; after the comment when one is present; offset 28 on
        shorter layouts; the last three bytes otherwise.
    """
    if len(body) >= _COMMENT_LEN_OFFSET + 4:
        comment_len = struct.unpack(">I", body[_COMMENT_LEN_OFFSET : _COMMENT_LEN_OFFSET + 4])[0]
        rgb_at = _CUE_RGB_OFFSET + comment_len
        if comment_len % 2 == 0 and rgb_at + 3 <= len(body):
            return body[rgb_at], body[rgb_at + 1], body[rgb_at + 2]
    if len(body) >= _CUE_RGB_OFFSET_SHORT + 3:
        return (
            body[_CUE_RGB_OFFSET_SHORT],
            body[_CUE_RGB_OFFSET_SHORT + 1],
            body[_CUE_RGB_OFFSET_SHORT + 2],
        )
    if len(body) >= 3:
        return body[-3], body[-2], body[-1]
    return 0, 0, 0


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
        if tag != "PQTZ" or total_len <= header_len:
            continue
        body = data[offset + header_len : offset + total_len]
        return [
            Beat(number=number, bpm=tempo / 100.0, time_ms=time)
            for number, tempo, time in (
                struct.unpack(">HHI", body[i * 8 : (i + 1) * 8]) for i in range(len(body) // 8)
            )
        ]
    return []
