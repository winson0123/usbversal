"""Tests for the TUI Library screen (step 3: the playlist tree)."""

import asyncio
import struct
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import DataTable, Static, Tree

from app.adapters.serato.naming import volume_label_for
from app.core.domain import Playlist
from app.services.sync_service import playlist_tree_sync_states
from app.tui.app import RekordboxThreadMixin
from app.tui.screens.library import LibraryScreen
from tests.conftest import EMPTY_DATABASE_V2, make_library


class _DummyProgressScreen(Screen):
    """Stands in for the real Progress screen. That screen's own behaviour
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


async def _wait_library(app: App, pilot) -> None:
    """
    Wait until the Library tree is filled and analysis colours have landed.

    A second ScreenResume can cancel the first exclusive worker; waiting
    on every worker then raises. The tree and status line are the signal
    the latest pass finished.

    Args:
        app: The running test app.
        pilot: Textual test pilot.
    """
    for _ in range(50):
        await pilot.pause()
        screen = app.screen
        if not isinstance(screen, LibraryScreen):
            continue
        tree = screen.query_one(Tree)
        status = str(screen.query_one("#selection-status", Static).render())
        if tree.root.children and "Reading" not in status and "Checking" not in status:
            return
    raise AssertionError("library tree never finished loading")


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
async def test_resume_does_not_block_the_screen(tmp_path: Path) -> None:
    """Home used to stay up, scan bar frozen, until every ANLZ/GEOB was read."""
    library = _library_with_two_playlists(tmp_path)
    gate = threading.Event()

    def blocked(lib, *, check_analysis: bool = True):
        gate.wait(timeout=5)
        return playlist_tree_sync_states(lib, check_analysis=check_analysis)

    with patch("app.tui.screens.library.playlist_tree_sync_states", blocked):
        app = _Harness(library)
        async with app.run_test() as pilot:
            await asyncio.wait_for(pilot.pause(), timeout=2)
            assert isinstance(app.screen, LibraryScreen)
            status = str(app.screen.query_one("#selection-status", Static).render())
            assert "Reading" in status
            gate.set()
            await _wait_library(app, pilot)
            names = {node.data.name for node in _playlist_nodes(app.screen.query_one(Tree))}
            assert names == {"Techno", "Trance"}


@pytest.mark.asyncio
async def test_tree_shows_every_playlist_with_its_state(tmp_path: Path) -> None:
    """Each playlist appears labelled with its sync state and synced/total counts."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await _wait_library(app, pilot)

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
        await _wait_library(app, pilot)

        tree = app.screen.query_one(Tree)
        names = [node.data.name for node in tree.root.children]
        assert names == ["Techno", "Trance"]
        assert "All playlists" not in names


@pytest.mark.asyncio
async def test_returning_to_the_screen_reflects_a_sync_that_just_happened(
    tmp_path: Path,
) -> None:
    """Done applies the sync report so the tree updates without an ANLZ re-scan."""
    from app.services.sync_service import PlaylistSyncResult, SyncReport
    from app.tui.screens.progress import DoneScreen

    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await _wait_library(app, pilot)
        tree = app.screen.query_one(Tree)
        before = {node.data.name: str(node.label) for node in _playlist_nodes(tree)}
        assert "0/1" in before["Trance"]
        assert "1/1" in before["Techno"]

        report = SyncReport(
            mount=library.mount,
            records_added=0,
            results=(
                PlaylistSyncResult(
                    playlist_id=2,
                    playlist_name="Trance",
                    crate_name=f"{volume_label_for(library.mount)}%%Trance",
                    tracks=1,
                ),
            ),
        )
        # Same stack path as a real sync: Library -> Progress-like -> Done -> pop.
        app.push_screen(DoneScreen(report=report))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, LibraryScreen)
        tree = screen.query_one(Tree)
        after = {node.data.name: str(node.label) for node in _playlist_nodes(tree)}
        assert "1/1" in after["Trance"]
        assert "1/1" in after["Techno"]


