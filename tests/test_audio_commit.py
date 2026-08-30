"""Tests for the audio-file commit path that must not leave a 0-byte song."""

import os
import struct
from io import BytesIO
from pathlib import Path

import pytest

from app.adapters.serato.tags import (
    TagFormatError,
    _commit_audio_bytes,
    _seek_chunk,
    read_geob,
    write_geob,
)

_GEOB_MIME = b"application/octet-stream"


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


def test_write_geob_refuses_an_empty_file(tmp_path: Path) -> None:
    """An empty song is not rewritten; the path stays empty."""
    target = tmp_path / "empty.mp3"
    target.write_bytes(b"")

    with pytest.raises(TagFormatError, match="empty"):
        write_geob(target, {"Serato Markers2": b"\x01\x01"})

    assert target.stat().st_size == 0


def test_write_geob_promotes_a_leftover_tmp(tmp_path: Path) -> None:
    """A leftover .tmp is swapped onto an empty destination before the write."""
    payload = b"\x01\x01" + b"\x00" * 8
    rebuilt = _mp3([_geob_frame("Serato Markers2", payload)], padding=64)
    target = tmp_path / "t.mp3"
    target.write_bytes(b"")
    (tmp_path / "t.mp3.tmp").write_bytes(rebuilt)

    assert write_geob(target, {"Serato Markers2": payload}) is False
    assert target.read_bytes() == rebuilt
    assert read_geob(target)["Serato Markers2"] == payload
    assert not (tmp_path / "t.mp3.tmp").exists()


def test_commit_refuses_a_truncated_payload(tmp_path: Path) -> None:
    """A rebuilt file shorter than half the original is not written."""
    target = tmp_path / "t.mp3"
    original = b"x" * 1000
    target.write_bytes(original)

    with pytest.raises(TagFormatError, match="truncated"):
        _commit_audio_bytes(target, b"yy", original)

    assert target.read_bytes() == original


def test_commit_same_size_patches_without_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A same-size rewrite must not copy the song through a .tmp replace."""
    replaced: list[Path] = []

    original_replace = Path.replace

    def track_replace(self: Path, dest: Path) -> Path:
        """Record a replace so the test can forbid it."""
        replaced.append(Path(dest))
        return original_replace(self, dest)

    monkeypatch.setattr(Path, "replace", track_replace)
    target = tmp_path / "t.mp3"
    original = b"x" * 100 + b"audio-payload"
    new_data = b"y" * 100 + b"audio-payload"
    target.write_bytes(original)

    _commit_audio_bytes(target, new_data, original)

    assert replaced == []
    assert not (tmp_path / "t.mp3.tmp").exists()
    assert target.read_bytes() == new_data


def test_write_geob_same_size_patches_without_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A padded MP3 GEOB rewrite must patch in place, not replace the file."""
    original_replace = Path.replace
    replaced: list[Path] = []

    def track_replace(self: Path, dest: Path) -> Path:
        """Record a replace so the test can forbid it."""
        replaced.append(Path(dest))
        return original_replace(self, dest)

    monkeypatch.setattr(Path, "replace", track_replace)
    first = b"\x01\x01" + b"\x00" * 8
    second = b"\x01\x02" + b"\x00" * 8
    target = tmp_path / "t.mp3"
    target.write_bytes(_mp3([_geob_frame("Serato Markers2", first)], padding=64))

    assert write_geob(target, {"Serato Markers2": second}) is True

    assert replaced == []
    assert not (tmp_path / "t.mp3.tmp").exists()
    assert read_geob(target)["Serato Markers2"] == second


