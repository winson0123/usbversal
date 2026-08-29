"""Tests for bootstrapping an empty Serato library on a rekordbox-only stick."""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.adapters.serato import read_database_track_paths
from app.adapters.serato.neworder import read_crate_order
from app.adapters.serato.paths import resolve_serato_library
from app.core.domain import Playlist
from app.services.bootstrap_service import bootstrap_serato_library
from app.services.sync_service import sync_playlists
from tests.conftest import make_library


def _rekordbox_only_stick(root: Path) -> Path:
    """A mount with a Rekordbox export and nothing under _Serato_ at all."""
    rb = root / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"rekordbox database contents")
    return root


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_creates_an_empty_valid_serato_library(tmp_path: Path) -> None:
    """A rekordbox-only stick gets _Serato_, Subcrates, database V2, neworder.pref."""
    mount = _rekordbox_only_stick(tmp_path)

    result = bootstrap_serato_library(mount)

    assert result.created is True
    resolved = resolve_serato_library(mount)
    assert resolved is not None
    serato_root, database_path = resolved
    assert (serato_root / "Subcrates").is_dir()
    assert read_database_track_paths(database_path) == []
    assert read_crate_order(serato_root) == []


def test_pioneer_files_are_byte_identical_after_bootstrap(tmp_path: Path) -> None:
    """Bootstrap writes only inside _Serato_ -- PIONEER/ never changes."""
    mount = _rekordbox_only_stick(tmp_path)
    db_path = mount / "PIONEER" / "rekordbox" / "exportLibrary.db"
    before = _hash(db_path)

    bootstrap_serato_library(mount)

    assert _hash(db_path) == before


def test_a_zero_byte_database_is_bootstrapped(tmp_path: Path) -> None:
    """A dirty-unmount 0-byte database V2 is replaced with a valid empty index."""
    mount = _rekordbox_only_stick(tmp_path)
    serato = mount / "_Serato_"
    serato.mkdir()
    (serato / "database V2").write_bytes(b"")

    result = bootstrap_serato_library(mount)

    assert result.created is True
    resolved = resolve_serato_library(mount)
    assert resolved is not None
    assert read_database_track_paths(resolved[1]) == []


def test_an_existing_serato_library_is_left_alone(tmp_path: Path) -> None:
    """A stick that already has _Serato_ is reported as not created, untouched."""
    mount = _rekordbox_only_stick(tmp_path)
    serato = mount / "_Serato_"
    serato.mkdir()
    existing_db = serato / "database V2"
    existing_db.write_bytes(b"vrsn\x00\x00\x00\x04real")
    before = existing_db.read_bytes()

    result = bootstrap_serato_library(mount)

    assert result.created is False
    assert existing_db.read_bytes() == before


def test_raises_when_there_are_no_rekordbox_files(tmp_path: Path) -> None:
    """A mount with no Rekordbox export is not a stick this can bootstrap."""
    tmp_path.mkdir(exist_ok=True)

    with pytest.raises(FileNotFoundError):
        bootstrap_serato_library(tmp_path)


def test_sync_playlists_works_after_bootstrap(tmp_path: Path) -> None:
    """The gap this closes: sync_playlists can now run on a rekordbox-only stick."""
    mount = _rekordbox_only_stick(tmp_path)
    bootstrap_serato_library(mount)

    adapter = MagicMock()
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    adapter.list_playlists.return_value = [playlist]
    adapter.get_playlist_track_paths.side_effect = lambda pid: ["/Contents/a.mp3"]
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.return_value = []
    adapter.database.get_genres.return_value = []
    adapter.database.get_keys.return_value = []
    content = SimpleNamespace(
        path="/Contents/a.mp3",
        title="T",
        artist_id=None,
        album_id=None,
        genre_id=None,
        key_id=None,
        length=None,
        file_size=None,
        bitrate=None,
        sampling_rate=None,
        bpmx100=None,
        release_year=None,
        release_date=None,
        date_added=None,
        analysis_data_file_path=None,
    )
    adapter.database.get_contents.return_value = [content]
    library = make_library(mount, adapter)

    report = sync_playlists(library, [1])

    assert report.crates_written == 1
    assert report.records_added == 1
