"""Tests for per-playlist sync state."""

import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.adapters.serato.naming import volume_label_for
from app.core.domain import Playlist, SyncState
from app.services.sync_service import (
    find_crate_name_collisions,
    playlist_sync_states,
    playlist_tree_sync_states,
    sync_states_to_dict,
)
from tests.conftest import EMPTY_DATABASE_V2, make_library

_DAT_REL = "USBANLZ/ANLZ0000.DAT"
_GEOB_MIME = b"application/octet-stream"


def _stem(mount: Path, name: str) -> str:
    """Crate filename stem including the volume parent."""
    return f"{volume_label_for(mount)}%%{name}"


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


def _section(tag: bytes, header_extra: bytes, body: bytes) -> bytes:
    """Build one ANLZ section with its header and total lengths."""
    header_len = 12 + len(header_extra)
    total_len = header_len + len(body)
    return tag + struct.pack(">II", header_len, total_len) + header_extra + body


def _anlz(sections: bytes) -> bytes:
    """Wrap sections in a PMAI container."""
    return b"PMAI" + struct.pack(">II", 28, 28 + len(sections)) + b"\x00" * 16 + sections


def _pqtz(beats: list[tuple[int, float, int]]) -> bytes:
    """Build a PQTZ beat grid section."""
    body = b"".join(struct.pack(">HHI", n, int(bpm * 100), t) for n, bpm, t in beats)
    return _section(b"PQTZ", b"\x00" * 12, body)


def _synchsafe(value: int) -> bytes:
    """Encode an integer as a 28-bit synchsafe big-endian value."""
    return bytes(((value >> shift) & 0x7F) for shift in (21, 14, 7, 0))


def _geob_frame(description: str, payload: bytes) -> bytes:
    """Build one raw ID3v2.4 GEOB frame."""
    body = b"\x00" + _GEOB_MIME + b"\x00\x00" + description.encode("latin1") + b"\x00" + payload
    return b"GEOB" + _synchsafe(len(body)) + b"\x00\x00" + body


def _mp3(frames: list[bytes]) -> bytes:
    """Build a minimal ID3v2.4 MP3 carrying the given GEOB frames."""
    body = b"".join(frames)
    return b"ID3" + bytes([4, 0, 0]) + _synchsafe(len(body)) + body + b"\xff\xfb" + b"\x00" * 64


def _content(path: str, dat_rel: str | None = None) -> SimpleNamespace:
    """
    Build a Rekordbox-shaped content row for sync-state tests.

    Args:
        path: Rekordbox content path.
        dat_rel: Drive-relative ANLZ ``.DAT`` path, or None when unanalysed.

    Returns:
        Namespace with ``path`` and optional ``analysis_data_file_path``.
    """
    return SimpleNamespace(
        path=path,
        analysis_data_file_path=f"/{dat_rel}" if dat_rel else None,
    )


def _write_dat(mount: Path, rel: str, beats: list[tuple[int, float, int]]) -> None:
    """
    Write an ANLZ ``.DAT`` under the mount.

    Args:
        mount: Mount root.
        rel: Drive-relative path for the ``.DAT``.
        beats: ``(number, bpm, time_ms)`` rows; empty writes a tag with no grid.
    """
    path = mount / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_anlz(_pqtz(beats) if beats else b""))


def _write_audio(mount: Path, rel: str, *, beatgrid: bool) -> None:
    """
    Write a dummy MP3 under the mount.

    Args:
        mount: Mount root.
        rel: Drive-relative audio path.
        beatgrid: When True, the file already carries ``Serato BeatGrid``.
    """
    path = mount / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [_geob_frame("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00\x00")] if beatgrid else []
    path.write_bytes(_mp3(frames))


def test_fully_synced_playlist_is_green(tmp_path: Path) -> None:
    """Every track present in the crate reports as synced."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Pocket"): ["Contents/a.mp3", "Contents/b.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/Contents/a.mp3", "/Contents/b.mp3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED
    assert (state.in_crate, state.complete, state.total, state.blocked) == (2, 2, 2, 0)


def test_partially_synced_playlist_is_yellow(tmp_path: Path) -> None:
    """Some tracks in the crate reports as partial."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Pocket"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/Contents/a.mp3", "/Contents/b.mp3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.PARTIAL
    assert (state.in_crate, state.complete, state.total) == (1, 1, 2)


def test_missing_crate_is_red(tmp_path: Path) -> None:
    """A playlist with no crate reports as not synced."""
    mount = _stick(tmp_path, crates={}, indexed=["Contents/a.mp3"])
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/Contents/a.mp3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.NOT_SYNCED
    assert state.in_crate == 0