def test_commit_restores_the_span_when_in_place_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed in-place write puts the original span back."""
    target = tmp_path / "t.mp3"
    original = b"x" * 100
    target.write_bytes(original)

    fsync_calls = {"n": 0}
    real_fsync = os.fsync

    def boom(fd: int) -> None:
        """Fail the first fsync so restore can still flush."""
        fsync_calls["n"] += 1
        if fsync_calls["n"] == 1:
            raise OSError("disk")
        real_fsync(fd)

    monkeypatch.setattr("app.adapters.serato.tags.os.fsync", boom)

    with pytest.raises(TagFormatError, match="in-place"):
        _commit_audio_bytes(target, b"y" * 100, original)

    assert target.read_bytes() == original


def _tagless_wav() -> bytes:
    """
    Build a RIFF WAVE that has fmt and data only.

    Returns:
        A complete WAVE file with no ``id3 `` chunk.
    """
    fmt = struct.pack("<HHIIHH", 1, 1, 44100, 88200, 2, 16)
    pcm = b"\x00\x00" * 16
    chunks = b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


def test_commit_wav_append_does_not_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tagless WAVE must grow by header patch plus append, not replace."""
    original_replace = Path.replace
    replaced: list[Path] = []

    def track_replace(self: Path, dest: Path) -> Path:
        """Record a replace so the test can forbid it."""
        replaced.append(Path(dest))
        return original_replace(self, dest)

    monkeypatch.setattr(Path, "replace", track_replace)
    original = _tagless_wav()
    tail = b"id3 " + struct.pack("<I", 10) + b"ID3" + b"\x00" * 7
    new_data = bytearray(original + tail)
    new_data[4:8] = struct.pack("<I", len(new_data) - 8)
    target = tmp_path / "t.wav"
    target.write_bytes(original)

    _commit_audio_bytes(target, bytes(new_data), original)

    assert replaced == []
    assert not (tmp_path / "t.wav.tmp").exists()
    assert target.read_bytes() == bytes(new_data)


def test_write_geob_tagless_wav_does_not_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_geob on a tagless WAVE must not copy the audio through replace."""
    original_replace = Path.replace
    replaced: list[Path] = []

    def track_replace(self: Path, dest: Path) -> Path:
        """Record a replace so the test can forbid it."""
        replaced.append(Path(dest))
        return original_replace(self, dest)

    monkeypatch.setattr(Path, "replace", track_replace)
    target = tmp_path / "t.wav"
    target.write_bytes(_tagless_wav())

    assert write_geob(target, {"Serato Markers2": b"\x01\x01" + b"\x00" * 8}) is True

    assert replaced == []
    assert not (tmp_path / "t.wav.tmp").exists()
    assert read_geob(target)["Serato Markers2"] == b"\x01\x01" + b"\x00" * 8


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


def _data_chunk(pcm: bytes) -> bytes:
    """
    Return a ``data`` chunk.

    Args:
        pcm: Sample bytes.

    Returns:
        A complete ``data`` chunk.
    """
    return _riff_chunk(b"data", pcm)


def test_write_geob_grows_wav_id3_after_data_without_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Growing an ``id3 `` after ``data`` must not copy the audio through replace."""
    original_replace = Path.replace
    replaced: list[Path] = []

    def track_replace(self: Path, dest: Path) -> Path:
        """Record a replace so the test can forbid it."""
        replaced.append(Path(dest))
        return original_replace(self, dest)

    monkeypatch.setattr(Path, "replace", track_replace)
    pcm = b"\x01\x02" * 16
    original = _wav_from_chunks(
        _fmt_chunk(),
        _data_chunk(pcm),
        _riff_chunk(b"id3 ", _id3_tag()),
        _riff_chunk(b"LIST", b"INFO"),
    )
    target = tmp_path / "t.wav"
    target.write_bytes(original)

    assert write_geob(target, {"Serato Markers2": b"\x01\x01" + b"\x00" * 8}) is True

    assert replaced == []
    assert not (tmp_path / "t.wav.tmp").exists()
    assert read_geob(target)["Serato Markers2"] == b"\x01\x01" + b"\x00" * 8
    audio_end = 12 + 24 + 8 + len(pcm)
    assert target.read_bytes()[8:audio_end] == original[8:audio_end]
    assert b"LIST" in target.read_bytes()


