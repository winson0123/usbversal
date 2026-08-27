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


def _write_crate(serato_root: Path, name: str, paths: list[str]) -> None:
    """Write one .crate file holding the given track paths."""
    version = "1.0/Serato ScratchLive Crate".encode("utf-16-be")
    blob = b"vrsn" + struct.pack(">I", len(version)) + version
    for path in paths:
        inner = (
            b"ptrk" + struct.pack(">I", len(path.encode("utf-16-be"))) + path.encode("utf-16-be")
        )
        blob += b"otrk" + struct.pack(">I", len(inner)) + inner
    (serato_root / "Subcrates" / f"{name}.crate").write_bytes(blob)


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
        _write_crate(serato, name, paths)
    return root


def _adapter(playlists: list[Playlist], tracks: dict[int, list[str]]) -> MagicMock:
    adapter = MagicMock()
    adapter.list_playlists.return_value = playlists
    adapter.get_playlist_track_paths.side_effect = lambda pid: tracks[pid]
    return adapter


def _playlist_nodes(tree: Tree):
    """Real playlist/folder nodes, one level under the "All playlists" root."""
    return tree.root.children[0].children


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
    """Each playlist appears labelled with its sync state and synced/total counts."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        labels = [str(node.label) for node in _playlist_nodes(tree)]

        assert any("Techno" in label and "synced" in label and "1/1" in label for label in labels)
        assert any(
            "Trance" in label and "not synced" in label and "0/1" in label for label in labels
        )


@pytest.mark.asyncio
async def test_all_playlists_row_contains_everything_and_aggregates_it(
    tmp_path: Path,
) -> None:
    """ "All playlists" is a real folder holding every top-level node, and
    rolls up state/counts across the whole library."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        all_node = tree.root.children[0]

        assert all_node.data.name == "All playlists"
        assert all_node.allow_expand
        assert {child.data.name for child in all_node.children} == {"Techno", "Trance"}
        # Techno is 1/1 synced, Trance is 0/1 -- mixed, so partial; counts sum.
        assert "1/2" in str(all_node.label)
        assert "partial" in str(all_node.label)


@pytest.mark.asyncio
async def test_all_playlists_is_collapsible(tmp_path: Path) -> None:
    """Pressing "e" on "All playlists" collapses it, hiding every playlist."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        all_node = app.screen.query_one(Tree).root.children[0]
        assert all_node.is_expanded

        await pilot.press("e")
        await pilot.pause()

        assert not all_node.is_expanded


@pytest.mark.asyncio
async def test_e_does_nothing_on_a_leaf(tmp_path: Path) -> None:
    """Expand/collapse on a non-folder row is a no-op, not an error."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")  # move off "All playlists" onto "Techno", a leaf

        await pilot.press("e")
        await pilot.pause()

        # Still there, still showing everything -- nothing broke.
        tree = app.screen.query_one(Tree)
        assert {child.data.name for child in _playlist_nodes(tree)} == {"Techno", "Trance"}


@pytest.mark.asyncio
async def test_returning_to_the_screen_reflects_a_sync_that_just_happened(
    tmp_path: Path,
) -> None:
    """The bug this closes: the tree used to stay stale until the app restarted.

    LibraryScreen built its tree once in on_mount and never again, so
    Done -> enter -> pop_screen landed back on a screen still showing
    whatever was true before the sync ran. on_screen_resume now rebuilds it.
    """
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(Tree)
        before = {node.data.name: str(node.label) for node in _playlist_nodes(tree)}
        assert "0/1" in before["Trance"]

        # Simulate what a completed sync writes: Trance now has a crate.
        _write_crate(library.mount / "_Serato_", "Trance", ["Contents/b.mp3"])

        # Simulate returning from Progress/Done: push another screen, then
        # pop back to this one -- the same path DoneScreen's enter takes.
        app.push_screen(Screen())
        await pilot.pause()
        app.pop_screen()
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        after = {node.data.name: str(node.label) for node in _playlist_nodes(tree)}
        assert "1/1" in after["Trance"]
        assert "synced" in after["Trance"]
        assert "not" not in after["Trance"]


@pytest.mark.asyncio
async def test_space_on_all_playlists_selects_everything(tmp_path: Path) -> None:
    """The cursor starts on the synthetic "All playlists" row; space selects everything."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "2 playlists selected" in status


@pytest.mark.asyncio
async def test_space_selects_the_highlighted_playlist(tmp_path: Path) -> None:
    """Pressing space on a leaf (past the "All" row) toggles just that one."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")  # move off "All playlists" onto "Techno"
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
        await pilot.press("down")
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
        await pilot.press("down")  # move off "All playlists" onto "Genres"
        await pilot.press("space")
        await pilot.pause()

        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "2 playlists selected" in status


@pytest.mark.asyncio
async def test_count_column_lines_up_regardless_of_depth_or_row_kind(tmp_path: Path) -> None:
    """The bug the user reported: columns looked jagged across different rows.

    Tree's own guide lines and expand icon eat a different amount of space
    per row depending on nesting depth and whether the row is a folder or a
    leaf, so naive fixed-width padding on the label text alone drifts out of
    alignment. _prefix_width compensates for exactly that, so the count
    column should start at the same character offset on "All playlists"
    (depth 0, no icon), a folder (depth 0, with an icon), and a leaf nested
    two levels deep (depth 2, no icon).
    """
    mount = _stick(tmp_path, crates={}, indexed=[])
    playlists = [
        Playlist(id=8, name="Music", parent_id=None, is_folder=True),
        Playlist(id=9, name="Genres", parent_id=8, is_folder=True),
        Playlist(id=1, name="Techno", parent_id=9, is_folder=False),
    ]
    library = make_library(mount, _adapter(playlists, {1: []}))
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        lines = ["".join(segment.text for segment in tree.render_line(y)) for y in range(3)]
        # "All playlists" (depth 0, no icon), "Music" (depth 0, folder icon),
        # "Genres" (depth 1, folder icon) -- covers every combination this
        # fixture can reach without a third nesting level.
        positions = {line.index("0/0") for line in lines}

        assert len(positions) == 1, lines


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
            await pilot.press("down")  # move off "All playlists" onto "Techno"
            await pilot.press("space")
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, _DummyProgressScreen)
            assert app.screen.library is library
            assert app.screen.playlist_ids == [1]
