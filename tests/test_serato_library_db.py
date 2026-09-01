"""Tests for updating Serato's library index."""

import sqlite3
from pathlib import Path

import pytest

from app.adapters.serato.library_db import (
    TrackAnalysis,
    library_db_path,
    read_track_analysis,
    update_track_analysis,
)

SCHEMA = """
create table asset (
    id integer primary key autoincrement,
    revision integer not null,
    portable_id text,
    file_name text,
    key text not null default '',
    bpm real,
    is_stale integer not null default 0,
    analysis_flags integer not null default 0
);
create table space (id integer, name text, revision integer);
create table serato (database_name text, revision integer);
create table master (uuid blob, revision integer);
"""


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """A stand-in Serato library index with two tracks."""
    path = tmp_path / "location.sqlite"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany(
        "insert into asset (revision, portable_id, file_name, key, bpm) values (?,?,?,?,?)",
        [
            (10, "Contents/a.mp3", "a.mp3", "Cm", 71.5),
            (11, "Contents/b.mp3", "b.mp3", "Am", 128.0),
        ],
    )
    con.execute("insert into space values (1, 'Serato Library', 11)")
    con.execute("insert into serato values ('', 20)")
    con.execute("insert into master values (x'00', 20)")
    con.commit()
    con.close()
    return path


def test_library_path_is_under_the_library_folder(tmp_path: Path) -> None:
    """The index lives at _Serato_/Library/location.sqlite."""
    assert library_db_path(tmp_path).parts[-2:] == ("Library", "location.sqlite")


def test_reads_stored_analysis(database: Path) -> None:
    """Existing rows are read back by track path."""
    stored = read_track_analysis(database)

    assert stored["Contents/a.mp3"] == TrackAnalysis(bpm=71.5, key="Cm")
    assert stored["Contents/b.mp3"].bpm == 128.0


def test_updates_bpm_and_key(database: Path) -> None:
    """Written values replace what Serato had cached."""
    changed = update_track_analysis(
        database, {"Contents/a.mp3": TrackAnalysis(bpm=143.0, key="8A")}
    )

    stored = read_track_analysis(database)
    assert changed == 1
    assert stored["Contents/a.mp3"] == TrackAnalysis(bpm=143.0, key="8A")
    assert stored["Contents/b.mp3"].bpm == 128.0


def test_omitted_fields_are_left_alone(database: Path) -> None:
    """A None field keeps whatever Serato already stored."""
    update_track_analysis(database, {"Contents/a.mp3": TrackAnalysis(bpm=143.0)})

    assert read_track_analysis(database)["Contents/a.mp3"].key == "Cm"


def test_unchanged_values_are_not_rewritten(database: Path) -> None:
    """Writing the values already present, on an analysed row, updates nothing."""
    con = sqlite3.connect(database)
    con.execute("update asset set analysis_flags = 24 where portable_id = 'Contents/a.mp3'")
    con.commit()
    con.close()
    assert (
        update_track_analysis(database, {"Contents/a.mp3": TrackAnalysis(bpm=71.5, key="Cm")}) == 0
    )


def test_marks_existing_row_analyzed(database: Path) -> None:
    """Same BPM and key still writes analysis_flags when the row is unanalyzed."""
    changed = update_track_analysis(database, {"Contents/a.mp3": TrackAnalysis(bpm=71.5, key="Cm")})

    con = sqlite3.connect(database)
    flags = con.execute(
        "select analysis_flags from asset where portable_id = 'Contents/a.mp3'"
    ).fetchone()[0]
    con.close()
    assert changed == 1
    assert flags == 24


def test_unknown_tracks_are_ignored(database: Path) -> None:
    """A path Serato does not know is skipped rather than inserted."""
    assert update_track_analysis(database, {"Contents/ghost.mp3": TrackAnalysis(bpm=100.0)}) == 0
    assert len(read_track_analysis(database)) == 2


def test_changed_rows_take_new_revisions_and_go_stale(database: Path) -> None:
    """Serato tracks change by revision, and stale rows get re-read."""
    update_track_analysis(database, {"Contents/a.mp3": TrackAnalysis(bpm=143.0)})

    con = sqlite3.connect(database)
    revision, stale = con.execute(
        "select revision, is_stale from asset where portable_id = 'Contents/a.mp3'"
    ).fetchone()

    assert revision > 11
    assert stale == 1
    assert con.execute("select revision from space").fetchone()[0] == revision


def test_no_updates_leaves_the_file_untouched(database: Path) -> None:
    """An empty update set does not open the database for writing."""
    before = database.read_bytes()

    assert update_track_analysis(database, {}) == 0
    assert database.read_bytes() == before
