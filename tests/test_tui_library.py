"""Tests for the TUI Library screen (step 3: the playlist tree)."""

import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import DataTable, Static, Tree

from app.adapters.serato.naming import volume_label_for
from app.core.domain import Playlist
from app.tui.app import RekordboxThreadMixin
from app.tui.screens.library import LibraryScreen, _clip, _legend_text
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
    adapter.database.get_contents.return_value = []
    adapter.database.get_artists.return_value = []
    adapter.database.get_albums.return_value = []
    adapter.database.get_genres.return_value = []
    adapter.database.get_keys.return_value = []
    return adapter


def _playlist_nodes(tree: Tree):
    """Top-level playlist and folder nodes under the hidden Tree root."""
    return tree.root.children


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
        crates={f"{volume_label_for(tmp_path)}%%Techno": ["Contents/a.mp3"]},
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

        assert any("Techno" in label and "1/1" in label for label in labels)
        assert any("Trance" in label and "0/1" in label for label in labels)
        assert all("not synced" not in label and "partial" not in label for label in labels)


@pytest.mark.asyncio
async def test_tree_has_no_all_playlists_parent(tmp_path: Path) -> None:
    """Top-level playlists sit on the hidden root so they are not indented."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        names = [node.data.name for node in tree.root.children]
        assert names == ["Techno", "Trance"]
        assert "All playlists" not in names


@pytest.mark.asyncio
async def test_e_does_nothing_on_a_leaf(tmp_path: Path) -> None:
    """Expand/collapse on a non-folder row is a no-op, not an error."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

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
        _write_crate(
            library.mount / "_Serato_",
            f"{volume_label_for(library.mount)}%%Trance",
            ["Contents/b.mp3"],
        )

        # Simulate returning from Progress/Done: push another screen, then
        # pop back to this one -- the same path DoneScreen's enter takes.
        app.push_screen(Screen())
        await pilot.pause()
        app.pop_screen()
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        after = {node.data.name: str(node.label) for node in _playlist_nodes(tree)}
        assert "1/1" in after["Trance"]
        assert "not synced" not in after["Trance"]


@pytest.mark.asyncio
async def test_a_selects_every_playlist(tmp_path: Path) -> None:
    """Select-all is a key, not a parent row that indents the tree."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()

        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "2 playlists selected" in status


@pytest.mark.asyncio
async def test_a_again_clears_the_selection(tmp_path: Path) -> None:
    """Pressing a when everything is selected returns to nothing selected."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.press("a")
        await pilot.pause()

        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "0 playlists selected" in status


@pytest.mark.asyncio
async def test_space_selects_the_highlighted_playlist(tmp_path: Path) -> None:
    """Pressing space on a leaf toggles just that one."""
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
    alignment.     _prefix_width compensates for exactly that, so the count
    column should start at the same character offset on a top-level
    folder (depth 0, with an icon), a nested folder (depth 1, with an
    icon), and a leaf two levels down (depth 2, no icon).
    """
    mount = _stick(tmp_path, crates={}, indexed=[])
    playlists = [
        Playlist(id=8, name="Music", parent_id=None, is_folder=True),
        Playlist(id=9, name="Genres", parent_id=8, is_folder=True),
        Playlist(id=1, name="Techno", parent_id=9, is_folder=False),
    ]
    library = make_library(mount, _adapter(playlists, {1: []}))
    app = _Harness(library)
    async with app.run_test(size=(120, 24)) as pilot:
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        app.screen.on_resize()
        await pilot.pause()
        lines = ["".join(segment.text for segment in tree.render_line(y)) for y in range(3)]
        # "Music" (depth 0, folder icon), "Genres" (depth 1, folder icon),
        # "Techno" (depth 2, leaf) -- folder and leaf at different depths.
        positions = {line.index("0/0") for line in lines}

        assert len(positions) == 1, lines


@pytest.mark.asyncio
async def test_nested_playlist_names_stay_readable(tmp_path: Path) -> None:
    """A fixed 16-cell name column left depth-3 folders as a single letter."""
    mount = _stick(tmp_path, crates={}, indexed=[])
    playlists = [
        Playlist(id=1, name="Genres", parent_id=None, is_folder=True),
        Playlist(id=2, name="House", parent_id=1, is_folder=True),
        Playlist(id=3, name="Amapiano", parent_id=2, is_folder=False),
        Playlist(id=4, name="Africa", parent_id=2, is_folder=False),
    ]
    library = make_library(mount, _adapter(playlists, {3: [], 4: []}))
    app = _Harness(library)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.screen.on_resize()
        await pilot.pause()

        tree = app.screen.query_one(Tree)
        text = "\n".join(
            "".join(segment.text for segment in tree.render_line(y))
            for y in range(tree.virtual_size.height)
        )
        assert "Amapiano" in text
        assert "Africa" in text
        assert "House" in text


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


@pytest.mark.asyncio
async def test_library_is_two_panes_with_a_legend(tmp_path: Path) -> None:
    """Playlists sit on the left with a colour key; tracks sit on the right."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#playlist-pane").border_title == "Playlists"
        assert app.screen.query_one("#track-pane").border_title == "Tracks"
        legend = str(app.screen.query_one("#sync-legend", Static).render())
        assert "synced" in legend and "partial" in legend and "not synced" in legend
        assert app.screen.query_one("#playlist-pane").styles.border.top[0] == "round"
        assert app.screen.query_one("#sync-legend").styles.border.top[0] == "solid"
        assert app.screen.query_one("#sync-legend").styles.margin.top == 1
        assert app.screen.query_one("#sync-legend").styles.padding.top == 0
        header = app.screen.query_one("#header")
        assert [child.id for child in header.children] == ["mount-info", "selection-status"]
        table = app.screen.query_one("#track-table", DataTable)
        assert [str(col.label) for col in table.columns.values()] == [
            "Title",
            "Genre",
            "Key",
            "BPM",
        ]


@pytest.mark.asyncio
async def test_highlighting_a_playlist_fills_the_track_table(tmp_path: Path) -> None:
    """The right pane lists the highlighted playlist's tracks."""
    library = _library_with_two_playlists(tmp_path)
    content = type(
        "Row",
        (),
        {
            "path": "/Contents/a.mp3",
            "title": "Alpha",
            "genre_id": None,
            "key_id": None,
            "bpmx100": 12800,
        },
    )()
    library.rekordbox.database.get_contents.return_value = [content]
    app = _Harness(library)
    async with app.run_test() as pilot:
        await pilot.pause()

        table = app.screen.query_one("#track-table", DataTable)
        assert table.row_count == 1
        assert table.get_row_at(0)[0].plain == "Alpha"


def test_legend_words_use_the_same_colour_as_the_dot() -> None:
    """Each legend label is the same traffic-light colour as its bullet."""
    legend = _legend_text()
    coloured = {
        colour: "".join(
            legend.plain[span.start : span.end]
            for span in legend.spans
            if colour in str(span.style)
        )
        for colour in ("green", "yellow", "red")
    }
    assert "synced" in coloured["green"]
    assert "partial" in coloured["yellow"]
    assert "not synced" in coloured["red"]


def test_clip_adds_ellipsis_when_text_is_wider_than_the_column() -> None:
    """Long titles shrink to the column so Genre / Key / BPM stay visible."""
    assert _clip("Alpha", 8) == "Alpha"
    assert _clip("A very long track title", 10) == "A very ..."
    assert _clip("Hi", 2) == "Hi"
