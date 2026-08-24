"""Tests for reading and writing Serato GEOB frames in audio files."""

import shutil
import struct
from pathlib import Path

import pytest

from app.adapters.rekordbox.anlz import Beat
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.tags import TagFormatError, read_geob, write_geob

FIXTURES = Path(__file__).parent / "fixtures" / "serato"


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    """A writable copy of the unsynced fixture."""
    target = tmp_path / "t.wav"
    shutil.copy(FIXTURES / "Techno1.BEFORE.wav", target)
    return target


def _audio_chunk(path: Path) -> bytes:
    """Return the WAV's raw audio payload."""
    data = path.read_bytes()
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        if chunk == b"data":
            return data[offset + 8 : offset + 8 + size]
        offset += 8 + size + (size & 1)
    raise AssertionError("no data chunk")


def test_reads_the_serato_frames(wav: Path) -> None:
    """All three Serato frames are found in the fixture."""
    frames = read_geob(wav)

    assert set(frames) == {"Serato BeatGrid", "Serato Autotags", "Serato Markers2"}
    assert len(frames["Serato Markers2"]) == 470


def test_rewriting_nothing_leaves_the_file_identical(wav: Path) -> None:
    """A no-op write must not perturb a single byte."""
    original = wav.read_bytes()

    write_geob(wav, {})

    assert wav.read_bytes() == original


def test_rewriting_a_frame_with_its_own_bytes_is_identical(wav: Path) -> None:
    """Round-tripping a payload through the writer changes nothing."""
    original = wav.read_bytes()
    frames = read_geob(wav)

    write_geob(wav, {"Serato Markers2": frames["Serato Markers2"]})

    assert wav.read_bytes() == original


def test_audio_survives_a_tag_change(wav: Path) -> None:
    """Editing tags must never touch the audio payload."""
    before = _audio_chunk(wav)

    write_geob(wav, {"Serato BeatGrid": b"\x01\x00\x00\x00\x00\x00\x00"})

    assert _audio_chunk(wav) == before
    assert read_geob(wav)["Serato BeatGrid"] == b"\x01\x00\x00\x00\x00\x00\x00"


def test_untouched_frames_are_preserved(wav: Path) -> None:
    """Writing one frame leaves the others exactly as they were."""
    before = read_geob(wav)

    write_geob(wav, {"Serato Markers2": b"\x01\x01"})
    after = read_geob(wav)

    assert after["Serato BeatGrid"] == before["Serato BeatGrid"]
    assert after["Serato Autotags"] == before["Serato Autotags"]


def test_non_riff_input_is_rejected(tmp_path: Path) -> None:
    """A file with no id3 chunk fails rather than being mangled."""
    junk = tmp_path / "x.wav"
    junk.write_bytes(b"RIFF" + b"\x00" * 40)

    with pytest.raises(TagFormatError):
        read_geob(junk)


def _beat_times(payload: bytes) -> list[float]:
    """Beat positions Serato derives from a BeatGrid payload."""
    count = struct.unpack(">I", payload[2:6])[0]
    markers = []
    offset = 6
    for _ in range(count - 1):
        position, span = struct.unpack(">fI", payload[offset : offset + 8])
        offset += 8
        markers.append((position, span))
    terminal, _bpm = struct.unpack(">ff", payload[offset : offset + 8])
    markers.append((terminal, 0))

    times: list[float] = []
    for index in range(count - 1):
        position, span = markers[index]
        step = (markers[index + 1][0] - position) / span
        times.extend(position + step * k for k in range(span))
    times.append(markers[-1][0])
    return times


def test_steady_tempo_is_one_fourteen_byte_marker() -> None:
    """Serato's own analysis writes a single terminal marker and no trailer."""
    beats = [Beat(number=(i % 4) + 1, bpm=128.0, time_ms=int(i * 468.75)) for i in range(64)]

    payload = encode_beatgrid(beats)

    assert len(payload) == 14
    assert struct.unpack(">I", payload[2:6])[0] == 1
    position, bpm = struct.unpack(">ff", payload[6:14])
    assert (position, bpm) == (0.0, 128.0)


def test_marker_anchors_on_the_first_downbeat() -> None:
    """The anchor is the first beat of a bar, not merely the first beat."""
    beats = [
        Beat(number=3, bpm=120.0, time_ms=1000),
        Beat(number=4, bpm=120.0, time_ms=1500),
        Beat(number=1, bpm=120.0, time_ms=2000),
        Beat(number=2, bpm=120.0, time_ms=2500),
    ]

    position, _ = struct.unpack(">ff", encode_beatgrid(beats)[6:14])

    assert position == 2.0


def test_varying_tempo_is_left_to_serato() -> None:
    """A single marker cannot describe a changing tempo, so none is written."""
    beats = [
        Beat(number=1, bpm=120.0, time_ms=0),
        Beat(number=2, bpm=120.0, time_ms=500),
        Beat(number=3, bpm=140.0, time_ms=1000),
    ]

    assert encode_beatgrid(beats) is None


def test_no_beats_yields_no_grid() -> None:
    """A track with no analysis produces no payload."""
    assert encode_beatgrid([]) is None
