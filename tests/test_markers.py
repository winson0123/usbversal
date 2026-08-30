"""Tests for the Serato Markers_ (first five cues) codec."""

from app.adapters.serato.markers import (
    decode_markers_v1,
    decode_markers_v1_mp4,
    encode_markers_v1,
    encode_markers_v1_mp4,
    markers_id3_to_mp4,
    markers_mp4_to_id3,
)
from app.adapters.serato.markers2 import Cue

# Serato-written otonoke leftover: cue 0 at 1456 ms, #CC0044.
_OTONOKE_MP4_MARKERS = bytes.fromhex(
    "02050000000e000005b0ffffffff00ffffffff00cc00440100"
    "ffffffffffffffff00ffffffff000000000000"
    "ffffffffffffffff00ffffffff000000000000"
    "ffffffffffffffff00ffffffff000000000000"
    "ffffffffffffffff00ffffffff000000000000"
    "000005ad00001bbc00ffffffff0027aae10300"
    "ffffffffffffffff00ffffffff000000000300"
    "ffffffffffffffff00ffffffff000000000300"
    "ffffffffffffffff00ffffffff000000000300"
    "ffffffffffffffff00ffffffff000000000300"
    "ffffffffffffffff00ffffffff000000000300"
    "ffffffffffffffff00ffffffff000000000300"
    "ffffffffffffffff00ffffffff000000000300"
    "ffffffffffffffff00ffffffff000000000300"
    "0000ffffff0000"
)


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


def test_mp4_markers_reads_a_serato_written_row() -> None:
    """MP4 markers uses raw milliseconds and 0xFFFFFFFF unset, not serato32."""
    cues = decode_markers_v1_mp4(_OTONOKE_MP4_MARKERS)

    assert cues == [Cue(slot=0, position_ms=1456, colour="#CC0044")]
    assert decode_markers_v1(_OTONOKE_MP4_MARKERS) == []


def test_mp4_markers_round_trips_the_first_five_cues() -> None:
    """ID3 and MP4 layouts carry the same slots after conversion."""
    cues = [
        Cue(slot=0, position_ms=70, colour="#31002E"),
        Cue(slot=1, position_ms=30015, colour="#00C4FF"),
    ]

    mp4 = encode_markers_v1_mp4(cues)
    assert len(mp4) == 279
    assert decode_markers_v1_mp4(mp4) == cues
    assert decode_markers_v1(markers_mp4_to_id3(mp4)) == cues
    assert decode_markers_v1_mp4(markers_id3_to_mp4(encode_markers_v1(cues))) == cues
