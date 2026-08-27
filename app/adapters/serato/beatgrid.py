"""Encoding the Serato BeatGrid tag payload."""

from __future__ import annotations

import struct

from app.adapters.rekordbox.anlz import Beat

_HEADER = b"\x01\x00"

# Rekordbox measures tempo once per bar, and those readings wobble by a tenth
# of a BPM around the real tempo. Anchoring on every reading would encode that
# jitter as tempo changes, so a marker is only opened when the tempo has moved
# further than this from the last one.
_TEMPO_STEP = 2.0


def _anchors(beats: list[Beat]) -> list[Beat]:
    """
    Return the beats worth anchoring a marker on.

    Args:
        beats: Beats in time order.

    Returns:
        The first beat, plus each beat whose tempo has moved materially since
        the previous anchor.
    """
    chosen = [beats[0]]
    for beat in beats:
        if abs(beat.bpm - chosen[-1].bpm) > _TEMPO_STEP:
            chosen.append(beat)
    return chosen


def _downbeats(beats: list[Beat]) -> list[Beat]:
    """Prefer bar-1 beats; fall back to every beat when none are numbered 1."""
    found = [beat for beat in beats if beat.number == 1]
    return found or beats


def encode_beatgrid(beats: list[Beat]) -> bytes | None:
    """
    Build a Serato BeatGrid payload from Rekordbox beats.

    A steady track becomes the single terminal marker Serato writes itself:
    the first downbeat and the tempo. A track whose tempo moves gains a
    non-terminal marker at each change, which is how transitions and other
    variable-tempo edits keep their grid.

    Args:
        beats: Beats in time order, as read from ANLZ.

    Returns:
        Encoded payload, or None when there are no beats.
    """
    if not beats:
        return None

    anchors = _anchors(_downbeats(beats))

    payload = bytearray(_HEADER + struct.pack(">I", len(anchors)))
    for index, anchor in enumerate(anchors):
        payload += _pack_anchor(index, anchor, anchors)
    return bytes(payload)


def _pack_anchor(index: int, anchor: Beat, anchors: list[Beat]) -> bytes:
    """
    Encode one beatgrid marker, terminal or not.

    Args:
        index: Marker index among ``anchors``.
        anchor: Beat this marker is placed on.
        anchors: Full marker list, for the following beat when non-terminal.

    Returns:
        Packed marker bytes.
    """
    position = anchor.time_ms / 1000.0
    if index >= len(anchors) - 1:
        return struct.pack(">ff", position, anchor.bpm)
    following = anchors[index + 1]
    bars = max(1, round((following.time_ms - anchor.time_ms) / (240000.0 / anchor.bpm)))
    return struct.pack(">fI", position, bars * 4)
