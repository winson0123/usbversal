"""Home screen: steps 1 (Waiting) and 2 (Detect) of the target flow.

Watches for a mount appearing and checks whatever appears for Rekordbox
export validity, entirely through the cheap primitives TASK-202/203 built --
no ``LibraryDiscovery`` walk runs on this screen.
"""

from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, CenterMiddle
from textual.screen import Screen
from textual.widgets import Input, Static

from app.services.errors import DatabaseNotFoundError, UnsupportedDatabaseError
from app.services.library import (
    MountChangeKind,
    MountWatcher,
    UsbLibrary,
    prepare_library,
    probe_mount,
)
from app.tui.screens.library import LibraryScreen
from app.tui.widgets.path_input import PathInput

_NONE_FOUND = "Did not detect a valid DJ USB."
_RETRY_HINT = "Press 'Enter' to retry auto-scan…"
_SCANNING = "Automatically detecting for a DJ USB…"
_BANNER_ID = "banner"
_SPINNER_ID = "spinner"
_STATUS_ID = "status"
_INPUT_ID = "path-input"
_SPINNER_INTERVAL_S = 0.1
# A bright point sweeping left to right over a dotted bar, one step of
# fade-out trailing behind it -- e.g. "[·•●·]" -- rather than a single
# pulsing glyph, reads more like an active scan in progress. The resting
# fill is the same smallest dot the trail fades into, not blank space, so
# the bar never looks like it has empty gaps in it.
_BAR_WIDTH = 4
_SPINNER_FRAME_COUNT = _BAR_WIDTH + 2


def _scan_bar_frame(head: int) -> str:
    """One frame of the sweeping scan bar, with the bright point at `head`."""
    cells = []
    for i in range(_BAR_WIDTH):
        dist = head - i
        if dist == 0:
            cells.append("●")
        elif dist == 1:
            cells.append("•")
        else:
            cells.append("·")
    return "[" + "".join(cells) + "]"


_BANNER = """\
░█░█░█▀▀░█▀▄░█░█░█▀▀░█▀▄░█▀▀░█▀█░█░░
░█░█░▀▀█░█▀▄░▀▄▀░█▀▀░█▀▄░▀▀█░█▀█░█░░
░▀▀▀░▀▀▀░▀▀░░░▀░░▀▀▀░▀░▀░▀▀▀░▀░▀░▀▀▀"""


