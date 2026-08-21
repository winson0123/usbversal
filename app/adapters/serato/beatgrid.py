"""Encoding the Serato BeatGrid tag payload."""

from __future__ import annotations

import struct

from app.adapters.rekordbox.anlz import Beat

_HEADER = b"\x01\x00"


def encode_beatgrid(beats: list[Beat]) -> bytes | None:
    """
    Build a Serato BeatGrid payload from Rekordbox beats.

    Rekordbox records every beat, and Serato's format can hold a marker per
    beat, so each one is carried across directly. Every marker but the last
    reaches the next in a single beat; the last records the tempo it holds to
    the end of the track.

    Args:
        beats: Beats in time order, as read from ANLZ.

    Returns:
        Encoded payload, or None when there are no beats.
    """
    if not beats:
        return None

    payload = bytearray(_HEADER + struct.pack(">I", len(beats)))
    for beat in beats[:-1]:
        payload += struct.pack(">fI", beat.time_ms / 1000.0, 1)
    payload += struct.pack(">ff", beats[-1].time_ms / 1000.0, beats[-1].bpm)
    payload += b"\x00"
    return bytes(payload)
