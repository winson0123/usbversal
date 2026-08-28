"""Compact backup of an audio file's tag region, not a second copy of the song.

Usbversal only rewrites ID3 / RIFF id3 / FLAC metadata. The audio payload is
verified unchanged. A backup therefore stores the bytes around that payload
(the head and optional tail) plus hashes, so rollback can splice the original
tag back onto the current audio.

A destroyed or rewritten audio stream cannot be reconstructed from this
delta -- that is the size trade-off against copying a 200 GB library twice.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

_MAGIC = b"UVSD1\n"
_AUDIO_SUFFIXES = frozenset({".mp3", ".wav", ".flac", ".aiff", ".aif", ".m4a"})
_STRATEGY_SUFFIX = "suffix"
_STRATEGY_RIFF = "riff"


class AudioDeltaError(ValueError):
    """Raised when an audio container cannot be split into a tag delta."""


def is_audio_backup_path(path: Path) -> bool:
    """
    Return whether ``path`` is an audio file we should try to store as a delta.

    Args:
        path: Source file on the mount.

    Returns:
        True for recognised audio suffixes.
    """
    return path.suffix.lower() in _AUDIO_SUFFIXES


def encode_audio_delta(data: bytes) -> bytes:
    """
    Build a self-contained delta from an audio file's current bytes.

    Args:
        data: Whole audio file.

    Returns:
        Delta payload to store in the backup directory.

    Raises:
        AudioDeltaError: The container is not MP3, WAV, or FLAC, or has no
            isolatable audio payload.
    """
    start, size, strategy = _audio_span(data)
    audio = data[start : start + size]
    head = data[:start]
    tail = data[start + size :]
    header = {
        "original_size": len(data),
        "original_sha256": hashlib.sha256(data).hexdigest(),
        "audio_sha256": hashlib.sha256(audio).hexdigest(),
        "audio_size": size,
        "strategy": strategy,
    }
    payload = bytearray(_MAGIC)
    payload += json.dumps(header, separators=(",", ":")).encode("ascii")
    payload += b"\n"
    payload += struct.pack(">I", len(head))
    payload += head
    payload += struct.pack(">I", len(tail))
    payload += tail
    return bytes(payload)


def apply_audio_delta(current: bytes, delta: bytes) -> bytes:
    """
    Splice a stored tag-region delta onto the audio still on disk.

    Args:
        current: File bytes currently on the mount.
        delta: Payload from ``encode_audio_delta``.

    Returns:
        Reconstructed original file bytes.

    Raises:
        AudioDeltaError: The delta is corrupt, or the current audio payload
            no longer matches the backed-up stream.
    """
    header, head, tail = _parse_delta(delta)
    original_sha = header["original_sha256"]
    if hashlib.sha256(current).hexdigest() == original_sha:
        return current
    audio = _extract_audio(current, header)
    expected = header["audio_sha256"]
    if hashlib.sha256(audio).hexdigest() != expected:
        raise AudioDeltaError(
            "Current audio stream does not match the backup; "
            "the file cannot be reconstructed from a tag delta"
        )
    return head + audio + tail


def _audio_span(data: bytes) -> tuple[int, int, str]:
    """
    Return (start, size, strategy) of the raw audio payload.

    Args:
        data: Whole audio file.

    Returns:
        Offset, length, and how rollback should find the payload later.

    Raises:
        AudioDeltaError: Unrecognised container or missing audio payload.
    """
    if data[:3] == b"ID3":
        tag_size = 10 + _unsynchsafe(data[6:10])
        return tag_size, len(data) - tag_size, _STRATEGY_SUFFIX
    if data[:4] == b"fLaC":
        start = _flac_audio_start(data)
        return start, len(data) - start, _STRATEGY_SUFFIX
    if data[:4] == b"RIFF":
        offset = 12
        while offset + 8 <= len(data):
            chunk = data[offset : offset + 4]
            size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
            if chunk == b"data":
                return offset + 8, size, _STRATEGY_RIFF
            offset += 8 + size + (size & 1)
        raise AudioDeltaError("No data chunk in WAV")
    raise AudioDeltaError("Unrecognised audio container")


def _extract_audio(current: bytes, header: dict[str, object]) -> bytes:
    """
    Locate the audio payload in a (possibly retagged) file.

    Args:
        current: File bytes on the mount after a tag write.
        header: Parsed delta header.

    Returns:
        The audio payload bytes.

    Raises:
        AudioDeltaError: The strategy is unknown or the payload cannot be found.
    """
    audio_size = int(header["audio_size"])
    strategy = str(header["strategy"])
    if strategy == _STRATEGY_SUFFIX:
        if len(current) < audio_size:
            raise AudioDeltaError("Current file is shorter than the backed-up audio")
        return current[-audio_size:]
    if strategy == _STRATEGY_RIFF:
        start, size, _ = _audio_span(current)
        return current[start : start + size]
    raise AudioDeltaError(f"Unknown delta strategy {strategy!r}")


def _parse_delta(delta: bytes) -> tuple[dict[str, object], bytes, bytes]:
    """
    Split a delta payload into header, head, and tail.

    Args:
        delta: Bytes written by ``encode_audio_delta``.

    Returns:
        Header dict, bytes before the audio, bytes after the audio.

    Raises:
        AudioDeltaError: Magic, header, or length prefix is invalid.
    """
    if not delta.startswith(_MAGIC):
        raise AudioDeltaError("Not a usbversal audio delta")
    rest = delta[len(_MAGIC) :]
    line, separator, blob = rest.partition(b"\n")
    if not separator:
        raise AudioDeltaError("Audio delta header is truncated")
    try:
        header = json.loads(line.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AudioDeltaError("Audio delta header is not JSON") from exc
    if len(blob) < 4:
        raise AudioDeltaError("Audio delta is truncated")
    head_len = struct.unpack(">I", blob[:4])[0]
    head = blob[4 : 4 + head_len]
    after_head = blob[4 + head_len :]
    if len(head) != head_len or len(after_head) < 4:
        raise AudioDeltaError("Audio delta head is truncated")
    tail_len = struct.unpack(">I", after_head[:4])[0]
    tail = after_head[4 : 4 + tail_len]
    if len(tail) != tail_len:
        raise AudioDeltaError("Audio delta tail is truncated")
    return header, head, tail


def _unsynchsafe(raw: bytes) -> int:
    """Decode a 28-bit synchsafe big-endian value."""
    return (raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3]


def _flac_audio_start(data: bytes) -> int:
    """
    Return the byte offset of the first FLAC audio frame.

    Args:
        data: Whole FLAC file.

    Returns:
        Offset immediately after the last metadata block.

    Raises:
        AudioDeltaError: The metadata block chain is incomplete.
    """
    offset = 4
    while offset + 4 <= len(data):
        last = bool(data[offset] & 0x80)
        length = int.from_bytes(data[offset + 1 : offset + 4], "big")
        offset += 4 + length
        if last:
            return offset
    raise AudioDeltaError("FLAC file has no last metadata block")
