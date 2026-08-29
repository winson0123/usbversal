"""Tests for the TUI Progress and Done screens (steps 4-5)."""

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.containers import Center, CenterMiddle
from textual.screen import Screen
from textual.widgets import ProgressBar, RichLog, Static

from app.services.sync_progress import SyncProgress
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


@pytest.mark.asyncio
async def test_backup_samples_drive_the_bar_and_do_not_log_files() -> None:
    """Backup is one bar with an ETA, not a per-file log. Sync starts a new bar."""

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
                screen._update_progress(SyncProgress("backup", 0, 100, ""))
                screen._update_progress(SyncProgress("backup", 40, 100, ""))
                status = str(screen.query_one("#sync-status", Static).render())
                bar = screen.query_one(ProgressBar)
                assert "Backing up" in status
                assert "40%" in status
                assert bar.total == 100
                assert bar.progress == 40
                assert len(screen.query_one(RichLog).lines) == 0
                assert "empty" in screen.query_one(RichLog).classes
                assert str(screen.query_one("#sync-playlist", Static).render()) == ""

                screen._update_progress(SyncProgress("analysis", 1, 3, "Contents/a.mp3"))
                bar = screen.query_one(ProgressBar)
                assert bar.total == 3
                assert bar.progress == 1
                assert "empty" not in screen.query_one(RichLog).classes
            finally:
                hold.set()


@pytest.mark.asyncio
async def test_progress_shows_the_playlist_and_centers_the_bar() -> None:
    """The visible Bar strip is wide and centered; the playlist shows its own x/x."""

    hold = threading.Event()

    def _held_sync(library, playlist_ids, *, dry_run=False, backup_root=None, on_progress=None):
        hold.wait(timeout=5)
        return _fake_report()

    with patch("app.tui.screens.progress.sync_playlists", _held_sync):
        app = _Harness(library=object(), playlist_ids=[1])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            try:
                assert isinstance(screen, ProgressScreen)
                bar = screen.query_one("#sync-progress")
                strip = bar.query_one("Bar")
                row = screen.query_one("#sync-bar-row")
                assert isinstance(bar.parent, Center)
                assert isinstance(bar.parent.parent, CenterMiddle)
                assert row.size.width == screen.size.width
                strip_mid = strip.region.x + strip.region.width // 2
                assert abs(strip_mid - screen.size.width // 2) <= 1
                assert strip.region.width >= screen.size.width * 50 // 100
                log = screen.query_one(RichLog)
                assert "empty" in log.classes
                assert not isinstance(log.parent, CenterMiddle)
                screen._update_progress(
                    SyncProgress(
                        "analysis",
                        2,
                        5,
                        "Contents/x.mp3",
                        playlist="House",
                        playlist_done=2,
                        playlist_total=10,
                    )
                )
                label = str(screen.query_one("#sync-playlist", Static).render())
                assert "House" in label
                assert "2/10" in label
                assert isinstance(screen.query_one("#sync-progress").parent.parent, CenterMiddle)
                assert not isinstance(screen.query_one(RichLog).parent, CenterMiddle)
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
            assert "a.mp3" in text
            assert "Contents/" not in text
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
            assert "a.mp3" in text
            assert "Contents/" not in text
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


def test_display_title_is_the_filename() -> None:
    """The log shows the file title, not the directory path."""
    from app.services.sync_progress import display_title

    assert display_title("/Contents/Artist/Song.mp3") == "Song.mp3"
    assert display_title("") == ""
