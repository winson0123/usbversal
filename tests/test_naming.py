"""Tests for mapping Rekordbox playlists to Serato crate filenames."""

from pathlib import Path

from app.adapters.serato.naming import crate_name_for, volume_label_for
from app.core.domain import Playlist


def test_a_top_level_playlist_maps_to_its_own_name() -> None:
    """No parent means no prefix at all."""
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)

    assert crate_name_for(playlist, {1: playlist}) == "Pocket"


def test_a_nested_playlist_is_prefixed_with_its_folder() -> None:
    """One level of nesting joins folder and playlist with '%%'."""
    folder = Playlist(id=9, name="Techno", parent_id=None, is_folder=True)
    playlist = Playlist(id=1, name="Peak Time", parent_id=9, is_folder=False)
    by_id = {9: folder, 1: playlist}

    assert crate_name_for(playlist, by_id) == "Techno%%Peak Time"


def test_deep_nesting_joins_every_ancestor_in_order() -> None:
    """Multiple folder levels all appear, outermost first."""
    outer = Playlist(id=8, name="Music", parent_id=None, is_folder=True)
    inner = Playlist(id=9, name="Techno", parent_id=8, is_folder=True)
    playlist = Playlist(id=1, name="Peak Time", parent_id=9, is_folder=False)
    by_id = {8: outer, 9: inner, 1: playlist}

    assert crate_name_for(playlist, by_id) == "Music%%Techno%%Peak Time"


def test_same_named_playlists_in_different_folders_no_longer_collide() -> None:
    """The bug this task fixes: two 'Peak Time' playlists get distinct names."""
    techno = Playlist(id=9, name="Techno", parent_id=None, is_folder=True)
    trance = Playlist(id=10, name="Trance", parent_id=None, is_folder=True)
    techno_peak = Playlist(id=1, name="Peak Time", parent_id=9, is_folder=False)
    trance_peak = Playlist(id=2, name="Peak Time", parent_id=10, is_folder=False)
    by_id = {9: techno, 10: trance, 1: techno_peak, 2: trance_peak}

    assert crate_name_for(techno_peak, by_id) != crate_name_for(trance_peak, by_id)
    assert crate_name_for(techno_peak, by_id) == "Techno%%Peak Time"
    assert crate_name_for(trance_peak, by_id) == "Trance%%Peak Time"


def test_each_ancestor_name_is_sanitized_independently() -> None:
    """A folder name with invalid filename characters is cleaned like any other."""
    folder = Playlist(id=9, name="Techno/House", parent_id=None, is_folder=True)
    playlist = Playlist(id=1, name="2024?", parent_id=9, is_folder=False)
    by_id = {9: folder, 1: playlist}

    assert crate_name_for(playlist, by_id) == "Techno\uff0fHouse%%2024_"


def test_a_slash_in_the_name_stays_a_slash() -> None:
    """Rekordbox 'Afro / Afro House' must not become 'Afro _ Afro House'."""
    from app.adapters.serato.naming import sanitize_crate_name

    assert sanitize_crate_name("Afro / Afro House") == "Afro \uff0f Afro House"


def test_a_dangling_parent_reference_stops_rather_than_raising() -> None:
    """A playlist whose parent isn't in by_id falls back to its own name."""
    playlist = Playlist(id=1, name="Orphan", parent_id=999, is_folder=False)

    assert crate_name_for(playlist, {1: playlist}) == "Orphan"


def test_a_parent_cycle_does_not_infinite_loop() -> None:
    """A malformed parent_id cycle terminates instead of hanging."""
    a = Playlist(id=1, name="A", parent_id=2, is_folder=True)
    b = Playlist(id=2, name="B", parent_id=1, is_folder=True)
    playlist = Playlist(id=3, name="Leaf", parent_id=1, is_folder=False)
    by_id = {1: a, 2: b, 3: playlist}

    assert crate_name_for(playlist, by_id) == "B%%A%%Leaf"


def test_volume_label_is_the_mount_folder_name(tmp_path: Path) -> None:
    """A labelled mount folder becomes the parent crate name."""
    mount = tmp_path / "WONSIN"
    mount.mkdir()
    assert volume_label_for(mount) == "WONSIN"


def test_volume_label_falls_back_when_the_folder_has_no_name(tmp_path: Path) -> None:
    """A path whose name is empty cannot be a crate parent."""
    assert volume_label_for(Path("/")) == "USB"


def test_crate_name_prefixes_the_volume() -> None:
    """Every synced crate sits under the thumbdrive name."""
    playlist = Playlist(id=1, name="Contents", parent_id=None, is_folder=False)
    assert crate_name_for(playlist, {1: playlist}, volume="WONSIN") == "WONSIN%%Contents"
