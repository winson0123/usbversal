"""Encoding the Serato BeatGrid tag payload."""

from __future__ import annotations

import struct

from app.adapters.rekordbox.anlz import Beat

_HEADER = b"\x01\x00"


def encode_beatgrid(beats: list[Beat]) -> bytes | None:
    """
    Build a Serato BeatGrid payload from Rekordbox beats.

    Runs of beats sharing a tempo collapse into one marker. Every marker but
    the last stores how many beats reach the next marker; the last stores the
    tempo it holds to the end of the track.

    Args:
        beats: Beats in time order, as read from ANLZ.

    Returns:
        Encoded payload, or None when there are no beats.
    """
    if not beats:
        return None

    markers: list[tuple[float, float, int]] = []
    index = 0
    while index < len(beats):
        tempo = beats[index].bpm
        run_end = index
        while run_end + 1 < len(beats) and beats[run_end + 1].bpm == tempo:
            run_end += 1
        markers.append((beats[index].time_ms / 1000.0, tempo, run_end - index))
        index = run_end + 1

    payload = bytearray(_HEADER + struct.pack(">I", len(markers)))
    for position, (start, tempo, beat_count) in enumerate(markers):
        if position < len(markers) - 1:
            payload += struct.pack(">fI", start, beat_count)
        else:
            payload += struct.pack(">ff", start, tempo)
    payload += b"\x00"
    return bytes(payload)
