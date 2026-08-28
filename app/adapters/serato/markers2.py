"""Encoding and decoding the Serato Markers2 tag payload."""

from __future__ import annotations

import base64
import binascii
import struct
from dataclasses import dataclass

_HEADER = b"\x01\x01"
_LINE_LENGTH = 72
_B64_ALPHABET = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
_CUE = b"CUE"
_CUE_BODY_LENGTH = 13


@dataclass(frozen=True)
class Marker:
    """
    One raw Markers2 entry.

    Attributes:
        name: Entry name, such as CUE, COLOR, or BPMLOCK.
        body: Entry payload, kept verbatim for entries we do not interpret.
    """

    name: bytes
    body: bytes


@dataclass(frozen=True)
class Cue:
    """
    One Serato hot cue.

    Attributes:
        slot: Zero-based cue slot.
        position_ms: Cue position in milliseconds.
        colour: Cue colour as #RRGGBB.
        label: Cue name, empty when unnamed.
    """

    slot: int
    position_ms: int
    colour: str
    label: str = ""


def decode_markers(payload: bytes) -> list[Marker]:
    """
    Decode a Markers2 tag payload into its entries.

    Args:
        payload: Raw GEOB payload, including its two-byte header.

    Returns:
        Entries in file order; empty when the payload holds none.
    """
    encoded = bytes(c for c in payload[2:] if c not in b"\r\n\x00")
    if not encoded:
        return []
    try:
        blob = _decode_serato_b64(encoded)
    except (binascii.Error, ValueError):
        return []

    markers: list[Marker] = []
    offset = 2
    while offset < len(blob):
        end = blob.find(b"\x00", offset)
        if end < 0:
            break
        name = blob[offset:end]
        offset = end + 1
        if not name or offset + 4 > len(blob):
            break
        length = struct.unpack(">I", blob[offset : offset + 4])[0]
        offset += 4
        markers.append(Marker(name=name, body=blob[offset : offset + length]))
        offset += length
    return markers


def _decode_serato_b64(raw: bytes) -> bytes:
    """
    Decode Serato's wrapped, often unpadded base64.

    Python 3.11+ rejects a data length of 1 more than a multiple of 4
    (``AAAAA`` plus padding). Real tags sometimes have that leftover after
    newlines and NULs are stripped, so one impossible character is dropped
    rather than failing the whole sync.

    Args:
        raw: Base64 bytes, possibly including wrap or junk.

    Returns:
        Decoded payload bytes.

    Raises:
        binascii.Error: The remaining text is still not valid base64.
    """
    encoded = bytes(character for character in raw if character in _B64_ALPHABET)
    if len(encoded) % 4 == 1:
        encoded = encoded[:-1]
    if not encoded:
        return b""
    return base64.b64decode(encoded + b"=" * ((-len(encoded)) % 4))


def encode_markers(markers: list[Marker], *, payload_size: int | None = None) -> bytes:
    """
    Encode entries into a Markers2 tag payload.

    Args:
        markers: Entries to write, in order.
        payload_size: Pad the payload to this many bytes, as Serato does so a
            tag can be rewritten without resizing it.

    Returns:
        Raw GEOB payload ready to store in the tag.
    """
    blob = bytearray(_HEADER)
    for marker in markers:
        blob += marker.name + b"\x00" + struct.pack(">I", len(marker.body)) + marker.body
    blob += b"\x00"

    encoded = base64.b64encode(bytes(blob))
    wrapped = b"\n".join(
        encoded[i : i + _LINE_LENGTH] for i in range(0, len(encoded), _LINE_LENGTH)
    )
    payload = _HEADER + wrapped
    if payload_size is not None and len(payload) < payload_size:
        payload += b"\x00" * (payload_size - len(payload))
    return payload


def cue_to_marker(cue: Cue) -> Marker:
    """
    Build a CUE entry from a hot cue.

    Args:
        cue: Hot cue to encode.

    Returns:
        Marker holding the encoded cue.
    """
    colour = cue.colour.lstrip("#")
    body = (
        b"\x00"
        + bytes([cue.slot])
        + struct.pack(">I", cue.position_ms)
        + b"\x00"
        + bytes.fromhex(colour)
        + b"\x00\x00"
        + cue.label.encode("latin1")
        + b"\x00"
    )
    return Marker(name=_CUE, body=body)


def marker_to_cue(marker: Marker) -> Cue | None:
    """
    Read a CUE entry back into a hot cue.

    Args:
        marker: Entry to interpret.

    Returns:
        Cue, or None when the entry is not a usable cue.
    """
    if marker.name != _CUE or len(marker.body) < _CUE_BODY_LENGTH:
        return None
    body = marker.body
    red, green, blue = body[7:10]
    return Cue(
        slot=body[1],
        position_ms=struct.unpack(">I", body[2:6])[0],
        colour=f"#{red:02X}{green:02X}{blue:02X}",
        label=body[12:].split(b"\x00")[0].decode("latin1"),
    )


def replace_cues(markers: list[Marker], cues: list[Cue]) -> list[Marker]:
    """
    Replace the CUE entries in a marker list, preserving all others.

    Entries this tool does not interpret, such as COLOR and BPMLOCK, are kept
    verbatim and in place.

    Args:
        markers: Existing entries from the file.
        cues: Hot cues to write.

    Returns:
        New entry list with cues substituted.
    """
    kept = [marker for marker in markers if marker.name != _CUE]
    return kept + [cue_to_marker(cue) for cue in sorted(cues, key=lambda c: c.slot)]
