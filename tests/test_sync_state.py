"""Tests for per-playlist sync state."""

import struct
from pathlib import Path
from unittest.mock import MagicMock

from app.core.domain import Playlist, SyncState
from app.services.sync_service import (
    find_crate_name_collisions,
    playlist_sync_states,
    sync_states_to_dict,
)
from tests.conftest import EMPTY_DATABASE_V2, make_library


def _tlv(tag: bytes, payload: bytes) -> bytes:
    """Encode one Serato TLV record."""
    return tag + struct.pack(">I", len(payload)) + payload


def _crate(paths: list[str]) -> bytes:
    """Build a minimal valid .crate holding the given track paths."""
    version = "1.0/Serato ScratchLive Crate".encode("utf-16-be")
    blob = _tlv(b"vrsn", version)
    for path in paths:
        blob += _tlv(b"otrk", _tlv(b"ptrk", path.encode("utf-16-be")))
    return blob


def _stick(root: Path, *, crates: dict[str, list[str]], indexed: list[str]) -> Path:
    """Create a mount with a Rekordbox export and a Serato library."""
    rb = root / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"stub")

    serato = root / "_Serato_"
    (serato / "Subcrates").mkdir(parents=True)
    db = EMPTY_DATABASE_V2
    for path in indexed:
        db += _tlv(b"otrk", _tlv(b"pfil", path.encode("utf-16-be")))
    (serato / "database V2").write_bytes(db)
    for name, paths in crates.items():
        (serato / "Subcrates" / f"{name}.crate").write_bytes(_crate(paths))
    return root


def _adapter(playlists: list[Playlist], tracks: dict[int, list[str]]) -> MagicMock:
    """Stub Rekordbox adapter returning fixed playlists and track paths."""
    adapter = MagicMock()
    adapter.list_playlists.return_value = playlists
    adapter.get_playlist_track_paths.side_effect = lambda pid: tracks[pid]
    return adapter


def test_fully_synced_playlist_is_green(tmp_path: Path) -> None:
    """Every track present in the crate reports as synced."""
    mount = _stick(
        tmp_path,
        crates={"Pocket": ["Contents/a.mp3", "Contents/b.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/Contents/a.mp3", "/Contents/b.mp3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED
    assert (state.in_crate, state.total, state.blocked) == (2, 2, 0)


def test_partially_synced_playlist_is_yellow(tmp_path: Path) -> None:
    """Some tracks in the crate reports as partial."""
    mount = _stick(
        tmp_path,
        crates={"Pocket": ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/Contents/a.mp3", "/Contents/b.mp3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.PARTIAL
    assert (state.in_crate, state.total) == (1, 2)


def test_missing_crate_is_red(tmp_path: Path) -> None:
    """A playlist with no crate reports as not synced."""
    mount = _stick(tmp_path, crates={}, indexed=["Contents/a.mp3"])
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/Contents/a.mp3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.NOT_SYNCED
    assert state.in_crate == 0


def test_blocked_counts_tracks_serato_cannot_index(tmp_path: Path) -> None:
    """Tracks absent from database V2 are reported as blocked, not merely missing."""
    mount = _stick(tmp_path, crates={}, indexed=["Contents/a.mp3"])
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    library = make_library(
        mount, _adapter([playlist], {1: ["/Contents/a.mp3", "/Contents/ghost.mp3"]})
    )

    (state,) = playlist_sync_states(library)

    assert state.syncable == 1
    assert state.blocked == 1


def test_empty_playlist_is_synced(tmp_path: Path) -> None:
    """A playlist with no tracks has nothing outstanding."""
    mount = _stick(tmp_path, crates={}, indexed=[])
    playlist = Playlist(id=1, name="Empty", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: []}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED


def test_folders_are_not_reported(tmp_path: Path) -> None:
    """Folder nodes carry no sync state of their own."""
    mount = _stick(tmp_path, crates={}, indexed=[])
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    playlist = Playlist(id=1, name="Techno", parent_id=9, is_folder=False)
    library = make_library(mount, _adapter([folder, playlist], {1: []}))

    states = playlist_sync_states(library)

    assert [s.playlist_name for s in states] == ["Techno"]


def test_path_matching_ignores_leading_slash_and_case(tmp_path: Path) -> None:
    """Rekordbox /Contents/... matches Serato Contents/... regardless of case."""
    mount = _stick(
        tmp_path, crates={"P": ["Contents/Artist/Song.mp3"]}, indexed=["Contents/Artist/Song.mp3"]
    )
    playlist = Playlist(id=1, name="P", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/contents/artist/song.MP3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED


def test_collision_detection_flags_shared_crate_names() -> None:
    """Two playlists mapping to one crate filename are reported."""
    playlists = (
        Playlist(id=1, name="Techno/Trance", parent_id=None, is_folder=False),
        Playlist(id=2, name="Techno:Trance", parent_id=None, is_folder=False),
        Playlist(id=3, name="Unique", parent_id=None, is_folder=False),
    )

    collisions = find_crate_name_collisions(playlists)

    assert list(collisions) == ["Techno_Trance"]
    assert len(collisions["Techno_Trance"]) == 2


def test_summary_counts_states(tmp_path: Path) -> None:
    """Serialization summarises how many playlists sit in each state."""
    mount = _stick(tmp_path, crates={"A": ["Contents/a.mp3"]}, indexed=["Contents/a.mp3"])
    playlists = [
        Playlist(id=1, name="A", parent_id=None, is_folder=False),
        Playlist(id=2, name="B", parent_id=None, is_folder=False),
    ]
    library = make_library(
        mount, _adapter(playlists, {1: ["/Contents/a.mp3"], 2: ["/Contents/b.mp3"]})
    )

    payload = sync_states_to_dict(playlist_sync_states(library))

    assert payload["summary"] == {"synced": 1, "not_synced": 1}
    assert payload["count"] == 2
