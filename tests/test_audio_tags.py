"""Tests for reading and writing Serato GEOB frames in audio files."""

import shutil
import struct
from pathlib import Path

import pytest

from app.adapters.rekordbox.anlz import Beat
from app.adapters.serato.beatgrid import encode_beatgrid
from app.adapters.serato.tags import TagFormatError, read_geob, verify_geob_rewrite, write_geob

FIXTURES = Path(__file__).parent / "fixtures" / "serato"


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    """A writable copy of the unsynced fixture."""
    target = tmp_path / "t.wav"
    shutil.copy(FIXTURES / "Techno1.BEFORE.wav", target)
    return target


def _audio_chunk_offset(data: bytes) -> int:
    """Return the byte offset of the WAV's `data` chunk payload."""
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        if chunk == b"data":
            return offset + 8
        offset += 8 + size + (size & 1)
    raise AssertionError("no data chunk")


def _audio_chunk(path: Path) -> bytes:
    """Return the WAV's raw audio payload."""
    data = path.read_bytes()
    offset = _audio_chunk_offset(data)
    size = struct.unpack("<I", data[offset - 4 : offset])[0]
    return data[offset : offset + size]


def test_reads_the_serato_frames(wav: Path) -> None:
    """All three Serato frames are found in the fixture."""
    frames = read_geob(wav)

    assert set(frames) == {"Serato BeatGrid", "Serato Autotags", "Serato Markers2"}
    assert len(frames["Serato Markers2"]) == 470


def test_rewriting_nothing_leaves_the_file_identical(wav: Path) -> None:
    """A no-op write must not perturb a single byte."""
    original = wav.read_bytes()

    assert write_geob(wav, {}) is False
    assert wav.read_bytes() == original


def test_rewriting_a_frame_with_its_own_bytes_is_identical(wav: Path) -> None:
    """Round-tripping a payload through the writer changes nothing."""
    original = wav.read_bytes()
    frames = read_geob(wav)
    before = wav.stat().st_mtime_ns

    assert write_geob(wav, {"Serato Markers2": frames["Serato Markers2"]}) is False

    assert wav.read_bytes() == original
    assert wav.stat().st_mtime_ns == before


def test_one_changed_frame_still_rewrites(wav: Path) -> None:
    """A matching sibling does not skip a write that also has a new payload."""
    frames = read_geob(wav)

    assert (
        write_geob(
            wav,
            {
                "Serato BeatGrid": frames["Serato BeatGrid"],
                "Serato Markers2": b"\x01\x01",
            },
        )
        is True
    )
    assert read_geob(wav)["Serato Markers2"] == b"\x01\x01"
    assert read_geob(wav)["Serato BeatGrid"] == frames["Serato BeatGrid"]


def test_audio_survives_a_tag_change(wav: Path) -> None:
    """Editing tags must never touch the audio payload."""
    before = _audio_chunk(wav)

    assert write_geob(wav, {"Serato BeatGrid": b"\x01\x00\x00\x00\x00\x00\x00"}) is True

    assert _audio_chunk(wav) == before
    assert read_geob(wav)["Serato BeatGrid"] == b"\x01\x00\x00\x00\x00\x00\x00"


def test_untouched_frames_are_preserved(wav: Path) -> None:
    """Writing one frame leaves the others exactly as they were."""
    before = read_geob(wav)

    write_geob(wav, {"Serato Markers2": b"\x01\x01"})
    after = read_geob(wav)

    assert after["Serato BeatGrid"] == before["Serato BeatGrid"]
    assert after["Serato Autotags"] == before["Serato Autotags"]


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _riff_chunk(name: bytes, body: bytes) -> bytes:
    """
    Build one little-endian RIFF chunk with even padding.

    Args:
        name: Four-byte chunk id.
        body: Chunk payload.

    Returns:
        Header, payload, and a pad byte when the payload length is odd.
    """
    pad = b"\x00" if len(body) & 1 else b""
    return name + struct.pack("<I", len(body)) + body + pad


def _id3_tag(body: bytes = b"") -> bytes:
    """
    Build a minimal ID3v2.4 tag.

    Args:
        body: Declared tag body, with no extra padding.

    Returns:
        A complete ID3 header plus ``body``.
    """
    return b"ID3" + bytes([4, 0, 0]) + _synchsafe(len(body)) + body


def _wav_from_chunks(*chunks: bytes) -> bytes:
    """
    Wrap RIFF chunks in a WAVE file.

    Args:
        chunks: Complete ``fmt ``, ``data``, and optional later chunks.

    Returns:
        A complete WAVE file.
    """
    payload = b"".join(chunks)
    return b"RIFF" + struct.pack("<I", 4 + len(payload)) + b"WAVE" + payload