def test_zero_byte_crate_does_not_crash_sync_state(tmp_path: Path) -> None:
    """A dirty-unmount 0-byte crate is treated as missing, not a crash."""
    mount = _stick(tmp_path, crates={}, indexed=["Contents/a.mp3"])
    leftover = mount / "_Serato_" / "Subcrates" / f"{_stem(tmp_path, 'Pocket')}.crate"
    leftover.write_bytes(b"")
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
        tmp_path,
        crates={_stem(tmp_path, "P"): ["Contents/Artist/Song.mp3"]},
        indexed=["Contents/Artist/Song.mp3"],
    )
    playlist = Playlist(id=1, name="P", parent_id=None, is_folder=False)
    library = make_library(mount, _adapter([playlist], {1: ["/contents/artist/song.MP3"]}))

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED


def test_collision_detection_flags_shared_crate_names() -> None:
    """Two playlists mapping to one crate filename are reported."""
    playlists = (
        Playlist(id=1, name="Techno:Trance", parent_id=None, is_folder=False),
        Playlist(id=2, name="Techno?Trance", parent_id=None, is_folder=False),
        Playlist(id=3, name="Unique", parent_id=None, is_folder=False),
    )

    collisions = find_crate_name_collisions(playlists)

    assert list(collisions) == ["Techno_Trance"]
    assert len(collisions["Techno_Trance"]) == 2


def test_tree_folder_is_green_only_when_every_child_is_synced(tmp_path: Path) -> None:
    """A folder rolls up to synced only if all of its children are."""
    mount = _stick(
        tmp_path,
        crates={
            _stem(tmp_path, "Genres%%Techno"): ["Contents/a.mp3"],
            _stem(tmp_path, "Genres%%Trance"): ["Contents/b.mp3"],
        },
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    techno = Playlist(id=1, name="Techno", parent_id=9, is_folder=False)
    trance = Playlist(id=2, name="Trance", parent_id=9, is_folder=False)
    library = make_library(
        mount,
        _adapter([folder, techno, trance], {1: ["/Contents/a.mp3"], 2: ["/Contents/b.mp3"]}),
    )

    (root,) = playlist_tree_sync_states(library)

    assert root.state is SyncState.SYNCED
    assert [child.state for child in root.children] == [SyncState.SYNCED, SyncState.SYNCED]


def test_tree_folder_is_yellow_when_children_disagree(tmp_path: Path) -> None:
    """One synced child and one unsynced child rolls the folder up to partial."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Genres%%Techno"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    techno = Playlist(id=1, name="Techno", parent_id=9, is_folder=False)
    trance = Playlist(id=2, name="Trance", parent_id=9, is_folder=False)
    library = make_library(
        mount,
        _adapter([folder, techno, trance], {1: ["/Contents/a.mp3"], 2: ["/Contents/b.mp3"]}),
    )

    (root,) = playlist_tree_sync_states(library)

    assert root.state is SyncState.PARTIAL


def test_tree_empty_folder_is_red_not_green(tmp_path: Path) -> None:
    """A folder with nothing in it has nothing outstanding but is not 'synced'."""
    mount = _stick(tmp_path, crates={}, indexed=[])
    folder = Playlist(id=9, name="Empty", parent_id=None, is_folder=True)
    library = make_library(mount, _adapter([folder], {}))

    (root,) = playlist_tree_sync_states(library)

    assert root.state is SyncState.NOT_SYNCED


def test_in_crate_without_anlz_is_green(tmp_path: Path) -> None:
    """A crate member with no Rekordbox analysis has nothing to port."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Pocket"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3"],
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    adapter = _adapter([playlist], {1: ["/Contents/a.mp3"]})
    adapter.database.get_contents.return_value = [_content("/Contents/a.mp3")]
    library = make_library(mount, adapter)

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED
    assert (state.complete, state.in_crate, state.total) == (1, 1, 1)


def test_in_crate_with_beats_and_no_beatgrid_is_yellow(tmp_path: Path) -> None:
    """A crate member whose ANLZ beats are not on the file is partial."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Pocket"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3"],
    )
    _write_dat(mount, _DAT_REL, [(1, 128.0, 0)])
    _write_audio(mount, "Contents/a.mp3", beatgrid=False)
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    adapter = _adapter([playlist], {1: ["/Contents/a.mp3"]})
    adapter.database.get_contents.return_value = [_content("/Contents/a.mp3", _DAT_REL)]
    library = make_library(mount, adapter)

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.PARTIAL
    assert (state.complete, state.in_crate, state.total) == (0, 1, 1)


def test_in_crate_with_beats_and_beatgrid_is_green(tmp_path: Path) -> None:
    """A crate member whose ANLZ beats are already on the file is synced."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Pocket"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3"],
    )
    _write_dat(mount, _DAT_REL, [(1, 128.0, 0)])
    _write_audio(mount, "Contents/a.mp3", beatgrid=True)
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    adapter = _adapter([playlist], {1: ["/Contents/a.mp3"]})
    adapter.database.get_contents.return_value = [_content("/Contents/a.mp3", _DAT_REL)]
    library = make_library(mount, adapter)

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED
    assert (state.complete, state.total) == (1, 1)


