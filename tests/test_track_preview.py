"""Tests for Library-screen playlist track preview rows."""

from pathlib import Path
from types import SimpleNamespace

from app.adapters.serato.naming import volume_label_for
from app.core.domain import Playlist, SyncState
from app.services.track_preview import preview_playlist_tracks
from tests.conftest import make_library
from tests.test_sync_state import _adapter, _stick


def _content(*, path: str, title: str, genre_id: int, key_id: int, bpmx100: int) -> SimpleNamespace:
    """
    Build a Rekordbox-shaped content row for preview tests.

    Args:
        path: Rekordbox content path.
        title: Track title.
        genre_id: Genre lookup id.
        key_id: Key lookup id.
        bpmx100: Tempo times 100.

    Returns:
        Namespace with the fields ``preview_playlist_tracks`` reads.
    """
    return SimpleNamespace(
        path=path,
        title=title,
        genre_id=genre_id,
        key_id=key_id,
        bpmx100=bpmx100,
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
