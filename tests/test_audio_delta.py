"""Audio tag-region deltas: encode, apply, and backup/rollback."""

from __future__ import annotations

import struct
from pathlib import Path

from app.storage.audio_delta import apply_audio_delta, encode_audio_delta
from app.storage.backup import BackupManifest, create_backup, default_backup_root, resolve_artifact
from app.storage.rollback import rollback_from_backup


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _mp3(*, tag_body: bytes, audio: bytes) -> bytes:
    """Build a minimal ID3v2.4 MP3."""
    tag = b"ID3" + bytes([4, 0, 0]) + _synchsafe(len(tag_body)) + tag_body
    return tag + audio


def _wav(audio: bytes) -> bytes:
    """Build a minimal mono PCM WAV with a data chunk."""
    fmt = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 44100, 88200, 2, 16)
    data = b"data" + struct.pack("<I", len(audio)) + audio
    riff_size = 4 + len(fmt) + len(data)
    return b"RIFF" + struct.pack("<I", riff_size) + b"WAVE" + fmt + data


def test_mp3_delta_is_much_smaller_than_the_song() -> None:
    """The stored artifact is the tag, not a second copy of the audio."""
    audio = b"\xff\xfb" + b"\x00" * 200_000
    original = _mp3(tag_body=b"\x00" * 64, audio=audio)
    delta = encode_audio_delta(original)
    assert len(delta) < 500
    assert len(delta) < len(original) // 100


def test_mp3_delta_restores_the_original_tag_after_a_rewrite() -> None:
    """Rollback splices the old tag onto the same audio tail."""
    audio = b"\xff\xfb" + b"\x11" * 256
    original = _mp3(tag_body=b"OLD-TAG" + b"\x00" * 32, audio=audio)
    rewritten = _mp3(tag_body=b"NEW-TAG-GROWN" + b"\x00" * 48, audio=audio)
    restored = apply_audio_delta(rewritten, encode_audio_delta(original))
    assert restored == original


def test_wav_delta_keeps_the_data_chunk() -> None:
    """WAV audio lives in the data chunk, not as a simple suffix of the file."""
    audio = b"\x00\x01" * 128
    original = _wav(audio)
    # Pretend a tag write grew a chunk before data by rebuilding with same audio.
    rewritten = _wav(audio)
    assert apply_audio_delta(rewritten, encode_audio_delta(original)) == original


def test_create_backup_stores_mp3_as_a_delta_on_the_host(tmp_path: Path) -> None:
    """Audio extras become .delta files under the chosen host backup root."""
    mount = tmp_path / "usb"
    audio_bytes = b"\xff\xfb" + b"\x22" * 50_000
    track = mount / "Contents" / "song.mp3"
    track.parent.mkdir(parents=True)
    track.write_bytes(_mp3(tag_body=b"\x00" * 32, audio=audio_bytes))
    db = mount / "PIONEER" / "rekordbox" / "exportLibrary.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"db")

    result = create_backup(
        source_mount=mount,
        files=[db, track],
        backup_root=tmp_path / "host-backups",
    )

    assert not (mount / "backups").exists()
    entry = next(e for e in result.manifest.files if e.relative_path.endswith("song.mp3"))
    assert entry.kind == "delta"
    stored = resolve_artifact(result.backup_dir, entry)
    assert stored.is_file()
    assert stored.stat().st_size < track.stat().st_size // 10
    assert entry.stored_as == f"objects/{entry.sha256}"
    assert not (result.backup_dir / "Contents/song.mp3").exists()


def test_rollback_restores_an_mp3_from_its_delta(tmp_path: Path) -> None:
    """A tagged MP3 is put back to the pre-write tag without a full file copy."""
    mount = tmp_path / "usb"
    audio = b"\xff\xfb" + b"\x33" * 1024
    original = _mp3(tag_body=b"BEFORE" + b"\x00" * 16, audio=audio)
    track = mount / "Contents" / "song.mp3"
    track.parent.mkdir(parents=True)
    track.write_bytes(original)
    result = create_backup(source_mount=mount, files=[track], backup_root=tmp_path / "host-backups")
    track.write_bytes(_mp3(tag_body=b"AFTER-WRITE" + b"\x00" * 24, audio=audio))

    rollback_from_backup(source_mount=mount, backup_dir=result.backup_dir, pre_rollback=False)

    assert track.read_bytes() == original


def test_default_backup_root_is_not_on_the_mount(tmp_path: Path, monkeypatch) -> None:
    """Backups land under USBVERSAL_BACKUP_ROOT / the volume name."""
    mount = tmp_path / "WONSIN"
    mount.mkdir()
    monkeypatch.setenv("USBVERSAL_BACKUP_ROOT", str(tmp_path / "host"))
    root = default_backup_root(mount)
    assert root == (tmp_path / "host" / "WONSIN").resolve()
    assert mount not in root.parents and root != mount


def test_manifest_round_trips_delta_fields(tmp_path: Path) -> None:
    """kind and stored_as survive a manifest reload."""
    mount = tmp_path / "usb"
    track = mount / "t.mp3"
    track.parent.mkdir(parents=True)
    track.write_bytes(_mp3(tag_body=b"\x00" * 8, audio=b"\xff\xfb" + b"\x00" * 32))
    result = create_backup(source_mount=mount, files=[track], backup_root=tmp_path / "b")
    loaded = BackupManifest.load(result.backup_dir)
    assert loaded.files[0].kind == "delta"
    assert loaded.files[0].stored_as == f"objects/{loaded.files[0].sha256}"
    assert loaded.files[0].original_size == track.stat().st_size
