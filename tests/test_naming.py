"""Tests for mapping Rekordbox playlists to Serato crate filenames."""

from pathlib import Path

import pytest

from app.adapters.serato.naming import (
    crate_name_for,
    crate_name_slash_aliases,
    drop_legacy_slash_names,
    volume_label_for,
)
from app.core.domain import Playlist


@pytest.mark.parametrize(
    ("playlists", "leaf_id", "expected"),
    [
        (
            [Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)],
            1,
            "Pocket",
        ),
        (
            [
                Playlist(id=9, name="Techno", parent_id=None, is_folder=True),
                Playlist(id=1, name="Peak Time", parent_id=9, is_folder=False),
            ],
            1,
            "Techno%%Peak Time",
        ),
        (
            [
                Playlist(id=8, name="Music", parent_id=None, is_folder=True),
                Playlist(id=9, name="Techno", parent_id=8, is_folder=True),
                Playlist(id=1, name="Peak Time", parent_id=9, is_folder=False),
            ],
            1,
            "Music%%Techno%%Peak Time",
        ),
    ],
)
def test_crate_name_joins_ancestors(playlists: list[Playlist], leaf_id: int, expected: str) -> None:
    """Folder ancestors become a %% path; a top-level playlist is just its name."""
    by_id = {playlist.id: playlist for playlist in playlists}
    assert crate_name_for(by_id[leaf_id], by_id) == expected


def test_each_ancestor_name_is_sanitized_independently() -> None:
    """A folder name with invalid filename characters is cleaned like any other."""
    folder = Playlist(id=9, name="Techno/House", parent_id=None, is_folder=True)
    playlist = Playlist(id=1, name="2024?", parent_id=9, is_folder=False)
    by_id = {9: folder, 1: playlist}

    assert crate_name_for(playlist, by_id) == "Techno\u241b\u241b2fHouse%%2024_"


def test_a_slash_in_the_name_uses_serato_escape() -> None:
    """Rekordbox 'Afro / Afro House' must match Serato's own slash rename."""
    from app.adapters.serato.naming import sanitize_crate_name

    assert sanitize_crate_name("Afro / Afro House") == "Afro \u241b\u241b2f Afro House"


def test_slash_aliases_include_older_stand_ins() -> None:
    """A re-sync deletes leftover fullwidth and division-slash crate names."""
    current = "MY_USB%%Afro \u241b\u241b2f Afro House"
    fullwidth = "MY_USB%%Afro \uff0f Afro House"
    division = "MY_USB%%Afro \u2215 Afro House"
    assert crate_name_slash_aliases(current) == (current, fullwidth, division)
    assert drop_legacy_slash_names([fullwidth, division, current, "Pocket"], [current]) == [
        current,
        "Pocket",
    ]


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
    mount = tmp_path / "MY_USB"
    mount.mkdir()
    assert volume_label_for(mount) == "MY_USB"


def test_volume_label_falls_back_when_the_folder_has_no_name(tmp_path: Path) -> None:
    """A path whose name is empty and has no platform label becomes USB."""
    assert volume_label_for(Path("/")) == "USB"


def test_volume_label_uses_the_windows_filesystem_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare drive letter reads the stick's Windows volume label."""
    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "app.storage.mounts._windows_mount_label",
        lambda mount: "MY_USB",
    )

    assert volume_label_for(Path("E:/")) == "MY_USB"


def test_volume_label_uses_the_drive_letter_when_windows_label_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unlabeled Windows stick still gets a stable parent name."""
    monkeypatch.setattr("app.storage.mounts.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "app.storage.mounts._windows_mount_label",
        lambda mount: "E",
    )

    assert volume_label_for(Path("E:/")) == "E"


def test_crate_name_prefixes_the_volume() -> None:
    """Every synced crate sits under the thumbdrive name."""
    playlist = Playlist(id=1, name="Contents", parent_id=None, is_folder=False)
    assert crate_name_for(playlist, {1: playlist}, volume="MY_USB") == "MY_USB%%Contents"
