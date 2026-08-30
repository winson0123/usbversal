"""Encoding the Serato Markers_ tag (first five cues)."""

from __future__ import annotations

from app.adapters.serato.markers2 import Cue

_HEADER = b"\x02\x05" + (14).to_bytes(4, "big")
_ENTRY_COUNT = 14
_HOT_CUE_SLOTS = 5
_UNSET = b"\x7f\x7f\x7f\x7f"
_TYPE_CUE = 1
_TYPE_LOOP = 3
_FOOTER = b"\x07\x7f\x7f\x7f"
_EMPTY_FIELD = b"\x00\x7f\x7f\x7f\x7f\x7f"
_MP4_UNSET = b"\xff\xff\xff\xff"
_MP4_EMPTY_CUE = _MP4_UNSET + _MP4_UNSET + b"\x00" + _MP4_UNSET + b"\x00\x00\x00\x00\x00\x00"
_MP4_EMPTY_LOOP = _MP4_UNSET + _MP4_UNSET + b"\x00" + _MP4_UNSET + b"\x00\x00\x00\x00\x03\x00"
_MP4_ROW = 19
_MP4_FOOTER = b"\x00\x00\xff\xff\xff\x00\x00"
_MP4_LOOP_ROWS = 9


def _encode_serato32(red: int, green: int, blue: int) -> bytes:
    """
    Pack three bytes into Serato's 4-byte ``serato32`` form.

    Args:
        red: First plaintext byte (0-255).
        green: Second plaintext byte.
        blue: Third plaintext byte.

    Returns:
        Four bytes with a spare bit inserted after every seven payload bits.
    """
    z = blue & 0x7F
    y = ((blue >> 7) | (green << 1)) & 0x7F
    x = ((green >> 6) | (red << 2)) & 0x7F
    w = red >> 5
    return bytes((w, x, y, z))


def _decode_serato32(raw: bytes) -> tuple[int, int, int]:
    """
    Unpack a ``serato32`` value into three plaintext bytes.

    Args:
        raw: Four encoded bytes.

    Returns:
        ``(first, second, third)`` plaintext bytes.
    """
    w, x, y, z = raw
    blue = (z & 0x7F) | ((y & 0x01) << 7)
    green = ((y & 0x7F) >> 1) | ((x & 0x03) << 6)
    red = ((x & 0x7F) >> 2) | ((w & 0x07) << 5)
    return red, green, blue


def _position_field(position_ms: int | None) -> bytes:
    """
    Encode a cue start or end as the set-flag plus ``serato32`` time.

    Args:
        position_ms: Milliseconds, or None when the field is unset.

    Returns:
        Five bytes: ``00`` + time, or ``7f`` + ``7f 7f 7f 7f``.
    """
    if position_ms is None:
        return b"\x7f" + _UNSET
    return b"\x00" + _encode_serato32(
        (position_ms >> 16) & 0xFF,
        (position_ms >> 8) & 0xFF,
        position_ms & 0xFF,
    )


def _entry(*, position_ms: int | None, colour: str, kind: int) -> bytes:
    """
    Build one 22-byte Markers_ row.

    Args:
        position_ms: Start time for a set cue, or None when empty.
        colour: ``#RRGGBB`` used when the cue is set; ignored when empty.
        kind: ``1`` for a cue, ``3`` for a loop placeholder.

    Returns:
        Twenty-two bytes.
    """
    if position_ms is None:
        colour_bytes = b"\x00\x00\x00\x00"
    else:
        hex_colour = colour.lstrip("#")
        colour_bytes = _encode_serato32(
            int(hex_colour[0:2], 16),
            int(hex_colour[2:4], 16),
            int(hex_colour[4:6], 16),
        )
    return (
        _position_field(position_ms)
        + _position_field(None)
        + _EMPTY_FIELD
        + colour_bytes
        + bytes((kind, 0))
    )


def encode_markers_v1(cues: list[Cue]) -> bytes:
    """
    Encode the first five hot cues as a ``Serato Markers_`` payload.

    Serato prefers this tag over Markers2 when it is present, so leftover
    five-cue data on an MP3 hides the Markers2 pads. Slots 0-4 are written;
    the nine loop rows stay empty. The crate/library list still reads
    Markers2 for cues 6-8.

    Args:
        cues: Hot cues from Rekordbox. Slots outside 0-4 are ignored here.

    Returns:
        318-byte GEOB payload.
    """
    by_slot = {cue.slot: cue for cue in cues if 0 <= cue.slot < _HOT_CUE_SLOTS}
    entries = bytearray()
    for slot in range(_HOT_CUE_SLOTS):
        cue = by_slot.get(slot)
        if cue is None:
            entries += _entry(position_ms=None, colour="#000000", kind=_TYPE_CUE)
        else:
            entries += _entry(position_ms=cue.position_ms, colour=cue.colour, kind=_TYPE_CUE)
    for _ in range(_ENTRY_COUNT - _HOT_CUE_SLOTS):
        entries += _entry(position_ms=None, colour="#000000", kind=_TYPE_LOOP)
    return _HEADER + bytes(entries) + _FOOTER