def test_empty_anlz_is_green(tmp_path: Path) -> None:
    """A DAT with neither beats nor cues has nothing to port."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Pocket"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3"],
    )
    _write_dat(mount, _DAT_REL, [])
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    adapter = _adapter([playlist], {1: ["/Contents/a.mp3"]})
    adapter.database.get_contents.return_value = [_content("/Contents/a.mp3", _DAT_REL)]
    library = make_library(mount, adapter)

    (state,) = playlist_sync_states(library)

    assert state.state is SyncState.SYNCED
    assert state.complete == 1


def test_tree_folder_counts_only_green_tracks(tmp_path: Path) -> None:
    """A folder's x/y numerator is green descendants only."""
    mount = _stick(
        tmp_path,
        crates={
            _stem(tmp_path, "Genres%%Techno"): ["Contents/a.mp3"],
            _stem(tmp_path, "Genres%%Trance"): ["Contents/b.mp3"],
        },
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    _write_dat(mount, _DAT_REL, [(1, 128.0, 0)])
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    techno = Playlist(id=1, name="Techno", parent_id=9, is_folder=False)
    trance = Playlist(id=2, name="Trance", parent_id=9, is_folder=False)
    adapter = _adapter(
        [folder, techno, trance],
        {1: ["/Contents/a.mp3"], 2: ["/Contents/b.mp3"]},
    )
    adapter.database.get_contents.return_value = [
        _content("/Contents/a.mp3"),
        _content("/Contents/b.mp3", _DAT_REL),
    ]
    library = make_library(mount, adapter)

    (root,) = playlist_tree_sync_states(library)

    assert root.state is SyncState.PARTIAL
    assert (root.synced, root.total) == (1, 2)
    assert [child.state for child in root.children] == [SyncState.SYNCED, SyncState.PARTIAL]


def test_tree_leaf_carries_its_own_synced_and_total_counts(tmp_path: Path) -> None:
    """A leaf's synced/total match its green count, not just crate membership."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Pocket"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3", "Contents/c.mp3"],
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)
    tracks = {1: ["/Contents/a.mp3", "/Contents/b.mp3", "/Contents/c.mp3"]}
    library = make_library(mount, _adapter([playlist], tracks))

    (leaf,) = playlist_tree_sync_states(library)

    assert (leaf.synced, leaf.total) == (1, 3)


def test_tree_folder_counts_sum_its_children(tmp_path: Path) -> None:
    """A folder's synced/total are the sum across its descendants."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Genres%%Techno"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3", "Contents/c.mp3"],
    )
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    techno = Playlist(id=1, name="Techno", parent_id=9, is_folder=False)
    trance = Playlist(id=2, name="Trance", parent_id=9, is_folder=False)
    library = make_library(
        mount,
        _adapter(
            [folder, techno, trance],
            {1: ["/Contents/a.mp3"], 2: ["/Contents/b.mp3", "/Contents/c.mp3"]},
        ),
    )

    (root,) = playlist_tree_sync_states(library)

    # Techno: 1/1 synced. Trance: 0/2 synced. Folder sums both.
    assert (root.synced, root.total) == (1, 3)


def test_tree_rollup_composes_through_nested_folders(tmp_path: Path) -> None:
    """A folder of folders rolls up through both levels correctly."""
    mount = _stick(
        tmp_path,
        crates={_stem(tmp_path, "Music%%Genres%%Techno"): ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3"],
    )
    outer = Playlist(id=8, name="Music", parent_id=None, is_folder=True)
    inner = Playlist(id=9, name="Genres", parent_id=8, is_folder=True)
    techno = Playlist(id=1, name="Techno", parent_id=9, is_folder=False)
    library = make_library(mount, _adapter([outer, inner, techno], {1: ["/Contents/a.mp3"]}))

    (outer_state,) = playlist_tree_sync_states(library)

    assert outer_state.state is SyncState.SYNCED
    assert outer_state.leaf_ids == (1,)
    assert outer_state.children[0].state is SyncState.SYNCED
    assert outer_state.children[0].leaf_ids == (1,)
    assert outer_state.children[0].children[0].state is SyncState.SYNCED
    assert outer_state.children[0].children[0].leaf_ids == (1,)


def test_summary_counts_states(tmp_path: Path) -> None:
    """Serialization summarises how many playlists sit in each state."""
    mount = _stick(
        tmp_path, crates={_stem(tmp_path, "A"): ["Contents/a.mp3"]}, indexed=["Contents/a.mp3"]
    )
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