def test_commit_restores_wav_when_tail_rewrite_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed WAV tail rewrite restores the original id3 and LIST."""
    pcm = b"\x01\x02" * 16
    original = _wav_from_chunks(
        _fmt_chunk(),
        _data_chunk(pcm),
        _riff_chunk(b"id3 ", _id3_tag()),
        _riff_chunk(b"LIST", b"INFO"),
    )
    new_data = _wav_from_chunks(
        _fmt_chunk(),
        _data_chunk(pcm),
        _riff_chunk(b"id3 ", _id3_tag(b"\x00" * 64)),
        _riff_chunk(b"LIST", b"INFO"),
    )
    target = tmp_path / "t.wav"
    target.write_bytes(original)

    fsync_calls = {"n": 0}
    real_fsync = os.fsync

    def boom(fd: int) -> None:
        """Fail the first fsync so restore can still flush."""
        fsync_calls["n"] += 1
        if fsync_calls["n"] == 1:
            raise OSError("disk")
        real_fsync(fd)

    monkeypatch.setattr("app.adapters.serato.tags.os.fsync", boom)

    with pytest.raises(TagFormatError, match="WAV append"):
        _commit_audio_bytes(target, new_data, original)

    assert target.read_bytes() == original


def test_commit_restores_wav_when_append_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed WAV append restores the original size and RIFF header."""
    original = _tagless_wav()
    tail = b"id3 " + struct.pack("<I", 10) + b"ID3" + b"\x00" * 7
    new_data = bytearray(original + tail)
    new_data[4:8] = struct.pack("<I", len(new_data) - 8)
    target = tmp_path / "t.wav"
    target.write_bytes(original)

    fsync_calls = {"n": 0}
    real_fsync = os.fsync

    def boom(fd: int) -> None:
        """Fail the first fsync so restore can still flush."""
        fsync_calls["n"] += 1
        if fsync_calls["n"] == 1:
            raise OSError("disk")
        real_fsync(fd)

    monkeypatch.setattr("app.adapters.serato.tags.os.fsync", boom)

    with pytest.raises(TagFormatError, match="WAV append"):
        _commit_audio_bytes(target, bytes(new_data), original)

    assert target.read_bytes() == original


class _CountingBytesIO(BytesIO):
    """A stream that records how many bytes ``read`` actually copied."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size: int | None = -1) -> bytes:
        """Read bytes and add the copy size to ``bytes_read``."""
        data = super().read(-1 if size is None else size)
        self.bytes_read += len(data)
        return data


def test_seek_chunk_does_not_copy_the_wav_data() -> None:
    """Walking RIFF chunks must seek past ``data``, not pull it."""
    pcm = b"\x00" * 1_000_000
    id3 = b"ID3" + bytes([4, 0, 0]) + _synchsafe(0)
    fmt = struct.pack("<HHIIHH", 1, 1, 44100, 88200, 2, 16)
    chunks = (
        b"fmt "
        + struct.pack("<I", 16)
        + fmt
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
        + b"id3 "
        + struct.pack("<I", len(id3))
        + id3
    )
    wav = b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks
    stream = _CountingBytesIO(wav)
    stream.read(12)

    tag = _seek_chunk(stream, b"id3 ", "<I")

    assert tag == id3
    assert stream.bytes_read < 64


def test_read_geob_does_not_read_the_whole_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Comparing frames must not load the audio payload."""
    payload = b"\x01\x01" + b"\x00" * 8
    target = tmp_path / "t.mp3"
    target.write_bytes(_mp3([_geob_frame("Serato Markers2", payload)], padding=64))

    def boom(self: Path) -> bytes:
        """Fail if the skip path loads the song."""
        raise AssertionError("read the whole file")

    monkeypatch.setattr(Path, "read_bytes", boom)

    assert read_geob(target)["Serato Markers2"] == payload


def test_write_geob_skip_does_not_read_the_whole_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matching rewrite must not pull the audio to decide skip."""
    payload = b"\x01\x01" + b"\x00" * 8
    target = tmp_path / "t.mp3"
    target.write_bytes(_mp3([_geob_frame("Serato Markers2", payload)], padding=64))

    def boom(self: Path) -> bytes:
        """Fail if the skip path loads the song."""
        raise AssertionError("read the whole file")

    monkeypatch.setattr(Path, "read_bytes", boom)

    assert write_geob(target, {"Serato Markers2": payload}) is False


def test_commit_fsyncs_the_file_after_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live path and its directory must be fsynced after a size-changing swap."""
    called: list[Path] = []
    monkeypatch.setattr(
        "app.adapters.serato.tags.fsync_replaced",
        lambda path: called.append(path),
    )
    target = tmp_path / "t.mp3"
    original = b"x" * 100
    target.write_bytes(original)
    _commit_audio_bytes(target, b"y" * 120, original)
    assert called == [target]
    assert target.read_bytes() == b"y" * 120


def test_commit_restores_original_when_replace_zeros_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If replace leaves a 0-byte destination, the original bytes are written back."""
    target = tmp_path / "t.mp3"
    original = b"x" * 1000
    new_data = b"y" * 1200
    target.write_bytes(original)

    def zero_dest(self: Path, dest: Path) -> None:
        """Truncate the destination and drop the temporary file."""
        Path(dest).write_bytes(b"")
        Path(self).unlink(missing_ok=True)

    monkeypatch.setattr(Path, "replace", zero_dest)

    with pytest.raises(TagFormatError, match="short file"):
        _commit_audio_bytes(target, new_data, original)

    assert target.read_bytes() == original
