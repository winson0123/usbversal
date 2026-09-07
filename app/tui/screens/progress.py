"""Progress and Done screens.

Progress runs ``sync_playlists`` as a background worker and renders its
per-track progress; Done shows what happened.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, CenterMiddle
from textual.screen import Screen
from textual.widgets import Footer, ProgressBar, RichLog, Static

from app.services.cancellation import OperationCancelled
from app.services.library import UsbLibrary
from app.services.sync_errors import (
    failures_from_report,
    format_failure_lines,
    write_error_log,
)
from app.services.sync_progress import SyncProgress, display_title
from app.services.sync_service import SyncReport, sync_playlists
from app.tui.progress_rate import ProgressRateTracker, format_duration

_PHASE_STATUS = {
    "index": "Indexing tracks",
    "analysis": "Writing analysis",
    "crates": "Writing crates",
}

_STATUS_ID = "sync-status"
_BAR_ID = "sync-progress"
_PLAYLIST_ID = "sync-playlist"
_LOG_ID = "sync-log"
_SUMMARY_ID = "done-summary"
_ERRORS_ID = "done-errors"


class ProgressScreen(Screen):
    """Step 4: run the sync for the selected playlists and show progress."""

    DEFAULT_CSS = """
    ProgressScreen CenterMiddle {
        width: 100%;
    }
    ProgressScreen #sync-status, ProgressScreen #sync-playlist {
        width: auto;
        text-align: center;
    }
    ProgressScreen #sync-bar-row {
        width: 100%;
    }
    ProgressScreen #sync-progress {
        width: 60%;
        height: auto;
        margin: 1 0;
    }
    ProgressScreen #sync-progress Bar {
        width: 1fr;
    }
    ProgressScreen #sync-log {
        dock: bottom;
        width: 100%;
        height: 12;
        margin: 0 2 1 2;
    }
    ProgressScreen #sync-log.empty, ProgressScreen #sync-playlist.empty {
        display: none;
    }
    """

    def __init__(self, library: UsbLibrary, playlist_ids: Sequence[int]) -> None:
        """
        Args:
            library: Opened session handle.
            playlist_ids: Rekordbox playlist ids to sync, in selection order.
        """
        super().__init__()
        self.library = library
        self._playlist_ids = list(playlist_ids)
        self._tracker = ProgressRateTracker()
        self._phase: str | None = None

    def compose(self) -> ComposeResult:
        """Keep status, bar, and playlist mid-screen; dock the log below."""
        with CenterMiddle():
            with Center():
                yield Static("Starting…", id=_STATUS_ID)
            with Center(id="sync-bar-row"):
                yield ProgressBar(id=_BAR_ID, show_eta=False, show_percentage=False)
            with Center():
                yield Static("", id=_PLAYLIST_ID, classes="empty")
        yield RichLog(id=_LOG_ID, max_lines=500, auto_scroll=True, wrap=True, classes="empty")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run(), exclusive=True)

    async def _run(self) -> None:
        try:
            # sync_playlists reads through library.rekordbox, which must stay
            # on the app's one dedicated thread. See UsbversalApp.run_rekordbox.
            report = await self.app.run_rekordbox(
                sync_playlists,
                self.library,
                self._playlist_ids,
                on_progress=self._report_progress,
            )
        except OperationCancelled:
            # Quit owns teardown; do not push Done over a dying UI.
            return
        except Exception as exc:  # reported on the Done screen, not raised
            log = self.query_one(RichLog)
            log.remove_class("empty")
            log.write(Text(f"Sync failed: {exc}", style="red"))
            self.app.switch_screen(DoneScreen(error=str(exc)))
            return
        self.app.switch_screen(DoneScreen(report=report))

    def _report_progress(self, sample: SyncProgress) -> None:
        """Called from the sync's worker thread; marshal back to the UI thread."""
        self.app.call_from_thread(self._update_progress, sample)

    def _update_progress(self, sample: SyncProgress) -> None:
        """
        Apply one sync sample to the bar, status line, and log.

        Args:
            sample: Phase, counts, item path or crate name, and optional error.
        """
        if sample.phase != self._phase:
            self._tracker = ProgressRateTracker()
            self._phase = sample.phase
        self.query_one(ProgressBar).update(total=sample.total, progress=sample.done)
        estimate = self._tracker.observe(
            current=sample.done, total=sample.total, at=time.monotonic()
        )
        label = _PHASE_STATUS.get(sample.phase, sample.phase)
        message = f"{label}: {sample.done}/{sample.total}"
        if estimate.eta_seconds is not None:
            message += f" (eta {format_duration(estimate.eta_seconds)})"
        elif estimate.rate_per_second is not None:
            message += f" ({estimate.rate_per_second:.1f}/s)"
        self.query_one(f"#{_STATUS_ID}", Static).update(message)

        playlist = self.query_one(f"#{_PLAYLIST_ID}", Static)
        if sample.playlist and sample.playlist_total:
            playlist.remove_class("empty")
            playlist.update(f"{sample.playlist}  {sample.playlist_done}/{sample.playlist_total}")
        else:
            playlist.add_class("empty")
            playlist.update("")

        log = self.query_one(RichLog)
        log.remove_class("empty")
        line = f"[{sample.done}/{sample.total}] {display_title(sample.item)}"
        if sample.error is None:
            log.write(Text(line, style="green"))
        else:
            log.write(Text(f"{line}: {sample.error}", style="red"))


