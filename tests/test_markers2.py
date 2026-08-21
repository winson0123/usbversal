"""Tests for the Serato Markers2 codec, against known-good Lexicon output."""

import struct
from pathlib import Path

from app.adapters.serato.markers2 import (
    Cue,
    decode_markers,
    encode_markers,
    marker_to_cue,
    replace_cues,
)

FIXTURES = Path(__file__).parent / "fixtures" / "serato"

# Serato's colours for the two cues Lexicon wrote into Techno1.AFTER.wav.
AFTER_CUES = [
    Cue(slot=0, position_ms=0, colour="#CC0044"),
    Cue(slot=1, position_ms=441, colour="#0088CC"),
]


def _riff_id3(path: Path) -> bytes:
    """Return the ID3 stream stored in a WAV's `id3 ` chunk."""
    data = path.read_bytes()
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        if chunk == b"id3 ":
            return data[offset + 8 : offset + 8 + size]
        offset += 8 + size + (size & 1)
    raise AssertionError(f"no id3 chunk in {path}")


def _markers2_payload(path: Path) -> bytes:
    """Return the raw Serato Markers2 GEOB payload from a WAV fixture."""
    tag = _riff_id3(path)

    def synch(raw: bytes) -> int:
        return (raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3]

    offset, end = 10, 10 + synch(tag[6:10])
    while offset + 10 <= min(end, len(tag)):
        frame_id = tag[offset : offset + 4]
        if frame_id == b"\x00\x00\x00\x00":
            break
        size = synch(tag[offset + 4 : offset + 8])
        body = tag[offset + 10 : offset + 10 + size]
        offset += 10 + size
        if frame_id != b"GEOB":
            continue
        cursor = 1
        for _ in range(3):
            cursor = body.find(b"\x00", cursor) + 1
        if body[:cursor].find(b"Serato Markers2") != -1:
            return body[cursor:]
    raise AssertionError(f"no Serato Markers2 frame in {path}")


def test_before_fixture_holds_only_colour_and_bpmlock() -> None:
    """The unsynced fixture has no cues."""
    markers = decode_markers(_markers2_payload(FIXTURES / "Techno1.BEFORE.wav"))

    assert [m.name for m in markers] == [b"COLOR", b"BPMLOCK"]


def test_after_fixture_decodes_to_the_documented_cues() -> None:
    """The synced fixture holds the two cues Lexicon wrote."""
    markers = decode_markers(_markers2_payload(FIXTURES / "Techno1.AFTER.wav"))
    cues = [c for c in (marker_to_cue(m) for m in markers) if c is not None]

    assert cues == AFTER_CUES


def test_writing_cues_onto_before_reproduces_after_exactly() -> None:
    """The encoder is correct if it turns BEFORE into AFTER byte for byte.

    Both payloads come from Lexicon, so this is an oracle rather than a
    restatement of our own encoding.
    """
    before = _markers2_payload(FIXTURES / "Techno1.BEFORE.wav")
    after = _markers2_payload(FIXTURES / "Techno1.AFTER.wav")

    rebuilt = encode_markers(
        replace_cues(decode_markers(before), AFTER_CUES),
        payload_size=len(after),
    )

    assert rebuilt == after


def test_round_trip_preserves_unhandled_entries() -> None:
    """COLOR and BPMLOCK survive a decode and re-encode untouched."""
    payload = _markers2_payload(FIXTURES / "Techno1.AFTER.wav")
    markers = decode_markers(payload)

    assert encode_markers(markers, payload_size=len(payload)) == payload


def test_replacing_cues_keeps_other_entries_and_drops_old_cues() -> None:
    """Rewriting cues leaves COLOR and BPMLOCK in place."""
    markers = decode_markers(_markers2_payload(FIXTURES / "Techno1.AFTER.wav"))

    replaced = replace_cues(markers, [Cue(slot=0, position_ms=1234, colour="#112233")])

    assert [m.name for m in replaced] == [b"COLOR", b"BPMLOCK", b"CUE"]
    assert marker_to_cue(replaced[-1]) == Cue(slot=0, position_ms=1234, colour="#112233")


def test_cue_round_trips_through_encoding() -> None:
    """A cue survives encoding and decoding unchanged."""
    from app.adapters.serato.markers2 import cue_to_marker

    cue = Cue(slot=3, position_ms=98765, colour="#0A0B0C", label="drop")

    assert marker_to_cue(cue_to_marker(cue)) == cue
