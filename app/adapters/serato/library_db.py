"""Updating Serato's own library index, _Serato_/Library/location.sqlite.

Serato reads track metadata from this database for its library list, while the
deck reads analysis from the file's tags. Values written into audio tags do not
reach the list until this index is updated too.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

FILENAME = "location.sqlite"


def library_db_path(serato_root: Path) -> Path:
    """
    Return the library index path for a Serato library root.

    Args:
        serato_root: Path to the _Serato_ directory.

    Returns:
        Path to location.sqlite, which may not exist.
    """
    return serato_root / "Library" / FILENAME


@dataclass(frozen=True)
class TrackAnalysis:
    """
    Analysis values for one track as the library list shows them.

    Attributes:
        bpm: Tempo, or None to leave unchanged.
        key: Musical key, or None to leave unchanged.
    """

    bpm: float | None = None
    key: str | None = None


def read_track_analysis(database_path: Path) -> dict[str, TrackAnalysis]:
    """
    Read the analysis values Serato holds for each track.

    Args:
        database_path: Path to location.sqlite.

    Returns:
        Drive-relative track path to its stored analysis.
    """
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as con:
        return {
            row[0]: TrackAnalysis(bpm=row[1], key=row[2])
            for row in con.execute("select portable_id, bpm, key from asset")
            if row[0]
        }


def update_track_analysis(
    database_path: Path,
    updates: dict[str, TrackAnalysis],
) -> int:
    """
    Write analysis values into Serato's library index.

    Each changed row takes a new revision above the current maximum, and the
    space revision follows, which is how Serato records that rows have moved on.
    Rows are also marked stale so Serato re-reads the file it came from.

    Args:
        database_path: Path to location.sqlite.
        updates: Drive-relative track path to the values to store.

    Returns:
        Number of rows updated.
    """
    if not updates:
        return 0

    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row
        revision = con.execute("select max(revision) from asset").fetchone()[0] or 0
        changed = 0
        for row in con.execute("select id, portable_id, bpm, key from asset").fetchall():
            revision, delta = _apply_analysis_row(con, row, updates, revision)
            changed += delta
        if changed:
            _bump_index_revisions(con, revision)
        con.commit()

    logger.info("serato_library_index_updated", path=str(database_path), rows=changed)
    return changed


def _apply_analysis_row(
    con: sqlite3.Connection,
    row: sqlite3.Row,
    updates: dict[str, TrackAnalysis],
    revision: int,
) -> tuple[int, int]:
    """
    Apply one index-row update when the stored values actually change.

    Args:
        con: Open writable connection.
        row: Current asset row.
        updates: Drive-relative path to the values to store.
        revision: Current maximum revision.

    Returns:
        ``(revision, changed)`` after this row — ``changed`` is 1 or 0.
    """
    wanted = updates.get(row["portable_id"])
    if wanted is None:
        return revision, 0
    bpm, key = _merged_analysis(row, wanted)
    if (bpm, key) == (row["bpm"], row["key"]):
        return revision, 0
    revision += 1
    con.execute(
        "update asset set bpm = ?, key = ?, revision = ?, is_stale = 1 where id = ?",
        (bpm, key, revision, row["id"]),
    )
    return revision, 1


def _merged_analysis(row: sqlite3.Row, wanted: TrackAnalysis) -> tuple[object, object]:
    """Return the BPM and key after applying only the fields that were set."""
    bpm = row["bpm"] if wanted.bpm is None else wanted.bpm
    key = row["key"] if wanted.key is None else wanted.key
    return bpm, key


def _bump_index_revisions(con: sqlite3.Connection, revision: int) -> None:
    """Advance the space / serato / master revisions after asset rows change."""
    con.execute("update space set revision = ?", (revision,))
    con.execute("update serato set revision = max(revision, ?)", (revision,))
    con.execute("update master set revision = max(revision, ?)", (revision,))