class DoneScreen(Screen):
    """Step 5: completion summary. Enter returns to Library."""

    BINDINGS = [
        Binding("enter", "return_to_library", "Back to Library", show=True),
    ]

    DEFAULT_CSS = """
    DoneScreen CenterMiddle {
        width: 100%;
    }
    DoneScreen #done-summary {
        width: auto;
        height: auto;
        text-align: center;
        padding: 1 2;
    }
    DoneScreen #done-errors {
        dock: bottom;
        width: 100%;
        height: 12;
        margin: 0 2 1 2;
    }
    """

    def __init__(self, *, report: SyncReport | None = None, error: str | None = None) -> None:
        """
        Args:
            report: The completed sync's report, when it succeeded.
            error: The failure message, when it did not.
        """
        super().__init__()
        self._report = report
        self._error = error
        self._failures = failures_from_report(report) if report is not None else ()

    def compose(self) -> ComposeResult:
        """Keep the summary mid-screen; dock failures below when present."""
        with CenterMiddle():
            with Center():
                yield Static(self._summary(), id=_SUMMARY_ID)
        if self._failures:
            yield RichLog(id=_ERRORS_ID, max_lines=500, auto_scroll=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        """Fill the error list and write the host error.log."""
        if not self._failures:
            return
        log = self.query_one(f"#{_ERRORS_ID}", RichLog)
        for failure in self._failures:
            log.write(Text(format_failure_lines(failure), style="red"))
        if self._report is not None:
            write_error_log(self._report.mount, self._failures)

    def _summary(self) -> Text:
        if self._error is not None:
            # Text(), not markup. self._error is an arbitrary exception
            # message and could itself contain "[...]", which markup
            # parsing would misread as a tag.
            return Text(f"Sync failed: {self._error}", style="red")
        report = self._report
        assert report is not None
        lines = [
            f"Synced {report.crates_written} playlist(s), {report.records_added} new record(s).",
            f"Grids: {report.grids_written}  Cues: {report.cues_written}  "
            f"Index rows: {report.index_rows_updated}",
        ]
        style = "green"
        if report.analysis_errors:
            lines.append(f"{len(report.analysis_errors)} track(s) could not be analysed.")
            style = "red"
        return Text("\n".join(lines), style=style)

    def action_return_to_library(self) -> None:
        self.app.pop_screen()
