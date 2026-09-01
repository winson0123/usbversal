"""Regression tests: our GEOB writes must never disturb another tool's frames.

About a fifth of the reference library carries Mixed In Key frames (`Key`,
`Energy`, `CuePoints`, and its own unprefixed `BeatGrid`, distinct from
`Serato BeatGrid`), and one file carries Sound Forge frames. Nothing in this
codebase is meant to touch them. write_geob only rebuilds the frame
descriptions it is explicitly told to, but until now nothing proved it.
"""

from pathlib import Path

import pytest

from app.adapters.serato.tags import TagFormatError, read_geob, write_geob

_GEOB_MIME = b"application/octet-stream"

# Mixed In Key's own frame names. Sound Forge's exact
# frame name is not documented anywhere in this repo, so "Unknown Vendor Tag"
# stands in for it. The guarantee has to hold for any frame we don't own,
# not just the ones we happen to have a name for.
_FOREIGN_FRAMES = {
    "Key": b"8A",
    "Energy": b"\x05",
    "CuePoints": b'{"cues": []}',
    "BeatGrid": b"mixed-in-key-grid-bytes",
    "Unknown Vendor Tag": b"\x01\x02\x03",
}


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _geob_frame(description: str, payload: bytes) -> bytes:
    """Build one raw ID3v2.4 GEOB frame."""
    body = b"\x00" + _GEOB_MIME + b"\x00\x00" + description.encode("latin1") + b"\x00" + payload
    return b"GEOB" + _synchsafe(len(body)) + b"\x00\x00" + body


def _mp3(frames: list[bytes], *, padding: int) -> bytes:
    """Build a minimal ID3v2.4 MP3 carrying the given GEOB frames."""
    audio = b"\xff\xfb" + b"\x00" * 64
    body = b"".join(frames) + b"\x00" * padding
    tag = b"ID3" + bytes([4, 0, 0]) + _synchsafe(len(body)) + body
    return tag + audio


@pytest.fixture
def mixed_vendor_mp3(tmp_path: Path) -> Path:
    """An MP3 carrying foreign vendor frames alongside our own, with headroom."""
    frames = [_geob_frame(name, payload) for name, payload in _FOREIGN_FRAMES.items()]
    frames.append(_geob_frame("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00\x00"))
    frames.append(_geob_frame("Serato Markers2", b"\x01\x01"))
    target = tmp_path / "t.mp3"
    target.write_bytes(_mp3(frames, padding=64))
    return target


def test_foreign_vendor_frames_survive_a_beatgrid_write(mixed_vendor_mp3: Path) -> None:
    """Writing our own beatgrid leaves every foreign frame byte-identical."""
    before = {name: read_geob(mixed_vendor_mp3)[name] for name in _FOREIGN_FRAMES}

    write_geob(mixed_vendor_mp3, {"Serato BeatGrid": b"\x01\x00\x00\x00\x00\x01\x02\x03"})

    after = read_geob(mixed_vendor_mp3)
    for name, payload in before.items():
        assert after[name] == payload, name


def test_foreign_vendor_frames_survive_a_cue_write(mixed_vendor_mp3: Path) -> None:
    """A hot-cue write, not just a beatgrid write, leaves foreign frames alone."""
    before = {name: read_geob(mixed_vendor_mp3)[name] for name in _FOREIGN_FRAMES}

    write_geob(mixed_vendor_mp3, {"Serato Markers2": b"\x01\x01" + b"\x00" * 10})

    after = read_geob(mixed_vendor_mp3)
    for name, payload in before.items():
        assert after[name] == payload, name


def test_foreign_vendor_frames_survive_removal_of_our_own(mixed_vendor_mp3: Path) -> None:
    """Removing one of our own frames does not disturb anyone else's."""
    before = {name: read_geob(mixed_vendor_mp3)[name] for name in _FOREIGN_FRAMES}

    write_geob(mixed_vendor_mp3, {}, remove_geob={"Serato Markers2"})

    after = read_geob(mixed_vendor_mp3)
    for name, payload in before.items():
        assert after[name] == payload, name


def test_a_tight_tag_grows_instead_of_dropping_foreign_frames(tmp_path: Path) -> None:
    """No padding: the tag grows. Foreign frames stay; the audio is unchanged."""
    frames = [_geob_frame(name, payload) for name, payload in _FOREIGN_FRAMES.items()]
    frames.append(_geob_frame("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00\x00"))
    target = tmp_path / "t.mp3"
    original = _mp3(frames, padding=0)
    target.write_bytes(original)
    before = {name: read_geob(target)[name] for name in _FOREIGN_FRAMES}

    write_geob(target, {"Serato BeatGrid": b"\x01\x00" + b"\x00" * 200})

    after = read_geob(target)
    for name, payload in before.items():
        assert after[name] == payload, name
    assert after["Serato BeatGrid"] == b"\x01\x00" + b"\x00" * 200
    assert len(target.read_bytes()) > len(original)


def test_offsets_block_growing_a_tight_tag(tmp_path: Path) -> None:
    """Serato Offsets_ pins the audio; a tight tag must not move it."""
    frames = [_geob_frame("Serato Offsets_", b"\x00" * 16)]
    frames.append(_geob_frame("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00\x00"))
    target = tmp_path / "t.mp3"
    target.write_bytes(_mp3(frames, padding=0))
    before = target.read_bytes()

    with pytest.raises(TagFormatError):
        write_geob(target, {"Serato BeatGrid": b"\x01\x00" + b"\x00" * 200})

    assert target.read_bytes() == before
