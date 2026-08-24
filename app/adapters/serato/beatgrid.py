"""Encoding the Serato BeatGrid tag payload."""

from __future__ import annotations

import struct

from app.adapters.rekordbox.anlz import Beat

_HEADER = b"\x01\x00"


def encode_beatgrid(beats: list[Beat]) -> bytes | None:
    """
    Build a Serato BeatGrid payload from Rekordbox beats.

    Serato writes a single terminal marker holding the first downbeat and the
    tempo, and extrapolates the rest of the track from it. That form only
    describes a steady tempo, so tracks whose tempo varies are left alone for
    Serato to analyse itself.

    Args:
        beats: Beats in time order, as read from ANLZ.

    Returns:
        Fourteen-byte payload, or None when there are no beats or the tempo
        is not constant.
    """
    if not beats or len({beat.bpm for beat in beats}) > 1:
        return None

    downbeats = [beat for beat in beats if beat.number == 1] or beats
    anchor = downbeats[0]
    return _HEADER + struct.pack(">I", 1) + struct.pack(">ff", anchor.time_ms / 1000.0, anchor.bpm)
