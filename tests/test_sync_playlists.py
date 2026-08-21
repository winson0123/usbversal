"""Tests for syncing playlists into Serato crates."""

import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.adapters.serato import read_crate_track_paths, read_database_track_paths
from app.adapters.serato.neworder import read_crate_order, write_crate_order
from app.core.domain import Playlist
from app.services.migration_service import PlaylistNotFoundError
from app.services.sync_service import sync_playlists
from tests.conftest import EMPTY_DATABASE_V2, make_library

TRACKS = ["/Contents/a.mp3", "/Contents/b.mp3"]


def _stick(root: Path, *, indexed: list[str], order: list[str] | None = None) -> Path:
    """Create a mount with a Rekordbox export and a Serato library."""
    rb = root / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"stub")

    serato = root / "_Serato_"
    (serato / "Subcrates").mkdir(parents=True)
    blob = EMPTY_DATABASE_V2
    for path in indexed:
        inner = (
            b"pfil" + struct.pack(">I", len(path.encode("utf-16-be"))) + path.encode("utf-16-be")
        )
        blob += b"otrk" + struct.pack(">I", len(inner)) + inner
    (serato / "database V2").write_bytes(blob)
    if order is not None:
        write_crate_order(serato, order)
    return root


def _library(mount: Path, playlists: list[Playlist], tracks: dict[int, list[str]], contents=None):
    """Build a session handle over a stubbed Rekordbox adapter."""
    adapter = MagicMock()
    adapter.list_playlists.return_value = playlists
    adapter.get_playlist_track_paths.side_effect = lambda pid: tracks[pid]
    database = MagicMock()
    database.get_artists.return_value = []
    database.get_albums.return_value = []
    database.get_genres.return_value = []
    database.get_keys.return_value = []
    database.get_contents.return_value = contents or []
    adapter.database = database
    return make_library(mount, adapter)


def _content(path: str) -> SimpleNamespace:
    """Minimal Rekordbox content row."""
    return SimpleNamespace(
        path=path,
        title="T",
        artist_id=None,
        album_id=None,
        genre_id=None,
        key_id=None,
        length=10,
        file_size=1000,
        bitrate=320,
        sampling_rate=44100,
        bpmx100=12800,
        release_year=0,
        release_date="",
        date_added=None,
    )


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry run reports the plan and leaves the stick untouched."""
    mount = _stick(tmp_path, indexed=[])
    before = (mount / "_Serato_" / "database V2").read_bytes()
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS})

    report = sync_playlists(library, [1], dry_run=True)

    assert report.dry_run is True
    assert report.backup_id is None
    assert report.records_added == 2
    assert (mount / "_Serato_" / "database V2").read_bytes() == before
    assert not list((mount / "_Serato_" / "Subcrates").glob("*.crate"))


def test_sync_indexes_missing_tracks_and_writes_a_crate(tmp_path: Path) -> None:
    """Tracks Serato does not know are added, then placed in a crate."""
    mount = _stick(tmp_path, indexed=[])
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS}, [_content(t) for t in TRACKS])

    report = sync_playlists(library, [1])

    assert report.records_added == 2
    assert report.crates_written == 1
    assert report.backup_id is not None
    crate = mount / "_Serato_" / "Subcrates" / "test.crate"
    assert read_crate_track_paths(crate) == ["Contents/a.mp3", "Contents/b.mp3"]
    assert read_database_track_paths(mount / "_Serato_" / "database V2") == [
        "Contents/a.mp3",
        "Contents/b.mp3",
    ]


def test_already_indexed_tracks_are_not_duplicated(tmp_path: Path) -> None:
    """Tracks Serato already knows are not added a second time."""
    mount = _stick(tmp_path, indexed=["Contents/a.mp3"])
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS}, [_content(t) for t in TRACKS])

    report = sync_playlists(library, [1])

    assert report.records_added == 1
    assert (
        read_database_track_paths(mount / "_Serato_" / "database V2").count("Contents/a.mp3") == 1
    )


def test_shared_tracks_are_indexed_once_across_playlists(tmp_path: Path) -> None:
    """A track in two selected playlists produces one database record."""
    mount = _stick(tmp_path, indexed=[])
    playlists = [
        Playlist(id=1, name="one", parent_id=None, is_folder=False),
        Playlist(id=2, name="two", parent_id=None, is_folder=False),
    ]
    library = _library(mount, playlists, {1: TRACKS, 2: TRACKS}, [_content(t) for t in TRACKS])

    report = sync_playlists(library, [1, 2])

    assert report.records_added == 2
    assert report.crates_written == 2


def test_existing_crate_order_is_preserved(tmp_path: Path) -> None:
    """New crates append to the display order rather than replacing it."""
    mount = _stick(tmp_path, indexed=[], order=["Pocket"])
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS}, [_content(t) for t in TRACKS])

    sync_playlists(library, [1])

    assert read_crate_order(mount / "_Serato_") == ["Pocket", "test"]


def test_unknown_playlist_is_rejected(tmp_path: Path) -> None:
    """Selecting a missing playlist fails before anything is written."""
    mount = _stick(tmp_path, indexed=[])
    library = _library(mount, [], {})

    with pytest.raises(PlaylistNotFoundError):
        sync_playlists(library, [99])


def test_folder_cannot_be_synced(tmp_path: Path) -> None:
    """Folders hold no tracks and are not valid selections."""
    mount = _stick(tmp_path, indexed=[])
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    library = _library(mount, [folder], {})

    with pytest.raises(PlaylistNotFoundError):
        sync_playlists(library, [9])


def test_each_crate_holds_only_its_own_tracks(tmp_path: Path) -> None:
    """Writing several crates in one run must not leak tracks between them.

    serato-tools keeps DEFAULT_ENTRIES at class level and add_track mutates it,
    so a new crate would otherwise inherit every track added before it.
    """
    mount = _stick(tmp_path, indexed=[])
    playlists = [
        Playlist(id=1, name="one", parent_id=None, is_folder=False),
        Playlist(id=2, name="two", parent_id=None, is_folder=False),
    ]
    tracks = {1: ["/Contents/one.mp3"], 2: ["/Contents/two.mp3"]}
    contents = [_content("/Contents/one.mp3"), _content("/Contents/two.mp3")]
    library = _library(mount, playlists, tracks, contents)

    sync_playlists(library, [1, 2])

    subcrates = mount / "_Serato_" / "Subcrates"
    assert read_crate_track_paths(subcrates / "one.crate") == ["Contents/one.mp3"]
    assert read_crate_track_paths(subcrates / "two.crate") == ["Contents/two.mp3"]