def decode_markers_v1(payload: bytes) -> list[Cue]:
    """
    Read set hot cues from a ``Serato Markers_`` payload.

    Args:
        payload: Raw GEOB bytes.

    Returns:
        Cues in slot order. Empty when the payload is too short.
    """
    if len(payload) < 6 + _ENTRY_COUNT * 22:
        return []
    cues: list[Cue] = []
    for slot in range(_HOT_CUE_SLOTS):
        entry = payload[6 + slot * 22 : 6 + (slot + 1) * 22]
        if entry[0] != 0 or entry[1:5] == _UNSET:
            continue
        t_hi, t_mid, t_lo = _decode_serato32(entry[1:5])
        red, green, blue = _decode_serato32(entry[16:20])
        cues.append(
            Cue(
                slot=slot,
                position_ms=(t_hi << 16) | (t_mid << 8) | t_lo,
                colour=f"#{red:02X}{green:02X}{blue:02X}",
            )
        )
    return cues


def _is_mp4_markers(payload: bytes) -> bool:
    """
    Return whether ``payload`` is the MP4 ``markers`` layout.

    ID3 Markers_ uses serato32 times and ``0x7f`` unset. MP4 uses a raw
    millisecond ``uint32`` and ``0xFFFFFFFF`` unset.

    Args:
        payload: Raw Markers_ bytes.

    Returns:
        True when the first row uses the MP4 unset pattern.
    """
    if len(payload) < 6 + _MP4_ROW:
        return False
    return payload[6:10] == _MP4_UNSET or payload[10:14] == _MP4_UNSET


def encode_markers_v1_mp4(cues: list[Cue]) -> bytes:
    """
    Encode the first five hot cues as an MP4 ``markers`` payload.

    Serato ignores ID3-shaped Markers_ on M4A. Each row is 19 bytes: a
    raw big-endian start time, ``0xFFFFFFFF`` unused fields, raw RGB,
    and a type byte.

    Args:
        cues: Hot cues from Rekordbox. Slots outside 0-4 are ignored.

    Returns:
        Header, five cue rows, nine empty loop rows, and the colour footer.
    """
    by_slot = {cue.slot: cue for cue in cues if 0 <= cue.slot < _HOT_CUE_SLOTS}
    body = bytearray(_HEADER)
    for slot in range(_HOT_CUE_SLOTS):
        cue = by_slot.get(slot)
        if cue is None:
            body += _MP4_EMPTY_CUE
            continue
        hex_colour = cue.colour.lstrip("#")
        colour = bytes.fromhex(hex_colour)
        body += (
            cue.position_ms.to_bytes(4, "big")
            + _MP4_UNSET
            + b"\x00"
            + _MP4_UNSET
            + b"\x00"
            + colour
            + bytes((_TYPE_CUE, 0))
        )
    body += _MP4_EMPTY_LOOP * _MP4_LOOP_ROWS
    body += _MP4_FOOTER
    return bytes(body)


def decode_markers_v1_mp4(payload: bytes) -> list[Cue]:
    """
    Read set hot cues from an MP4 ``markers`` payload.

    Args:
        payload: Raw ``markers`` atom payload after the FLAC-style wrapper.

    Returns:
        Cues in slot order. Empty when the payload is too short.
    """
    if len(payload) < 6 + _HOT_CUE_SLOTS * _MP4_ROW:
        return []
    cues: list[Cue] = []
    for slot in range(_HOT_CUE_SLOTS):
        entry = payload[6 + slot * _MP4_ROW : 6 + (slot + 1) * _MP4_ROW]
        if entry[:4] == _MP4_UNSET:
            continue
        position = int.from_bytes(entry[:4], "big")
        colour = entry[14:17]
        cues.append(
            Cue(
                slot=slot,
                position_ms=position,
                colour=f"#{colour[0]:02X}{colour[1]:02X}{colour[2]:02X}",
            )
        )
    return cues


def markers_id3_to_mp4(payload: bytes) -> bytes:
    """
    Convert an ID3 Markers_ payload to the MP4 ``markers`` layout.

    Args:
        payload: ID3 or already-MP4 Markers_ bytes.

    Returns:
        MP4 ``markers`` bytes. Unchanged when already MP4.
    """
    if _is_mp4_markers(payload):
        return payload
    return encode_markers_v1_mp4(decode_markers_v1(payload))


def markers_mp4_to_id3(payload: bytes) -> bytes:
    """
    Convert an MP4 ``markers`` payload to the ID3 Markers_ layout.

    Args:
        payload: MP4 or already-ID3 Markers_ bytes.

    Returns:
        ID3 Markers_ bytes. Unchanged when already ID3.
    """
    if not _is_mp4_markers(payload):
        return payload
    return encode_markers_v1(decode_markers_v1_mp4(payload))
