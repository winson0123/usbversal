"""Tests for building Serato records from Rekordbox metadata."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.track_records import (
    RekordboxLookups,
    build_track_record,
    load_lookups,
    serato_path,
)

LOOKUPS = RekordboxLookups(
    artists={1: "Alice Deejay"},
    albums={2: "Greatest Hits"},
    genres={3: "Dance"},
    keys={4: "Bm"},
)


def _content(**overrides: object) -> SimpleNamespace:
    """Build a Rekordbox content row with sensible defaults."""
    row = {
        "path": "/Contents/Artist/track.mp3",
        "title": "Track",
        "artist_id": 1,
        "album_id": 2,
        "genre_id": 3,
        "key_id": 4,
        "length": 214,
        "file_size": 8603036,
        "bitrate": 320,
        "sampling_rate": 44100,
        "bpmx100": 13698,
        "release_year": 0,
        "release_date": "",
        "date_added": datetime(2026, 1, 7, tzinfo=UTC),
    }
    row.update(overrides)
    return SimpleNamespace(**row)


def test_path_loses_its_leading_slash() -> None:
    """Serato stores drive-relative paths with no leading slash."""
    assert serato_path("/Contents/a.mp3") == "Contents/a.mp3"
    assert serato_path("Contents/a.mp3") == "Contents/a.mp3"


def test_field_formats_match_serato_conventions() -> None:
    """Numeric metadata is rendered in the string forms Serato stores."""
    fields = dict(build_track_record(_content(), LOOKUPS))

    assert fields["pfil"] == "Contents/Artist/track.mp3"
    assert fields["ttyp"] == "mp3"
    assert fields["tbpm"] == "136.98"
    assert fields["tlen"] == "03:34.00"
    assert fields["tsiz"] == "8.2MB"
    assert fields["tbit"] == "320.0kbps"
    assert fields["tsmp"] == "44.1k"


def test_lookups_resolve_ids_to_names() -> None:
    """Artist, album, genre, and key ids become names."""
    fields = dict(build_track_record(_content(), LOOKUPS))

    assert fields["tart"] == "Alice Deejay"
    assert fields["talb"] == "Greatest Hits"
    assert fields["tgen"] == "Dance"
    assert fields["tkey"] == "Bm"


def test_absent_metadata_is_omitted_not_blanked() -> None:
    """Real Serato records omit fields rather than storing empty strings."""
    fields = dict(
        build_track_record(
            _content(artist_id=None, album_id=None, genre_id=None, key_id=None), LOOKUPS
        )
    )

    for tag in ("tart", "talb", "tgen", "tkey"):
        assert tag not in fields


def test_container_types_use_serato_names() -> None:
    """WAV and MP4-family files carry Serato's own type names."""
    assert dict(build_track_record(_content(path="/a.wav"), LOOKUPS))["ttyp"] == "wave"
    assert dict(build_track_record(_content(path="/a.m4a"), LOOKUPS))["ttyp"] == "quicktime"
    assert dict(build_track_record(_content(path="/a.flac"), LOOKUPS))["ttyp"] == "flac"


def test_release_date_preferred_over_bare_year() -> None:
    """A full release date is stored when Rekordbox has one."""
    dated = dict(build_track_record(_content(release_date="2025-02-14"), LOOKUPS))
    yearly = dict(build_track_record(_content(release_year=2019), LOOKUPS))

    assert dated["ttyr"] == "2025-02-14"
    assert yearly["ttyr"] == "2019"


def test_date_added_written_as_both_string_and_integer() -> None:
    """Serato stores the added date twice, as tadd and uadd."""
    fields = dict(build_track_record(_content(), LOOKUPS))
    stamp = int(datetime(2026, 1, 7, tzinfo=UTC).timestamp())

    assert fields["tadd"] == str(stamp)
    assert fields["uadd"] == stamp


def test_analysis_flags_are_false() -> None:
    """Serato has not analysed these files, so its analysis flags stay unset."""
    fields = dict(build_track_record(_content(), LOOKUPS))

    assert fields["bbgl"] is False
    assert fields["bovc"] is False


def test_path_is_always_present_even_without_metadata() -> None:
    """A record with almost no metadata still identifies its file."""
    bare = _content(
        title=None,
        artist_id=None,
        album_id=None,
        genre_id=None,
        key_id=None,
        length=0,
        file_size=0,
        bitrate=0,
        sampling_rate=0,
        bpmx100=0,
        date_added=None,
    )
    fields = dict(build_track_record(bare, LOOKUPS))

    assert fields["pfil"] == "Contents/Artist/track.mp3"
    assert fields["ttyp"] == "mp3"


def test_load_lookups_keeps_tables_that_succeed_when_one_fails() -> None:
    """A Diesel/rbox failure on one lookup table must not empty the rest."""
    database = MagicMock()
    database.get_artists.return_value = [SimpleNamespace(id=1, name="Alice")]
    database.get_albums.side_effect = RuntimeError(
        "Diesel error: Unexpected null for non-null column"
    )
    database.get_genres.return_value = [SimpleNamespace(id=3, name="Techno")]
    database.get_keys.return_value = [SimpleNamespace(id=4, name="8A")]

    lookups = load_lookups(database)

    assert lookups.artists == {1: "Alice"}
    assert lookups.albums == {}
    assert lookups.genres == {3: "Techno"}
    assert lookups.keys == {4: "8A"}

