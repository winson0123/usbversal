"""Tests for the TUI Library screen (step 3: the playlist tree)."""

import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import Static, Tree

from app.core.domain import Playlist
from app.tui.app import RekordboxThreadMixin
from app.tui.screens.library import LibraryScreen
from tests.conftest import EMPTY_DATABASE_V2, make_library


class _DummyProgressScreen(Screen):
    """Stands in for the real Progress screen -- that screen's own behaviour
    is covered by tests/test_tui_progress.py; these tests only need proof
    that Library handed off to it with the right selection."""

    def __init__(self, library: object, playlist_ids: list[int]) -> None:
        super().__init__()
        self.library = library
        self.playlist_ids = playlist_ids

    def compose(self):
        yield Static("dummy")


def _stick(root: Path, *, crates: dict[str, list[str]], indexed: list[str]) -> Path:
    """Create a mount with a Rekordbox export and a Serato library."""
    rb = root / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"stub")

    serato = root / "_Serato_"
    (serato / "Subcrates").mkdir(parents=True)
    db = EMPTY_DATABASE_V2
    for path in indexed:
        db += (
            b"otrk"
            + struct.pack(">I", len(b"pfil") + 4 + len(path.encode("utf-16-be")))
            + b"pfil"
            + struct.pack(">I", len(path.encode("utf-16-be")))
            + path.encode("utf-16-be")
        )
    (serato / "database V2").write_bytes(db)
    for name, paths in crates.items():
        version = "1.0/Serato ScratchLive Crate".encode("utf-16-be")
        blob = b"vrsn" + struct.pack(">I", len(version)) + version
        for path in paths:
            inner = (
                b"ptrk"
                + struct.pack(">I", len(path.encode("utf-16-be")))
                + path.encode("utf-16-be")
            )
            blob += b"otrk" + struct.pack(">I", len(inner)) + inner
        (serato / "Subcrates" / f"{name}.crate").write_bytes(blob)
    return root


def _adapter(playlists: list[Playlist], tracks: dict[int, list[str]]) -> MagicMock:
    adapter = MagicMock()
    adapter.list_playlists.return_value = playlists
    adapter.get_playlist_track_paths.side_effect = lambda pid: tracks[pid]
    return adapter


class _Harness(RekordboxThreadMixin, App):
    """Minimal app that pushes a Library screen for one library.

    Mixes in RekordboxThreadMixin directly rather than subclassing
    UsbversalApp: Textual dispatches on_mount to every class in the MRO that
    defines one, so subclassing UsbversalApp (which has its own on_mount
    pushing HomeScreen) would push both screens.
    """

    def __init__(self, library) -> None:
        super().__init__()
        self._library = library

    def on_mount(self) -> None:
        self.push_screen(LibraryScreen(self._library))


def _library_with_two_playlists(tmp_path: Path):
    """One synced, one unsynced top-level playlist."""
    mount = _stick(
        tmp_path,
        crates={"Techno": ["Contents/a.mp3"]},
        indexed=["Contents/a.mp3", "Contents/b.mp3"],
    )
    playlists = [
        Playlist(id=1, name="Techno", parent_id=None, is_folder=False),
        Playlist(id=2, name="Trance", parent_id=None, is_folder=False),
    ]
    tracks = {1: ["/Contents/a.mp3"], 2: ["/Contents/b.mp3"]}
    return make_library(mount, _adapter(playlists, tracks))


@pytest.mark.asyncio
async def test_tree_shows_every_playlist_with_its_state(tmp_path: Path) -> None:
    """Each playlist appears in the tree labelled with its sync state."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        labels = [str(node.label) for node in tree.root.children]

        assert any("Techno" in label and "synced" in label for label in labels)
        assert any("Trance" in label and "not synced" in label for label in labels)


@pytest.mark.asyncio
async def test_space_selects_the_highlighted_playlist(tmp_path: Path) -> None:
    """Pressing space on a leaf toggles it into the selection."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "1 playlist selected" in status


@pytest.mark.asyncio
async def test_space_again_deselects(tmp_path: Path) -> None:
    """Toggling the same node twice returns to nothing selected."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.press("space")
        await pilot.pause()

        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "0 playlists selected" in status


@pytest.mark.asyncio
async def test_space_on_a_folder_selects_every_descendant(tmp_path: Path) -> None:
    """Toggling a folder toggles all of its playlists at once."""
    mount = _stick(tmp_path, crates={}, indexed=[])
    playlists = [
        Playlist(id=9, name="Genres", parent_id=None, is_folder=True),
        Playlist(id=1, name="Techno", parent_id=9, is_folder=False),
        Playlist(id=2, name="Trance", parent_id=9, is_folder=False),
    ]
    tracks = {1: [], 2: []}
    library = make_library(mount, _adapter(playlists, tracks))
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "2 playlists selected" in status


@pytest.mark.asyncio
async def test_enter_with_no_selection_does_not_start_a_sync(tmp_path: Path) -> None:
    """Confirming with nothing selected just re-reports zero selected."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    with patch("app.tui.screens.library.ProgressScreen", _DummyProgressScreen):
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, LibraryScreen)
            status = str(app.screen.query_one("#selection-status", Static).render())
            assert "0 playlists selected" in status


@pytest.mark.asyncio
async def test_enter_with_a_selection_starts_the_sync(tmp_path: Path) -> None:
    """Confirming a selection hands off to the Progress screen with it."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    with patch("app.tui.screens.library.ProgressScreen", _DummyProgressScreen):
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("space")
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, _DummyProgressScreen)
            assert app.screen.library is library
            assert app.screen.playlist_ids == [1]