def _fmt_chunk() -> bytes:
    """Return a 16-bit mono PCM ``fmt `` chunk."""
    return _riff_chunk(b"fmt ", struct.pack("<HHIIHH", 1, 1, 44100, 88200, 2, 16))


def _data_chunk(pcm: bytes | None = None) -> bytes:
    """
    Return a ``data`` chunk.

    Args:
        pcm: Sample bytes. Sixteen silent frames when omitted.

    Returns:
        A complete ``data`` chunk.
    """
    if pcm is None:
        pcm = b"\x00\x00" * 16
    return _riff_chunk(b"data", pcm)


def _tagless_wav() -> bytes:
    """
    Build a RIFF WAVE that has fmt and data only.

    Returns:
        A complete WAVE file with no ``id3 `` chunk.
    """
    return _wav_from_chunks(_fmt_chunk(), _data_chunk())


def _wav_with_tight_id3(*, before_data: bool, list_after: bool = False) -> bytes:
    """
    Build a WAVE whose ``id3 `` has no padding.

    Args:
        before_data: Place ``id3 `` before ``data`` when True.
        list_after: Append a trailing ``LIST`` after ``id3 ``.

    Returns:
        A complete WAVE file with a zero-body ID3 tag.
    """
    id3 = _riff_chunk(b"id3 ", _id3_tag())
    pieces = [_fmt_chunk()]
    if before_data:
        pieces.append(id3)
        pieces.append(_data_chunk(b"\x01\x02" * 16))
    else:
        pieces.append(_data_chunk(b"\x01\x02" * 16))
        pieces.append(id3)
    if list_after:
        pieces.append(_riff_chunk(b"LIST", b"INFO"))
    return _wav_from_chunks(*pieces)


def test_non_riff_input_is_rejected(tmp_path: Path) -> None:
    """A RIFF file that is not WAVE fails rather than being mangled."""
    junk = tmp_path / "x.wav"
    junk.write_bytes(b"RIFF" + b"\x00" * 40)

    with pytest.raises(TagFormatError):
        read_geob(junk)


def test_read_geob_on_tagless_wav_is_empty(tmp_path: Path) -> None:
    """A valid WAVE with no id3 chunk has no Serato frames yet."""
    path = tmp_path / "bare.wav"
    path.write_bytes(_tagless_wav())

    assert read_geob(path) == {}


def test_tagless_wav_gains_id3_chunk(tmp_path: Path) -> None:
    """A WAVE without id3 gets a chunk; the data payload stays the same."""
    path = tmp_path / "bare.wav"
    path.write_bytes(_tagless_wav())
    before = _audio_chunk(path)

    write_geob(path, {"Serato BeatGrid": b"\x01\x00\x00\x00\x00\x00\x00"})

    assert read_geob(path)["Serato BeatGrid"] == b"\x01\x00\x00\x00\x00\x00\x00"
    assert _audio_chunk(path) == before
    assert b"id3 " in path.read_bytes()


def test_a_frame_the_file_never_carried_reads_back(wav: Path) -> None:
    """A brand new GEOB frame is appended, not silently dropped.

    A hand-run pass once found this path silently no-op'd when the frame did
    not already exist in the tag.
    """
    write_geob(wav, {"Serato Analysis": b"\x02\x01"})

    assert read_geob(wav)["Serato Analysis"] == b"\x02\x01"


def test_removed_frames_do_not_read_back(wav: Path) -> None:
    """A frame named for removal is gone, not merely unchanged."""
    assert write_geob(wav, {}, remove_geob={"Serato Autotags"}) is True

    assert "Serato Autotags" not in read_geob(wav)


def test_verify_accepts_an_unchanged_rewrite(wav: Path) -> None:
    """A rewrite that changes nothing passes verification."""
    original = wav.read_bytes()

    verify_geob_rewrite(original, original, {})


def test_verify_rejects_a_size_change_when_id3_is_before_data() -> None:
    """Growing an ``id3 `` that sits before ``data`` would move the audio."""
    original = _wav_with_tight_id3(before_data=True)

    with pytest.raises(TagFormatError, match="file size"):
        verify_geob_rewrite(original, original + b"\x00", {})


def test_tight_wav_id3_after_data_grows(tmp_path: Path) -> None:
    """A tight ``id3 `` after ``data`` grows; audio and a trailing LIST stay."""
    path = tmp_path / "after.wav"
    path.write_bytes(_wav_with_tight_id3(before_data=False, list_after=True))
    before = _audio_chunk(path)

    write_geob(path, {"Serato BeatGrid": b"\x01\x00\x00\x00\x00\x00\x00"})

    assert read_geob(path)["Serato BeatGrid"] == b"\x01\x00\x00\x00\x00\x00\x00"
    assert _audio_chunk(path) == before
    assert b"LIST" in path.read_bytes()