@pytest.mark.asyncio
async def test_post_sync_resume_skips_analysis_refresh(tmp_path: Path) -> None:
    """Returning from Done must not re-run playlist_tree_sync_states."""
    from app.services.sync_service import PlaylistSyncResult, SyncReport
    from app.tui.screens.progress import DoneScreen

    library = _library_with_two_playlists(tmp_path)
    calls: list[bool] = []

    def tracking(lib, *, check_analysis: bool = True):
        calls.append(check_analysis)
        return playlist_tree_sync_states(lib, check_analysis=check_analysis)

    with patch("app.tui.screens.library.playlist_tree_sync_states", tracking):
        app = _Harness(library)
        async with app.run_test() as pilot:
            await _wait_library(app, pilot)
            calls.clear()

            report = SyncReport(
                mount=library.mount,
                records_added=0,
                results=(
                    PlaylistSyncResult(
                        playlist_id=1,
                        playlist_name="Techno",
                        crate_name=f"{volume_label_for(library.mount)}%%Techno",
                        tracks=1,
                    ),
                ),
            )
            app.push_screen(DoneScreen(report=report))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

    assert calls == []


@pytest.mark.asyncio
async def test_resume_skips_crate_only_pass_that_flashed_unsynced(
    tmp_path: Path,
) -> None:
    """A plain resume (not post-sync) still does a full analysis pass only."""
    library = _library_with_two_playlists(tmp_path)
    calls: list[bool] = []

    def tracking(lib, *, check_analysis: bool = True):
        calls.append(check_analysis)
        return playlist_tree_sync_states(lib, check_analysis=check_analysis)

    with patch("app.tui.screens.library.playlist_tree_sync_states", tracking):
        app = _Harness(library)
        async with app.run_test() as pilot:
            await _wait_library(app, pilot)
            # Test harness has no Home-precomputed states, so first open
            # still does the cheap crate pass then the analysis pass.
            assert calls == [False, True]
            calls.clear()

            app.push_screen(Screen())
            await pilot.pause()
            app.pop_screen()
            await _wait_library(app, pilot)

    assert calls == [True]


