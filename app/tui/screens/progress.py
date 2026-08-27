"""Progress and Done screens: steps 4-5 of the target flow.

Progress runs ``sync_playlists`` as a background worker and renders its
per-track progress; Done shows what happened. This is the first place
``sync_playlists`` becomes reachable from the TUI at all.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, ProgressBar, RichLog, Static

from app.jobs.progress_rate import ProgressRateTracker, format_duration
from app.services.library import UsbLibrary
from app.services.sync_service import SyncReport, sync_playlists

_STATUS_ID = "sync-status"
_BAR_ID = "sync-progress"
_LOG_ID = "sync-log"
_SUMMARY_ID = "done-summary"


class ProgressScreen(Screen):
    """Step 4: run the sync for the selected playlists and show progress."""

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

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Starting sync…", id=_STATUS_ID)
            yield ProgressBar(id=_BAR_ID, show_eta=False)
            yield RichLog(id=_LOG_ID, max_lines=500, auto_scroll=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run(), exclusive=True)

    async def _run(self) -> None:
        try:
            # sync_playlists reads through library.rekordbox, which must stay
            # on the app's one dedicated thread -- see UsbversalApp.run_rekordbox.
            report = await self.app.run_rekordbox(
                sync_playlists,
                self.library,
                self._playlist_ids,
                on_progress=self._report_progress,
            )
        except Exception as exc:  # reported on the Done screen, not raised
            self.query_one(RichLog).write(Text(f"Sync failed: {exc}", style="red"))
            self.app.switch_screen(DoneScreen(error=str(exc)))
            return
        self.app.switch_screen(DoneScreen(report=report))

    def _report_progress(self, done: int, total: int, track: str, error: str | None) -> None:
        """Called from the sync's worker thread; marshal back to the UI thread."""
        self.app.call_from_thread(self._update_progress, done, total, track, error)

    def _update_progress(self, done: int, total: int, track: str, error: str | None) -> None:
        self.query_one(ProgressBar).update(total=total, progress=done)
        estimate = self._tracker.observe(current=done, total=total, at=time.monotonic())
        message = f"Writing analysis: {done}/{total}"
        if estimate.rate_per_second is not None:
            message += f" ({estimate.rate_per_second:.1f}/s"
            if estimate.eta_seconds is not None:
                message += f", eta {format_duration(estimate.eta_seconds)}"
            message += ")"
        self.query_one(f"#{_STATUS_ID}", Static).update(message)

        log = self.query_one(RichLog)
        if error is None:
            log.write(Text(f"[{done}/{total}] {track}", style="green"))
        else:
            log.write(Text(f"[{done}/{total}] {track}: {error}", style="red"))


class DoneScreen(Screen):
    """Step 5: completion summary. Enter returns to Library, Esc exits."""

    BINDINGS = [
        Binding("enter", "return_to_library", "Back to Library", show=True),
        Binding("escape", "app.quit", "Quit", show=True),
    ]

    def __init__(self, *, report: SyncReport | None = None, error: str | None = None) -> None:
        """
        Args:
            report: The completed sync's report, when it succeeded.
            error: The failure message, when it did not.
        """
        super().__init__()
        self._report = report
        self._error = error

    def compose(self) -> ComposeResult:
        yield Static(self._summary(), id=_SUMMARY_ID)
        yield Footer()

    def _summary(self) -> Text:
        if self._error is not None:
            # Text(), not markup -- self._error is an arbitrary exception
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
