"""Building Serato database records from Rekordbox track metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

TrackRecord = list[tuple[str, Any]]

# Serato's own names for container formats; other extensions are used verbatim.
_TYPE_BY_SUFFIX = {
    "wav": "wave",
    "aif": "aiff",
    "m4a": "quicktime",
    "m4v": "quicktime",
    "mov": "quicktime",
    "mp4": "quicktime",
}


@dataclass(frozen=True)
class RekordboxLookups:
    """
    Id-to-name tables from a Rekordbox library.

    Attributes:
        artists: Artist id to name.
        albums: Album id to name.
        genres: Genre id to name.
        keys: Key id to name.
    """

    artists: dict[int, str]
    albums: dict[int, str]
    genres: dict[int, str]
    keys: dict[int, str]


def load_lookups(database: Any) -> RekordboxLookups:
    """
    Load Rekordbox id-to-name tables once for reuse across tracks.

    Args:
        database: Open rbox OneLibrary handle.

    Returns:
        Populated RekordboxLookups.
    """

    def table(rows: Any) -> dict[int, str]:
        return {row.id: row.name for row in rows if getattr(row, "name", None)}

    return RekordboxLookups(
        artists=table(database.get_artists()),
        albums=table(database.get_albums()),
        genres=table(database.get_genres()),
        keys=table(database.get_keys()),
    )


def serato_path(rekordbox_path: str) -> str:
    """
    Convert a Rekordbox content path to Serato's drive-relative form.

    Args:
        rekordbox_path: Path as stored by Rekordbox (e.g. /Contents/a.mp3).

    Returns:
        Drive-relative path with no leading slash.
    """
    return rekordbox_path.replace("\\", "/").lstrip("/")


def _duration(seconds: int | None) -> str | None:
    """Format a duration as Serato's MM:SS.hh string."""
    if not seconds:
        return None
    return f"{seconds // 60:02d}:{seconds % 60:02d}.00"


def build_track_record(content: Any, lookups: RekordboxLookups) -> TrackRecord:
    """
    Build the Serato database fields for one Rekordbox track.

    Fields with no Rekordbox value are omitted rather than written empty,
    matching how real records on a Serato stick are shaped.

    Args:
        content: rbox content row for the track.
        lookups: Id-to-name tables from the same library.

    Returns:
        Ordered (tag, value) pairs for one otrk record.
    """
    path = serato_path(content.path or "")
    suffix = Path(path).suffix.lstrip(".").lower()

    fields: TrackRecord = [
        ("ttyp", _TYPE_BY_SUFFIX.get(suffix, suffix or "mp3")),
        ("pfil", path),
    ]

    year = content.release_date or (str(content.release_year) if content.release_year else None)
    optional: list[tuple[str, Any]] = [
        ("tsng", content.title),
        ("tart", lookups.artists.get(content.artist_id)),
        ("talb", lookups.albums.get(content.album_id)),
        ("tgen", lookups.genres.get(content.genre_id)),
        ("tlen", _duration(content.length)),
        ("tsiz", f"{content.file_size / 1048576:.1f}MB" if content.file_size else None),
        ("tbit", f"{content.bitrate}.0kbps" if content.bitrate else None),
        ("tsmp", f"{content.sampling_rate / 1000:.1f}k" if content.sampling_rate else None),
        ("tbpm", f"{content.bpmx100 / 100:.2f}" if content.bpmx100 else None),
        ("tkey", lookups.keys.get(content.key_id)),
        ("ttyr", year),
    ]
    fields.extend((tag, value) for tag, value in optional if value)

    if content.file_size:
        fields.append(("ufsb", int(content.file_size)))
    if content.date_added is not None:
        stamp = int(content.date_added.timestamp())
        fields.append(("tadd", str(stamp)))
        fields.append(("uadd", stamp))

    # Serato has not analysed these files, so neither flag is set.
    fields.append(("bbgl", False))
    fields.append(("bovc", False))
    return fields
