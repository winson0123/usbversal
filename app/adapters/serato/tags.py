"""Reading and writing Serato GEOB frames in audio files."""

from __future__ import annotations

import struct
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class TagFormatError(ValueError):
    """Raised when an audio container or tag cannot be parsed."""


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _unsynchsafe(raw: bytes) -> int:
    """Decode a 28-bit synchsafe big-endian value."""
    return (raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3]


def _frame_size(raw: bytes, version: int) -> int:
    """Decode a frame size, which is synchsafe only from ID3v2.4."""
    return _unsynchsafe(raw) if version >= 4 else struct.unpack(">I", raw)[0]


def _encode_frame_size(size: int, version: int) -> bytes:
    """Encode a frame size for the tag's ID3 version."""
    return _synchsafe(size) if version >= 4 else struct.pack(">I", size)


def _geob_description(body: bytes) -> tuple[str, int]:
    """Return a GEOB frame's description and the offset its data starts at."""
    cursor = 1
    for _ in range(3):
        end = body.find(b"\x00", cursor)
        if end < 0:
            raise TagFormatError("Malformed GEOB frame")
        cursor = end + 1
    description = body[:cursor].split(b"\x00")[-2].decode("latin1", "replace")
    return description, cursor


def _riff_id3_span(data: bytes) -> tuple[int, int]:
    """Return the (start, size) of a WAV's id3 chunk payload."""
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        if chunk == b"id3 ":
            return offset + 8, size
        offset += 8 + size + (size & 1)
    raise TagFormatError("No id3 chunk in WAV")


def read_geob(path: str | Path) -> dict[str, bytes]:
    """
    Read Serato GEOB payloads from an audio file.

    Args:
        path: Path to a .wav file carrying an ID3 tag.

    Returns:
        Mapping of GEOB description to payload bytes.

    Raises:
        TagFormatError: The container or tag cannot be parsed.
    """
    data = Path(path).read_bytes()
    start, size = _riff_id3_span(data)
    tag = data[start : start + size]
    if tag[:3] != b"ID3":
        raise TagFormatError("id3 chunk does not hold an ID3 tag")

    version = tag[3]
    end = 10 + _unsynchsafe(tag[6:10])
    offset = 10
    frames: dict[str, bytes] = {}
    while offset + 10 <= min(end, len(tag)):
        frame_id = tag[offset : offset + 4]
        if frame_id == b"\x00\x00\x00\x00":
            break
        frame_size = _frame_size(tag[offset + 4 : offset + 8], version)
        body = tag[offset + 10 : offset + 10 + frame_size]
        offset += 10 + frame_size
        if frame_id == b"GEOB":
            description, cursor = _geob_description(body)
            frames[description] = body[cursor:]
    return frames


def write_geob(path: str | Path, updates: dict[str, bytes]) -> None:
    """
    Replace Serato GEOB payloads in an audio file, in place.

    Only the named frames are rewritten. Every other frame, the tag padding,
    and all audio data are preserved byte for byte.

    Args:
        path: Path to a .wav file carrying an ID3 tag.
        updates: GEOB description to new payload.

    Raises:
        TagFormatError: The container or tag cannot be parsed.
    """
    target = Path(path)
    data = target.read_bytes()
    start, size = _riff_id3_span(data)
    tag = data[start : start + size]
    version = tag[3]
    declared = _unsynchsafe(tag[6:10])
    end = 10 + declared

    rebuilt = bytearray()
    offset = 10
    while offset + 10 <= min(end, len(tag)):
        frame_id = tag[offset : offset + 4]
        if frame_id == b"\x00\x00\x00\x00":
            break
        frame_size = _frame_size(tag[offset + 4 : offset + 8], version)
        header = tag[offset : offset + 10]
        body = tag[offset + 10 : offset + 10 + frame_size]
        offset += 10 + frame_size

        if frame_id == b"GEOB":
            description, cursor = _geob_description(body)
            if description in updates:
                body = body[:cursor] + updates[description]
                header = frame_id + _encode_frame_size(len(body), version) + header[8:10]
        rebuilt += header + body

    padding = max(0, declared - (offset - 10))
    body_bytes = bytes(rebuilt) + b"\x00" * padding
    new_tag = tag[:6] + _synchsafe(len(body_bytes)) + body_bytes

    new_data = bytearray(data)
    pad = size & 1
    new_data[start - 8 : start + size + pad] = (
        b"id3 " + struct.pack("<I", len(new_tag)) + new_tag + b"\x00" * (len(new_tag) & 1)
    )
    new_data[4:8] = struct.pack("<I", len(new_data) - 8)

    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(bytes(new_data))
    temporary.replace(target)
    logger.info("audio_tags_written", path=str(target), frames=sorted(updates))
