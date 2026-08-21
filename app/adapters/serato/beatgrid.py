"""Encoding the Serato BeatGrid tag payload."""

from __future__ import annotations

import struct

from app.adapters.rekordbox.anlz import Beat

_HEADER = b"\x01\x00"

# Serato spaces beats evenly between markers. Rekordbox reports a smoothed
# tempo, so a run at one tempo can still drift; close the run before an
# interpolated beat strays this far from where Rekordbox puts it.
_MAX_DRIFT_MS = 10.0


def _drift_ms(beats: list[Beat], start: int, end: int) -> float:
    """
    Return the largest error from spacing beats evenly between two markers.

    Args:
        beats: All beats in time order.
        start: Index of the marker beat.
        end: Index of the next marker beat.

    Returns:
        Worst deviation in milliseconds for the beats between them.
    """
    first, last = beats[start].time_ms, beats[end].time_ms
    span = end - start
    step = (last - first) / span
    return max(
        (abs(beats[start + k].time_ms - (first + step * k)) for k in range(1, span)),
        default=0.0,
    )


def encode_beatgrid(beats: list[Beat]) -> bytes | None:
    """
    Build a Serato BeatGrid payload from Rekordbox beats.

    Beats are grouped into markers while they share a tempo and stay evenly
    spaced. Every marker but the last records how many beats reach the next
    marker; the last records the tempo it holds to the end of the track.

    Args:
        beats: Beats in time order, as read from ANLZ.

    Returns:
        Encoded payload, or None when there are no beats.
    """
    if not beats:
        return None

    # Markers open a tempo section. A section runs while the tempo holds and
    # evenly spaced beats stay close to Rekordbox's, so a steady track yields a
    # single terminal marker. A section is closed at the last beat that still
    # interpolated cleanly, never at the one that broke it.
    starts = [0]
    last_clean = 1
    for position in range(1, len(beats)):
        anchor = starts[-1]
        if beats[position].bpm != beats[anchor].bpm:
            # A tempo change belongs exactly at the beat that changed.
            starts.append(position)
            last_clean = position + 1
        elif _drift_ms(beats, anchor, position) > _MAX_DRIFT_MS:
            starts.append(max(last_clean, anchor + 1))
            last_clean = position
        else:
            last_clean = position

    markers = [
        (
            beats[start].time_ms / 1000.0,
            beats[start].bpm,
            (starts[i + 1] if i + 1 < len(starts) else start) - start,
        )
        for i, start in enumerate(starts)
    ]

    payload = bytearray(_HEADER + struct.pack(">I", len(markers)))
    for position, (start, tempo, beat_count) in enumerate(markers):
        if position < len(markers) - 1:
            payload += struct.pack(">fI", start, beat_count)
        else:
            payload += struct.pack(">ff", start, tempo)
    payload += b"\x00"
    return bytes(payload)
