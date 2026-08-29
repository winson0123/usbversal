"""Tests for appending track records to a Serato database V2 file."""

from pathlib import Path

from serato_tools.database_v2 import DatabaseV2

from app.adapters.serato import read_database_track_paths
from app.adapters.serato.writer import append_database_tracks
from tests.conftest import EMPTY_DATABASE_V2


def _database(tmp_path: Path) -> Path:
    """Create a mount holding a minimal Serato database."""
    serato = tmp_path / "_Serato_"
    serato.mkdir(parents=True)
    database = serato / "database V2"
    database.write_bytes(EMPTY_DATABASE_V2)
    return database


def test_dump_is_required_to_persist_appended_entries() -> None:
    """Guard the private hook this writer depends on.

    DatabaseV2.save() writes raw_data, which only _dump() refreshes from
    entries. If a serato-tools upgrade removes it, appending would silently
    write nothing, so fail here instead.
    """
    assert callable(getattr(DatabaseV2, "_dump", None))


def test_append_adds_tracks(tmp_path: Path) -> None:
    """Appended records are readable by the Serato parser."""
    database = _database(tmp_path)

    added = append_database_tracks(
        database_path=database,
        records=[[("ttyp", "mp3"), ("pfil", "Contents/a.mp3"), ("tsng", "A")]],
    )

    assert added == 1
    assert read_database_track_paths(database) == ["Contents/a.mp3"]


def test_append_preserves_existing_records(tmp_path: Path) -> None:
    """Existing tracks survive an append unchanged."""
    database = _database(tmp_path)
    append_database_tracks(
        database_path=database,
        records=[[("ttyp", "mp3"), ("pfil", "Contents/first.mp3")]],
    )

    append_database_tracks(
        database_path=database,
        records=[[("ttyp", "mp3"), ("pfil", "Contents/second.mp3")]],
    )

    assert read_database_track_paths(database) == [
        "Contents/first.mp3",
        "Contents/second.mp3",
    ]


def test_append_round_trips_field_values(tmp_path: Path) -> None:
    """String, integer, and boolean fields survive the write."""
    database = _database(tmp_path)

    append_database_tracks(
        database_path=database,
        records=[
            [
                ("ttyp", "mp3"),
                ("pfil", "Contents/a.mp3"),
                ("tbpm", "128.00"),
                ("uadd", 1767801600),
                ("bovc", True),
            ]
        ],
    )

    _, fields = DatabaseV2(file=str(database)).entries[-1]
    values = dict(fields)
    assert values["tbpm"] == "128.00"
    assert values["uadd"] == 1767801600
    assert values["bovc"] is True


def test_append_is_a_no_op_for_no_records(tmp_path: Path) -> None:
    """An empty record list leaves the file untouched."""
    database = _database(tmp_path)
    original = database.read_bytes()

    assert append_database_tracks(database_path=database, records=[]) == 0
    assert database.read_bytes() == original