@pytest.mark.asyncio
async def test_a_toggles_select_all(tmp_path: Path) -> None:
    """^a selects every playlist, then clears the selection."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await _wait_library(app, pilot)
        await pilot.press("ctrl+a")
        await pilot.pause()
        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "2 playlists selected" in status

        await pilot.press("ctrl+a")
        await pilot.pause()
        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "0 playlists selected" in status


@pytest.mark.asyncio
async def test_space_toggles_the_highlighted_playlist(tmp_path: Path) -> None:
    """Space selects the cursor leaf, then deselects it."""
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    async with app.run_test() as pilot:
        await _wait_library(app, pilot)
        await pilot.press("space")
        await pilot.pause()
        status = str(app.screen.query_one("#selection-status", Static).render())
        assert "1 playlist selected" in status

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
        await _wait_library(app, pilot)
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
            await _wait_library(app, pilot)
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
            await _wait_library(app, pilot)
            await pilot.press("space")
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, _DummyProgressScreen)
            assert app.screen.library is library
            assert app.screen.playlist_ids == [1]


@pytest.mark.asyncio
async def test_tree_node_selected_toggles_without_starting_sync(tmp_path: Path) -> None:
    """
    Mouse click posts NodeSelected; that must select, not sync.

    Enter alone starts the sync (priority binding). Click must not.
    """
    library = _library_with_two_playlists(tmp_path)
    app = _Harness(library)
    with patch("app.tui.screens.library.ProgressScreen", _DummyProgressScreen):
        async with app.run_test() as pilot:
            await _wait_library(app, pilot)
            screen = app.screen
            assert isinstance(screen, LibraryScreen)
            tree = screen.query_one(Tree)
            node = tree.root.children[0]
            tree.post_message(Tree.NodeSelected(node))
            await pilot.pause()

            assert isinstance(app.screen, LibraryScreen)
            status = str(app.screen.query_one("#selection-status", Static).render())
            assert "1 playlist selected" in status

            tree.post_message(Tree.NodeSelected(node))
            await pilot.pause()
            status = str(app.screen.query_one("#selection-status", Static).render())
            assert "0 playlists selected" in status


@pytest.mark.asyncio
async def test_revisiting_a_playlist_uses_the_preview_cache(tmp_path: Path) -> None:
    """Moving away and back must not reload the same playlist from Rekordbox."""
    library = _library_with_two_playlists(tmp_path)
    content_a = type(
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
    content_b = type(
        "Row",
        (),
        {
            "path": "/Contents/b.mp3",
            "title": "Beta",
            "genre_id": None,
            "key_id": None,
            "bpmx100": 14000,
        },
    )()
    library.rekordbox.database.get_contents.return_value = [content_a, content_b]

    calls: list[int] = []
    real_preview = __import__(
        "app.services.track_preview", fromlist=["preview_playlist_tracks"]
    ).preview_playlist_tracks

    def counting_preview(lib, playlist_id: int, **kwargs):
        """Record each preview load while still returning real rows."""
        calls.append(playlist_id)
        return real_preview(lib, playlist_id, **kwargs)

    app = _Harness(library)
    with patch("app.tui.screens.library.preview_playlist_tracks", counting_preview):
        async with app.run_test() as pilot:
            await _wait_library(app, pilot)
            screen = app.screen
            assert isinstance(screen, LibraryScreen)
            for _ in range(40):
                await pilot.pause()
                if 1 in screen._preview_cache and 2 in screen._preview_cache:
                    break
            first_loads = list(calls)
            assert 1 in first_loads

            await pilot.press("down")
            await pilot.pause()
            await pilot.press("up")
            await pilot.pause()

            assert calls.count(1) == first_loads.count(1)
            table = screen.query_one("#track-table", DataTable)
            assert table.display is True
            assert table.get_row_at(0)[0].plain == "Alpha"


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
        await _wait_library(app, pilot)

        table = app.screen.query_one("#track-table", DataTable)
        assert table.display is True
        assert table.row_count == 1
        assert table.get_row_at(0)[0].plain == "Alpha"


@pytest.mark.asyncio
async def test_preview_failure_clears_table_without_crashing(tmp_path: Path) -> None:
    """A broken Rekordbox lookup must leave the Library screen usable."""
    library = _library_with_two_playlists(tmp_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("Diesel error: Unexpected null for non-null column")

    with patch("app.tui.screens.library.preview_playlist_tracks", boom):
        app = _Harness(library)
        async with app.run_test() as pilot:
            await _wait_library(app, pilot)
            for _ in range(20):
                await pilot.pause()
                table = app.screen.query_one("#track-table", DataTable)
                if table.display:
                    break
            table = app.screen.query_one("#track-table", DataTable)
            assert table.display is True
            assert table.row_count == 0
            assert app.screen.query_one("#track-scan-wrap").display is False
            # Screen must still accept selection keys after the failed load.
            await pilot.press("space")
            status = str(app.screen.query_one("#selection-status", Static).render())
            assert "1 playlist selected" in status
            # Failed prefetch must not permanently cache an empty playlist.
            screen = app.screen
            assert isinstance(screen, LibraryScreen)
            assert 1 not in screen._preview_cache


@pytest.mark.asyncio
async def test_empty_library_hides_the_track_scan_bar(tmp_path: Path) -> None:
    """No leaf playlists must not leave the Tracks pane spinning forever."""
    mount = _stick(tmp_path, crates={}, indexed=[])
    folder = Playlist(id=9, name="Empty", parent_id=None, is_folder=True)
    library = make_library(mount, _adapter([folder], {}))
    app = _Harness(library)
    async with app.run_test() as pilot:
        await _wait_library(app, pilot)
        screen = app.screen
        assert isinstance(screen, LibraryScreen)
        assert screen.query_one("#track-scan-wrap").display is False
        assert screen.query_one("#track-table", DataTable).display is True
