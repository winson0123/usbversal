"""Reading and writing Serato GEOB frames in audio files."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Serato writes GEOB frames with this header: encoding byte, mime type, an
# empty filename, then the description.
_GEOB_MIME = b"application/octet-stream"


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


def _tag_span(data: bytes) -> tuple[int, int]:
    """
    Return the (start, size) of the ID3 tag inside an audio file.

    MP3 carries the tag at the head; WAV wraps it in a RIFF `id3 ` chunk.

    Args:
        data: Whole file contents.

    Returns:
        Offset and length of the ID3 tag.

    Raises:
        TagFormatError: No ID3 tag could be located.
    """
    if data[:3] == b"ID3":
        return 0, 10 + _unsynchsafe(data[6:10])

    if data[:4] == b"RIFF":
        offset = 12
        while offset + 8 <= len(data):
            chunk = data[offset : offset + 4]
            size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
            if chunk == b"id3 ":
                return offset + 8, size
            offset += 8 + size + (size & 1)
        raise TagFormatError("No id3 chunk in WAV")

    raise TagFormatError("Unrecognised audio container")


def _audio_span(data: bytes) -> tuple[int, int]:
    """
    Return the (start, size) of the raw audio payload, outside any tag.

    MP3 carries audio as everything after the ID3 tag. WAV interleaves
    chunks, so the audio lives in its own `data` chunk rather than simply
    after the tag -- hashing "everything but the tag" for a WAV would count
    other metadata chunks as audio and mask a real corruption.

    Args:
        data: Whole file contents.

    Returns:
        Offset and length of the audio payload.

    Raises:
        TagFormatError: The container is not recognised, or a WAV carries no
            `data` chunk.
    """
    if data[:3] == b"ID3":
        start, size = _tag_span(data)
        return start + size, len(data) - (start + size)

    if data[:4] == b"RIFF":
        offset = 12
        while offset + 8 <= len(data):
            chunk = data[offset : offset + 4]
            size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
            if chunk == b"data":
                return offset + 8, size
            offset += 8 + size + (size & 1)
        raise TagFormatError("No data chunk in WAV")

    raise TagFormatError("Unrecognised audio container")


def _read_geob_bytes(data: bytes) -> dict[str, bytes]:
    """Parse GEOB payloads out of whole file contents already in memory."""
    start, size = _tag_span(data)
    tag = data[start : start + size]
    if tag[:3] != b"ID3":
        raise TagFormatError("No ID3 tag found")

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
    return _read_geob_bytes(Path(path).read_bytes())


def verify_geob_rewrite(
    original: bytes,
    rebuilt: bytes,
    updates: dict[str, bytes],
    *,
    remove_geob: set[str] | None = None,
) -> None:
    """
    Confirm a rewritten file changed nothing but the requested GEOB frames.

    Every hand-run analysis pass repeated these three checks before trusting a
    write: the file's size, its audio stream, and the frames actually read
    back. This is that check, made mandatory rather than remembered. It caught
    two real defects during that work: a silent no-op when a frame did not
    already exist, and a false positive from hashing a WAV file whole instead
    of just its `data` chunk.

    Args:
        original: File contents before the rewrite.
        rebuilt: File contents about to be written.
        updates: GEOB description to the payload it was supposed to become.
        remove_geob: GEOB descriptions that were supposed to be deleted.

    Raises:
        TagFormatError: The file size changed, the audio payload moved or its
            content changed, a written frame does not read back as requested,
            or a frame meant for removal is still present.
    """
    if len(rebuilt) != len(original):
        raise TagFormatError(
            f"Write would change the file size ({len(original)} -> {len(rebuilt)} bytes)"
        )

    original_span = _audio_span(original)
    rebuilt_span = _audio_span(rebuilt)
    if original_span != rebuilt_span:
        raise TagFormatError("Write would move the audio stream")
    start, size = original_span
    original_hash = hashlib.sha256(original[start : start + size]).digest()
    rebuilt_hash = hashlib.sha256(rebuilt[start : start + size]).digest()
    if original_hash != rebuilt_hash:
        raise TagFormatError("Write would alter the audio stream")

    frames = _read_geob_bytes(rebuilt)
    for description, payload in updates.items():
        if frames.get(description) != payload:
            raise TagFormatError(f"{description!r} did not read back as written")
    for description in remove_geob or set():
        if description in frames:
            raise TagFormatError(f"{description!r} was supposed to be removed")


def write_geob(
    path: str | Path,
    updates: dict[str, bytes],
    *,
    remove_geob: set[str] | None = None,
    remove_frames: set[bytes] | None = None,
) -> None:
    """
    Replace or remove frames in an audio file's ID3 tag, in place.

    Only the named frames are touched. Every other frame and all audio data are
    preserved byte for byte, and the tag keeps its original size. Before
    anything reaches disk, the rebuilt file is verified against the original:
    same size, same audio stream, and every requested frame reads back exactly
    as written. The original file is untouched if verification fails.

    Args:
        path: Path to an .mp3 or .wav file carrying an ID3 tag.
        updates: GEOB description to new payload.
        remove_geob: GEOB descriptions to delete entirely.
        remove_frames: Frame ids to delete entirely, such as ``b"TKEY"``.

    Raises:
        TagFormatError: The container or tag cannot be parsed, the new frames
            no longer fit the original tag, or the rebuilt file fails
            verification against the original.
    """
    dropped_geob = remove_geob or set()
    dropped_frames = remove_frames or set()
    target = Path(path)
    data = target.read_bytes()
    start, size = _tag_span(data)
    tag = data[start : start + size]
    version = tag[3]
    declared = _unsynchsafe(tag[6:10])
    end = 10 + declared

    rebuilt = bytearray()
    written: set[str | None] = set()
    offset = 10
    while offset + 10 <= min(end, len(tag)):
        frame_id = tag[offset : offset + 4]
        if frame_id == b"\x00\x00\x00\x00":
            break
        frame_size = _frame_size(tag[offset + 4 : offset + 8], version)
        header = tag[offset : offset + 10]
        body = tag[offset + 10 : offset + 10 + frame_size]
        offset += 10 + frame_size

        description = None
        if frame_id in dropped_frames:
            continue
        if frame_id == b"GEOB":
            description, cursor = _geob_description(body)
            if description in dropped_geob:
                continue
            if description in updates:
                body = body[:cursor] + updates[description]
                header = frame_id + _encode_frame_size(len(body), version) + header[8:10]
            written.add(description)
        rebuilt += header + body

    # A frame the file has never carried is appended rather than replaced.
    for description, payload in updates.items():
        if description in written:
            continue
        body = b"\x00" + _GEOB_MIME + b"\x00\x00" + description.encode("latin1") + b"\x00" + payload
        rebuilt += b"GEOB" + _encode_frame_size(len(body), version) + b"\x00\x00" + body

    # Keep the tag the same size by absorbing the change into its padding.
    # Serato Offsets_ addresses the audio by byte position, so moving the
    # stream invalidates it and the waveform preview renders wrong.
    padding = declared - len(rebuilt)
    if padding < 0:
        raise TagFormatError(
            f"New frames exceed the tag's {declared} bytes by {-padding}; "
            "growing the tag would move the audio stream"
        )
    body_bytes = bytes(rebuilt) + b"\x00" * padding
    new_tag = tag[:6] + _synchsafe(len(body_bytes)) + body_bytes

    new_data = bytearray(data)
    if start == 0:
        # MP3: the tag sits at the head, followed by the audio stream.
        new_data[0:size] = new_tag
    else:
        # WAV: the tag lives in a RIFF chunk whose size, and the file's, follow.
        pad = size & 1
        new_data[start - 8 : start + size + pad] = (
            b"id3 " + struct.pack("<I", len(new_tag)) + new_tag + b"\x00" * (len(new_tag) & 1)
        )
        new_data[4:8] = struct.pack("<I", len(new_data) - 8)

    verify_geob_rewrite(bytes(data), bytes(new_data), updates, remove_geob=dropped_geob)

    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(bytes(new_data))
    temporary.replace(target)
    logger.info("audio_tags_written", path=str(target), frames=sorted(updates))