def test_tight_wav_id3_before_data_refuses_to_grow(tmp_path: Path) -> None:
    """A tight ``id3 `` before ``data`` must not move the audio stream."""
    path = tmp_path / "before.wav"
    original = _wav_with_tight_id3(before_data=True)
    path.write_bytes(original)

    with pytest.raises(TagFormatError, match="move the audio stream"):
        write_geob(path, {"Serato BeatGrid": b"\x01\x00\x00\x00\x00\x00\x00"})

    assert path.read_bytes() == original


def test_verify_rejects_a_moved_or_altered_audio_stream(wav: Path) -> None:
    """Corrupting the audio payload is caught even if the tag looks fine."""
    original = wav.read_bytes()
    start = _audio_chunk_offset(original)
    corrupted = bytearray(original)
    corrupted[start] ^= 0xFF

    with pytest.raises(TagFormatError, match="audio stream"):
        verify_geob_rewrite(original, bytes(corrupted), {})


def test_verify_rejects_a_frame_that_did_not_take(wav: Path) -> None:
    """A frame that does not read back as requested is caught before it is written."""
    original = wav.read_bytes()

    with pytest.raises(TagFormatError, match="Serato BeatGrid"):
        verify_geob_rewrite(original, original, {"Serato BeatGrid": b"not what is on disk"})


def test_verify_rejects_a_frame_meant_for_removal_still_present(wav: Path) -> None:
    """A removal that did not actually remove the frame is caught."""
    original = wav.read_bytes()

    with pytest.raises(TagFormatError, match="Serato BeatGrid"):
        verify_geob_rewrite(original, original, {}, remove_geob={"Serato BeatGrid"})


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


def test_no_beats_yields_no_grid() -> None:
    """A track with no analysis produces no payload."""
    assert encode_beatgrid([]) is None


def _bars(tempos: list[float], start_ms: int = 0) -> list[Beat]:
    """Build beats laying out one bar per tempo, four beats each."""
    beats: list[Beat] = []
    time = float(start_ms)
    for bpm in tempos:
        step = 60000.0 / bpm
        for number in range(1, 5):
            beats.append(Beat(number=number, bpm=bpm, time_ms=int(time)))
            time += step
    return beats


def test_tempo_jitter_does_not_open_markers() -> None:
    """Rekordbox measures per bar and those readings wobble; that is not a change."""
    beats = _bars([128.0, 128.1, 127.95, 128.05] * 4)

    payload = encode_beatgrid(beats)

    assert struct.unpack(">I", payload[2:6])[0] == 1


def test_a_real_tempo_change_opens_a_marker() -> None:
    """A transition between two tempos is anchored at the change."""
    beats = _bars([128.0] * 4 + [94.0] * 4)

    payload = encode_beatgrid(beats)
    count = struct.unpack(">I", payload[2:6])[0]
    _, terminal_bpm = struct.unpack(">ff", payload[6 + (count - 1) * 8 : 14 + (count - 1) * 8])

    assert count == 2
    assert round(terminal_bpm, 1) == 94.0


def test_a_ramp_is_anchored_at_each_step() -> None:
    """A gliding tempo gains a marker per meaningful step, not per bar."""
    beats = _bars([148.0] * 8 + [146.0, 144.0, 142.0, 140.0] + [140.0] * 8)

    count = struct.unpack(">I", encode_beatgrid(beats)[2:6])[0]

    assert 3 <= count <= 6, count


def test_terminal_bpm_is_the_settled_last_section() -> None:
    """The last anchor sits at the start of the final section, often still
    mid-ramp. Serato shows that marker's BPM, so it must be the tempo that
    holds, not the first reading of the section."""
    beats = _bars([148.8] * 8 + [146.0, 144.0, 142.0] + [140.87] + [140.0] * 8)

    payload = encode_beatgrid(beats)
    count = struct.unpack(">I", payload[2:6])[0]
    _, terminal_bpm = struct.unpack(">ff", payload[-8:])

    assert count >= 2
    assert round(terminal_bpm, 1) == 140.0


def test_non_terminal_markers_count_beats_to_the_next() -> None:
    """Every marker but the last says how many beats reach the next one."""
    beats = _bars([128.0] * 4 + [94.0] * 4)

    payload = encode_beatgrid(beats)
    position, beats_to_next = struct.unpack(">fI", payload[6:14])

    assert position == 0.0
    assert beats_to_next % 4 == 0
    assert beats_to_next > 0
