"""Tests for the TUI Progress and Done screens (steps 4-5)."""

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import ProgressBar, RichLog, Static

from app.services.sync_service import SyncProgress, SyncReport
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


def _fake_sync(
    *,
    calls=(
        SyncProgress("analysis", 1, 2, "Contents/a.mp3"),
        SyncProgress("analysis", 2, 2, "Contents/b.mp3"),
    ),
    report=None,
    error=None,
    delay_s=0.0,
):
    """Build a stand-in for sync_playlists that drives on_progress synchronously."""

    def _sync(library, playlist_ids, *, dry_run=False, backup_root=None, on_progress=None):
        if on_progress is not None:
            for sample in calls:
                if delay_s:
                    time.sleep(delay_s)
                on_progress(sample)
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

    The worker is held until after the assertions so ``pilot.pause()`` cannot
    race into Done before the bar is inspected.
    """

    hold = threading.Event()

    def _held_sync(library, playlist_ids, *, dry_run=False, backup_root=None, on_progress=None):
        hold.wait(timeout=5)
        return _fake_report()

    with patch("app.tui.screens.progress.sync_playlists", _held_sync):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            try:
                assert isinstance(screen, ProgressScreen)

                screen._update_progress(SyncProgress("analysis", 1, 4, "Contents/a.mp3"))
                screen._update_progress(SyncProgress("analysis", 3, 4, "Contents/b.mp3"))

                bar = screen.query_one(ProgressBar)
                assert bar.total == 4
                assert bar.progress == 3
            finally:
                hold.set()


def _log_line_styles(log: RichLog, index: int) -> tuple[str, list]:
    """Read back one written RichLog line as (plain text, segment styles)."""
    strip = log.lines[index]
    text = "".join(segment.text for segment in strip)
    styles = [segment.style for segment in strip]
    return text, styles


@pytest.mark.asyncio
async def test_progress_log_shows_a_green_line_per_successful_track() -> None:
    """Each track that analyses cleanly gets its own green log line -- the
    user asked to actually see what's happening, not just a bare counter."""

    def _slow_sync(library, playlist_ids, *, dry_run=False, backup_root=None, on_progress=None):
        time.sleep(1.0)
        return _fake_report()

    with patch("app.tui.screens.progress.sync_playlists", _slow_sync):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._update_progress(SyncProgress("analysis", 1, 2, "Contents/a.mp3"))
            await pilot.pause()

            log = screen.query_one(RichLog)
            text, styles = _log_line_styles(log, 0)
            assert "Contents/a.mp3" in text
            assert any(style is not None and style.color.name == "green" for style in styles)


@pytest.mark.asyncio
async def test_progress_log_shows_a_red_line_for_a_failed_track() -> None:
    """A track whose analysis failed gets a red line naming the error,
    instead of silently vanishing into the done/total counter."""

    def _slow_sync(library, playlist_ids, *, dry_run=False, backup_root=None, on_progress=None):
        time.sleep(1.0)
        return _fake_report()

    with patch("app.tui.screens.progress.sync_playlists", _slow_sync):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._update_progress(
                SyncProgress("analysis", 1, 2, "Contents/a.mp3", "bad beatgrid")
            )
            await pilot.pause()

            log = screen.query_one(RichLog)
            text, styles = _log_line_styles(log, 0)
            assert "Contents/a.mp3" in text
            assert "bad beatgrid" in text
            assert any(style is not None and style.color.name == "red" for style in styles)


@pytest.mark.asyncio
async def test_done_summary_is_green_on_a_clean_sync() -> None:
    """A sync with no analysis errors reads as unambiguously good news."""
    with patch("app.tui.screens.progress.sync_playlists", _fake_sync(report=_fake_report())):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            content = app.screen.query_one("#done-summary", Static).render()
            assert any(span.style == "green" for span in content.spans)


@pytest.mark.asyncio
async def test_done_summary_is_red_when_analysis_errors_present() -> None:
    """A partially-failed sync reads as a problem, not routine success."""
    report = _fake_report(analysis_errors=("Contents/a.mp3: bad grid",))
    with patch("app.tui.screens.progress.sync_playlists", _fake_sync(report=report)):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            content = app.screen.query_one("#done-summary", Static).render()
            assert any(span.style == "red" for span in content.spans)


@pytest.mark.asyncio
async def test_done_summary_is_red_on_a_hard_failure() -> None:
    """A sync that raised outright is exactly as much of a problem."""
    with patch(
        "app.tui.screens.progress.sync_playlists",
        _fake_sync(error=RuntimeError("stick unplugged")),
    ):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            content = app.screen.query_one("#done-summary", Static).render()
            assert any(span.style == "red" for span in content.spans)

            await app.workers.wait_for_complete()
