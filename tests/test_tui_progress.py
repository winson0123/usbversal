"""Tests for the TUI Progress and Done screens (steps 4-5)."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import RichLog, Static

from app.services.sync_progress import SyncProgress
from app.services.sync_service import SyncReport
from app.storage.host import host_volume_dir
from app.tui.app import RekordboxThreadMixin
from app.tui.screens.progress import DoneScreen, ProgressScreen


def _fake_report(**overrides) -> SyncReport:
    fields = {
        "mount": Path("/mnt/usb"),
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

    def _sync(library, playlist_ids, *, on_progress=None):
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
            summary = app.screen.query_one("#done-summary", Static).render()
            assert "3 new record" in str(summary)
            assert "Grids: 2" in str(summary)
            assert any(span.style == "green" for span in summary.spans)


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
            summary = app.screen.query_one("#done-summary", Static).render()
            assert "Sync failed" in str(summary)
            assert "stick unplugged" in str(summary)
            assert any(span.style == "red" for span in summary.spans)


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

            summary = app.screen.query_one("#done-summary", Static).render()
            assert "1 track" in str(summary)
            assert "could not be analysed" in str(summary)
            assert any(span.style == "red" for span in summary.spans)
            log = app.screen.query_one("#done-errors", RichLog)
            text = "".join(segment.text for line in log.lines for segment in line)
            assert "a.mp3" in text
            assert "Contents/a.mp3" in text
            assert "bad grid" in text
            error_log = host_volume_dir(Path("/mnt/usb")) / "error.log"
            assert error_log.is_file()
            assert "a.mp3" in error_log.read_text(encoding="utf-8")


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


def test_done_screen_has_no_escape_quit_binding() -> None:
    """Quit on Done is ^Q only; Esc must not appear as a footer action."""
    keys = {binding.key for binding in DoneScreen.BINDINGS}
    assert "escape" not in keys
    assert "enter" in keys


def _log_line_styles(log: RichLog, index: int) -> tuple[str, list]:
    """Read back one written RichLog line as (plain text, segment styles)."""
    strip = log.lines[index]
    text = "".join(segment.text for segment in strip)
    styles = [segment.style for segment in strip]
    return text, styles


@pytest.mark.asyncio
async def test_progress_log_shows_a_red_line_for_a_failed_track() -> None:
    """A track whose analysis failed gets a red line naming the error,
    instead of silently vanishing into the done/total counter."""

    def _slow_sync(library, playlist_ids, *, on_progress=None):
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
            assert "a.mp3" in text
            assert "Contents/" not in text
            assert "bad beatgrid" in text
            assert any(style is not None and style.color.name == "red" for style in styles)
