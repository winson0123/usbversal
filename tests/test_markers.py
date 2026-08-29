"""Tests for the Serato Markers_ (first five cues) codec."""

from app.adapters.serato.markers import decode_markers_v1, encode_markers_v1
from app.adapters.serato.markers2 import Cue


def test_markers_v1_round_trips_the_first_five_cues() -> None:
    """Slots 0-4 survive encode/decode; later slots are Markers2-only."""
    cues = [
        Cue(slot=0, position_ms=665, colour="#FF0017"),
        Cue(slot=3, position_ms=142140, colour="#CCCC00"),
        Cue(slot=6, position_ms=162346, colour="#0000FF"),
    ]

    payload = encode_markers_v1(cues)
    decoded = decode_markers_v1(payload)

    assert len(payload) == 318
    assert decoded == [
        Cue(slot=0, position_ms=665, colour="#FF0017"),
        Cue(slot=3, position_ms=142140, colour="#CCCC00"),
    ]


def test_markers_v1_encodes_the_known_cc0000_colour() -> None:
    """Holzhaus documents #CC0000 as serato32 06 30 00 00."""
    payload = encode_markers_v1([Cue(slot=0, position_ms=0, colour="#CC0000")])
    first = payload[6:28]
    assert first[16:20] == b"\x06\x30\x00\x00"
    assert decode_markers_v1(payload)[0].colour == "#CC0000"
