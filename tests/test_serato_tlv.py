"""Tests for Serato TLV encoding and database append."""

import struct
from pathlib import Path

import pytest

from app.adapters.base import WriteContext
from app.adapters.serato import read_database_track_paths
from app.adapters.serato.tlv import SeratoEncodingError, encode_field, encode_fields
from app.adapters.serato.writer import append_database_tracks
from tests.conftest import EMPTY_DATABASE_V2


def test_string_field_is_utf16_be() -> None:
    """String-typed tags encode as UTF-16BE with a big-endian length."""
    blob = encode_field("tsng", "Hi")

    assert blob[:4] == b"tsng"
    assert struct.unpack(">I", blob[4:8])[0] == 4
    assert blob[8:] == "Hi".encode("utf-16-be")


def test_numeric_and_boolean_widths() -> None:
    """u32, u16, and u8 tags encode at their documented widths."""
    assert encode_field("uadd", 1)[8:] == struct.pack(">I", 1)
    assert encode_field("sbav", 1)[8:] == struct.pack(">H", 1)
    assert encode_field("bovc", True)[8:] == b"\x01"
    assert encode_field("bovc", False)[8:] == b"\x00"


def test_container_nests_its_fields() -> None:
    """Container tags wrap an encoded field stream."""
    inner = encode_fields([("ptrk", "Contents/a.mp3")])
    blob = encode_field("otrk", [("ptrk", "Contents/a.mp3")])

    assert blob[:4] == b"otrk"
    assert blob[8:] == inner


def test_rejects_malformed_tag_and_type() -> None:
    """Bad tags and mismatched values fail loudly rather than writing garbage."""
    with pytest.raises(SeratoEncodingError):
        encode_field("bad", "x")
    with pytest.raises(SeratoEncodingError):
        encode_field("tsng", 5)
    with pytest.raises(SeratoEncodingError):
        encode_field("zzzz", "x")


def _database(tmp_path: Path) -> Path:
    """Create a mount with a minimal Serato database and a verified backup."""
    serato = tmp_path / "_Serato_"
    serato.mkdir(parents=True)
    database = serato / "database V2"
    database.write_bytes(EMPTY_DATABASE_V2)
    return database


def _context(tmp_path: Path, database: Path) -> WriteContext:
    """Build a WriteContext backed by a real verified backup."""
    from app.storage.backup import create_backup

    result = create_backup(
        source_mount=tmp_path, files=[database], backup_root=tmp_path / "backups"
    )
    return WriteContext(backup_path=result.backup_dir)


def test_append_adds_tracks_and_preserves_existing_bytes(tmp_path: Path) -> None:
    """Appending never re-encodes what is already in the file."""
    database = _database(tmp_path)
    original = database.read_bytes()
    context = _context(tmp_path, database)

    added = append_database_tracks(
        database_path=database,
        records=[[("ttyp", "mp3"), ("pfil", "Contents/a.mp3"), ("tsng", "A")]],
        write_context=context,
    )

    assert added == 1
    assert database.read_bytes()[: len(original)] == original
    assert read_database_track_paths(database) == ["Contents/a.mp3"]


def test_append_is_a_no_op_for_no_records(tmp_path: Path) -> None:
    """An empty record list leaves the file untouched."""
    database = _database(tmp_path)
    original = database.read_bytes()
    context = _context(tmp_path, database)

    assert append_database_tracks(database_path=database, records=[], write_context=context) == 0
    assert database.read_bytes() == original


def test_appended_records_survive_a_reread(tmp_path: Path) -> None:
    """Records written here are readable by the Serato parser."""
    database = _database(tmp_path)
    context = _context(tmp_path, database)

    append_database_tracks(
        database_path=database,
        records=[
            [("ttyp", "mp3"), ("pfil", "Contents/one.mp3"), ("tbpm", "128.00")],
            [("ttyp", "mp3"), ("pfil", "Contents/two.mp3"), ("tbpm", "140.00")],
        ],
        write_context=context,
    )

    assert read_database_track_paths(database) == ["Contents/one.mp3", "Contents/two.mp3"]
