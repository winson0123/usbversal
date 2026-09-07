"""Tests for Library-screen playlist track preview rows."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.serato.naming import volume_label_for
from app.core.domain import Playlist, SyncState
from app.services.track_preview import preview_playlist_tracks
from tests.conftest import make_library
from tests.test_sync_state import _DAT_REL, _adapter, _stick, _write_audio, _write_dat


def _content(
    *,
    path: str,
    title: str,
    genre_id: int,
    key_id: int,
    bpmx100: int,
    analysis_data_file_path: str | None = None,
) -> SimpleNamespace:
    """
    Build a Rekordbox-shaped content row for preview tests.

    Args:
        path: Rekordbox content path.
        title: Track title.
        genre_id: Genre lookup id.
        key_id: Key lookup id.
        bpmx100: Tempo times 100.
        analysis_data_file_path: Rekordbox ANLZ path, or None when unanalysed.

    Returns:
        Namespace with the fields ``preview_playlist_tracks`` reads.
    """
    return SimpleNamespace(
        path=path,
        title=title,
        genre_id=genre_id,
        key_id=key_id,
        bpmx100=bpmx100,
        analysis_data_file_path=analysis_data_file_path,
    )


def test_preview_marks_crate_membership_and_fills_metadata(tmp_path: Path) -> None:
    """In-crate tracks are green; missing tracks are red. Metadata comes from Rekordbox."""
    mount = _stick(
        tmp_path,
        crates={f"{volume_label_for(tmp_path)}%%Techno": ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    playlist = Playlist(id=1, name="Techno", parent_id=None, is_folder=False)
    adapter = _adapter([playlist], {1: ["/Contents/a.mp3", "/Contents/b.mp3"]})
    adapter.database.get_contents.return_value = [
        _content(path="/Contents/a.mp3", title="Alpha", genre_id=1, key_id=2, bpmx100=12800),
        _content(path="/Contents/b.mp3", title="Beta", genre_id=1, key_id=2, bpmx100=14000),
    ]
    adapter.database.get_genres.return_value = [SimpleNamespace(id=1, name="Techno")]
    adapter.database.get_keys.return_value = [SimpleNamespace(id=2, name="8A")]
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.return_value = []
    library = make_library(mount, adapter)

    rows = preview_playlist_tracks(library, 1)

    assert [(row.title, row.genre, row.key, row.bpm, row.state) for row in rows] == [
        ("Alpha", "Techno", "8A", "128.00", SyncState.SYNCED),
        ("Beta", "Techno", "8A", "140.00", SyncState.NOT_SYNCED),
    ]


def test_preview_of_a_folder_is_empty(tmp_path: Path) -> None:
    """Folders have no track list of their own."""
    mount = _stick(tmp_path, crates={}, indexed=[])
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    adapter = _adapter([folder], {})
    adapter.database.get_contents.return_value = []
    adapter.database.get_genres.return_value = []
    adapter.database.get_keys.return_value = []
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.return_value = []
    library = make_library(mount, adapter)

    assert preview_playlist_tracks(library, 9) == []


def test_preview_survives_broken_album_lookups(tmp_path: Path) -> None:
    """Album table Diesel nulls must not abort the track preview pane."""
    mount = _stick(
        tmp_path,
        crates={f"{volume_label_for(tmp_path)}%%Techno": ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3"],
    )
    playlist = Playlist(id=1, name="Techno", parent_id=None, is_folder=False)
    adapter = _adapter([playlist], {1: ["/Contents/a.mp3"]})
    adapter.database.get_contents.return_value = [
        _content(path="/Contents/a.mp3", title="Alpha", genre_id=1, key_id=2, bpmx100=12800),
    ]
    adapter.database.get_genres.return_value = [SimpleNamespace(id=1, name="Techno")]
    adapter.database.get_keys.return_value = [SimpleNamespace(id=2, name="8A")]
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.side_effect = RuntimeError(
        "Diesel error: Unexpected null for non-null column"
    )
    library = make_library(mount, adapter)

    rows = preview_playlist_tracks(library, 1)

    assert [(row.title, row.genre, row.key, row.bpm, row.state) for row in rows] == [
        ("Alpha", "Techno", "8A", "128.00", SyncState.SYNCED),
    ]


def test_preview_survives_broken_contents_and_membership(tmp_path: Path) -> None:
    """Content-table Diesel nulls leave filename rows; membership failure is empty."""
    mount = _stick(
        tmp_path,
        crates={f"{volume_label_for(tmp_path)}%%Techno": ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3"],
    )
    playlist = Playlist(id=1, name="Techno", parent_id=None, is_folder=False)
    adapter = _adapter([playlist], {1: ["/Contents/a.mp3"]})
    adapter.database.get_contents.side_effect = RuntimeError(
        "Diesel error: Unexpected null for non-null column"
    )
    adapter.database.get_genres.return_value = []
    adapter.database.get_keys.return_value = []
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.return_value = []
    library = make_library(mount, adapter)

    rows = preview_playlist_tracks(library, 1)

    assert [(row.title, row.genre, row.key, row.state) for row in rows] == [
        ("a.mp3", "", "", SyncState.SYNCED),
    ]

    adapter.get_playlist_track_paths.side_effect = RuntimeError(
        "Diesel error: Unexpected null for non-null column"
    )
    assert preview_playlist_tracks(library, 1) == []


def test_preview_marks_missing_analysis_yellow(tmp_path: Path) -> None:
    """In-crate with ANLZ beats but no BeatGrid is yellow; no ANLZ stays green."""
    mount = _stick(
        tmp_path,
        crates={f"{volume_label_for(tmp_path)}%%Techno": ["Contents/a.mp3", "Contents/c.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3", "Contents/c.mp3"],
    )
    _write_dat(mount, _DAT_REL, [(1, 128.0, 0)])
    _write_audio(mount, "Contents/a.mp3", beatgrid=False)
    playlist = Playlist(id=1, name="Techno", parent_id=None, is_folder=False)
    adapter = _adapter(
        [playlist],
        {1: ["/Contents/a.mp3", "/Contents/b.mp3", "/Contents/c.mp3"]},
    )
    adapter.database.get_contents.return_value = [
        _content(
            path="/Contents/a.mp3",
            title="Alpha",
            genre_id=1,
            key_id=2,
            bpmx100=12800,
            analysis_data_file_path=f"/{_DAT_REL}",
        ),
        _content(path="/Contents/b.mp3", title="Beta", genre_id=1, key_id=2, bpmx100=14000),
        _content(path="/Contents/c.mp3", title="Gamma", genre_id=1, key_id=2, bpmx100=12000),
    ]
    adapter.database.get_genres.return_value = [SimpleNamespace(id=1, name="Techno")]
    adapter.database.get_keys.return_value = [SimpleNamespace(id=2, name="8A")]
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.return_value = []
    library = make_library(mount, adapter)

    rows = preview_playlist_tracks(library, 1)

    assert [row.state for row in rows] == [
        SyncState.PARTIAL,
        SyncState.NOT_SYNCED,
        SyncState.SYNCED,
    ]
    assert [row.title for row in rows] == ["Alpha", "Beta", "Gamma"]


def test_preview_stops_when_should_cancel_flips(tmp_path: Path) -> None:
    """A stale highlight must abort mid-preview instead of finishing every track."""
    from app.services.cancellation import OperationCancelled, clear_quit_request

    clear_quit_request()
    mount = _stick(tmp_path, crates={}, indexed=[])
    playlist = Playlist(id=1, name="Techno", parent_id=None, is_folder=False)
    paths = [f"/Contents/t{i}.mp3" for i in range(20)]
    adapter = _adapter([playlist], {1: paths})
    adapter.database.get_contents.return_value = [
        _content(path=p, title=p, genre_id=1, key_id=2, bpmx100=12000) for p in paths
    ]
    adapter.database.get_genres.return_value = [SimpleNamespace(id=1, name="Techno")]
    adapter.database.get_keys.return_value = [SimpleNamespace(id=2, name="8A")]
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.return_value = []
    library = make_library(mount, adapter)
    cancel_after = {"n": 0}

    def should_cancel() -> bool:
        """Flip true after the first track row is built."""
        cancel_after["n"] += 1
        return cancel_after["n"] > 3

    with pytest.raises(OperationCancelled):
        preview_playlist_tracks(library, 1, should_cancel=should_cancel)
