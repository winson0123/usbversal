"""Tests for the TUI Progress and Done screens (steps 4-5)."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import ProgressBar, Static

from app.services.sync_service import SyncReport
from app.tui.app import RekordboxThreadMixin
from app.tui.screens.progress import DoneScreen, ProgressScreen


def _fake_report(**overrides) -> SyncReport:
    fields = {
        "mount": Path("/mnt/usb"),
        "dry_run": False,
        "backup_id": "20260101T000000Z",
        "records_added": 1,
        "results": (),
        "grids_written": 2,
        "cues_written": 1,
        "index_rows_updated": 2,
        "analysis_errors": (),
    }
    fields.update(overrides)
    return SyncReport(**fields)


def _fake_sync(*, calls=((1, 2), (2, 2)), report=None, error=None, delay_s=0.0):
    """Build a stand-in for sync_playlists that drives on_progress synchronously."""

    def _sync(library, playlist_ids, *, dry_run=False, backup_root=None, on_progress=None):
        if on_progress is not None:
            for done, total in calls:
                if delay_s:
                    time.sleep(delay_s)
                on_progress(done, total)
        if error is not None:
            raise error
        return report if report is not None else _fake_report()

    return _sync


class _Harness(RekordboxThreadMixin, App):
    """Minimal app that pushes a Progress screen for one sync run.

    Mixes in RekordboxThreadMixin directly rather than subclassing
    UsbversalApp: Textual dispatches on_mount to every class in the MRO that
    defines one, so subclassing UsbversalApp (which has its own on_mount
    pushing HomeScreen) would push both screens.
    """

    def __init__(self, library, playlist_ids) -> None:
        super().__init__()
        self._library = library
        self._playlist_ids = playlist_ids

    def on_mount(self) -> None:
        self.push_screen(ProgressScreen(self._library, self._playlist_ids))


@pytest.mark.asyncio
async def test_progress_updates_the_bar_and_transitions_to_done() -> None:
    """Progress samples update the bar, then the Done screen takes over."""
    with patch(
        "app.tui.screens.progress.sync_playlists",
        _fake_sync(report=_fake_report(records_added=3)),
    ):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert isinstance(app.screen, DoneScreen)
            summary = str(app.screen.query_one("#done-summary", Static).render())
            assert "3 new record" in summary
            assert "Grids: 2" in summary


@pytest.mark.asyncio
async def test_a_sync_failure_is_reported_on_the_done_screen() -> None:
    """An exception from sync_playlists is caught and shown, not raised."""
    with patch(
        "app.tui.screens.progress.sync_playlists",
        _fake_sync(error=RuntimeError("stick unplugged")),
    ):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert isinstance(app.screen, DoneScreen)
            summary = str(app.screen.query_one("#done-summary", Static).render())
            assert "Sync failed" in summary
            assert "stick unplugged" in summary


@pytest.mark.asyncio
async def test_analysis_errors_are_called_out_in_the_summary() -> None:
    """A partially-failed sync says so rather than looking fully clean."""
    with patch(
        "app.tui.screens.progress.sync_playlists",
        _fake_sync(report=_fake_report(analysis_errors=("Contents/a.mp3: bad grid",))),
    ):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            summary = str(app.screen.query_one("#done-summary", Static).render())
            assert "1 track" in summary
            assert "could not be analysed" in summary


class _MarkerScreen(Screen):
    """A recognisable screen underneath Progress, to prove enter returns to it."""

    def compose(self):
        yield Static("library placeholder")


class _LibraryHarness(RekordboxThreadMixin, App):
    """Pushes a marker screen (standing in for Library), then Progress on top."""

    def __init__(self, library, playlist_ids) -> None:
        super().__init__()
        self._library = library
        self._playlist_ids = playlist_ids

    def on_mount(self) -> None:
        self.push_screen(_MarkerScreen())
        self.push_screen(ProgressScreen(self._library, self._playlist_ids))


@pytest.mark.asyncio
async def test_enter_on_done_returns_to_the_screen_under_progress() -> None:
    """Confirming Done pops back to whatever was open before the sync."""
    with patch("app.tui.screens.progress.sync_playlists", _fake_sync()):
        app = _LibraryHarness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, DoneScreen)

            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, _MarkerScreen)


@pytest.mark.asyncio
async def test_progress_bar_reflects_the_last_sample() -> None:
    """_update_progress sets the bar's total/progress and a rate-bearing status line.

    Called directly rather than through the real worker/thread hop: the sync
    itself is synchronous and near-instant once faked, leaving no reliable
    window to catch the screen still on Progress rather than Done.
    """

    def _slow_sync(library, playlist_ids, *, dry_run=False, backup_root=None, on_progress=None):
        time.sleep(0.2)  # keeps the screen on Progress long enough to inspect
        return _fake_report()

    with patch("app.tui.screens.progress.sync_playlists", _slow_sync):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ProgressScreen)

            screen._update_progress(1, 4)
            screen._update_progress(3, 4)

            bar = screen.query_one(ProgressBar)
            assert bar.total == 4
            assert bar.progress == 3

            await app.workers.wait_for_complete()