class _Spinner(Static):
    """A sweeping scan bar. No colour of its own -- whatever the terminal's
    default foreground is, is what this renders in."""

    def on_mount(self) -> None:
        self._frame = 0
        self.update(_scan_bar_frame(self._frame))
        self.set_interval(_SPINNER_INTERVAL_S, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % _SPINNER_FRAME_COUNT
        self.update(_scan_bar_frame(self._frame))


class HomePhase(StrEnum):
    """Visible Home screen phase. Polling only transitions; render follows."""

    SEARCHING = "searching"
    FAILED = "failed"
    OPENING = "opening"
    READY = "ready"


class HomeScreen(Screen):
    """
    Poll for a mount to appear, check it, then push the Library screen.

    A mount is "valid" when it has a supported Rekordbox export
    (``MountProbe.is_dj_usb and MountProbe.is_supported``). Serato need not
    exist yet -- ``prepare_library`` creates an empty one first when
    it doesn't, so a plain rekordbox stick is never a dead end.

    ``SEARCHING`` lasts until a mount is accepted, rejected, or
    ``SCAN_TIMEOUT_S`` passes with nothing to find. ``FAILED`` shows the
    manual-path input so the user can retry or type a path.
    """

    DEFAULT_CSS = """
    HomeScreen #banner, HomeScreen #spinner, HomeScreen #status {
        width: auto;
        text-align: center;
    }
    HomeScreen #spinner, HomeScreen #status {
        margin-top: 1;
    }
    HomeScreen #path-input {
        width: 46;
        margin-top: 1;
    }
    """

    POLL_INTERVAL_S = 1.0
    SCAN_TIMEOUT_S = 3.0

    def __init__(self, watcher: MountWatcher | None = None) -> None:
        """
        Args:
            watcher: Mount watcher to poll; defaults to a fresh one. Injectable
                so tests can drive it with a fake scanner instead of the real
                filesystem.
        """
        super().__init__()
        self._watcher = watcher or MountWatcher()
        self._phase = HomePhase.SEARCHING
        self._error = _NONE_FOUND
        self._searching_since = time.monotonic()
        self.library: UsbLibrary | None = None

    def compose(self) -> ComposeResult:
        with CenterMiddle():
            with Center():
                yield Static(_BANNER, id=_BANNER_ID)
            with Center():
                yield _Spinner(id=_SPINNER_ID)
            with Center():
                yield Static("", id=_STATUS_ID)
            with Center():
                yield PathInput(
                    placeholder="or enter an absolute path…",
                    id=_INPUT_ID,
                )

    def on_mount(self) -> None:
        self._show_phase()
        self.set_interval(self.POLL_INTERVAL_S, self.poll_mounts)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        value = event.value.strip()
        if not value:
            self._enter(HomePhase.SEARCHING)
            self.poll_mounts()
            return
        self._enter(HomePhase.OPENING)
        self.run_worker(self._open(Path(value)), exclusive=True)

    def poll_mounts(self) -> None:
        """One watch tick: check for new mounts and probe any that appeared."""
        if self._phase in (HomePhase.OPENING, HomePhase.READY):
            return

        for change in self._watcher.poll():
            if change.kind is not MountChangeKind.APPEARED:
                continue
            probe = probe_mount(change.path)
            if probe is not None and probe.is_dj_usb and probe.is_supported:
                self._enter(HomePhase.OPENING)
                self.run_worker(self._open(change.path), exclusive=True)
                return
            self._enter(HomePhase.FAILED)

        if self._phase is HomePhase.SEARCHING and (
            time.monotonic() - self._searching_since >= self.SCAN_TIMEOUT_S
        ):
            self._enter(HomePhase.FAILED)

    async def _open(self, mount: Path) -> None:
        """Prepare the session handle, then hand off to the Library screen."""
        try:
            # prepare_library opens Rekordbox, so it must stay on the app's
            # one dedicated thread -- see UsbversalApp.run_rekordbox.
            library = await self.app.run_rekordbox(prepare_library, mount)
        except (OSError, DatabaseNotFoundError, UnsupportedDatabaseError) as exc:
            self._enter(HomePhase.FAILED, f"{_NONE_FOUND} ({exc})")
            return
        self.library = library
        self._enter(HomePhase.READY)
        self.app.push_screen(LibraryScreen(library))

    def _enter(self, phase: HomePhase, error: str = _NONE_FOUND) -> None:
        """
        Move to `phase` and render only when the visible state changes.

        Args:
            phase: Next Home phase.
            error: Status text used when entering ``FAILED``.
        """
        if phase is HomePhase.SEARCHING and self._phase is not HomePhase.SEARCHING:
            self._searching_since = time.monotonic()
        if phase is self._phase and (phase is not HomePhase.FAILED or error == self._error):
            return
        self._phase = phase
        self._error = error
        if phase is not HomePhase.READY:
            self._show_phase()

    def _show_phase(self) -> None:
        """Apply spinner, status, and path-input widgets from ``self._phase``."""
        spinner = self.query_one(f"#{_SPINNER_ID}", _Spinner)
        status = self.query_one(f"#{_STATUS_ID}", Static)
        path_input = self.query_one(PathInput)

        if self._phase is HomePhase.FAILED:
            spinner.display = False
            status.display = True
            # Text(), not markup -- the message can embed an arbitrary
            # exception string, which could itself contain "[...]" that
            # markup parsing would misread as a tag. The retry hint lives
            # here, not in the input's placeholder: the status line has
            # the whole screen's width, while the input box is fixed and
            # narrow.
            status.update(Text(f"{self._error} {_RETRY_HINT}", style="red"))
            path_input.display = True
            path_input.disabled = False
            path_input.focus()
            return

        spinner.display = True
        status.display = True
        # Dim, not red -- this is routine "still looking" information.
        status.update(Text(_SCANNING, style="dim"))
        # Disabled, not just hidden: Textual still auto-focuses a
        # hidden-but-enabled widget when it is the only focusable one.
        path_input.display = False
        path_input.disabled = True
