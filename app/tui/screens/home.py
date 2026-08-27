"""Home screen: steps 1 (Waiting) and 2 (Detect) of the target flow.

Watches for a mount appearing and checks whatever appears for Rekordbox
export validity, entirely through the cheap primitives TASK-202/203 built --
no ``LibraryDiscovery`` walk runs on this screen.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, CenterMiddle
from textual.screen import Screen
from textual.widgets import Input, Static

from app.services.bootstrap_service import bootstrap_serato_library
from app.services.errors import DatabaseNotFoundError, UnsupportedDatabaseError
from app.services.library import (
    MountChangeKind,
    MountWatcher,
    UsbLibrary,
    open_library,
    probe_mount,
)
from app.tui.screens.library import LibraryScreen

_NONE_FOUND = "Did not detect a valid DJ USB"
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


def _complete_path(partial: str) -> str | None:
    """
    Shell-style Tab completion for a filesystem path: complete to the
    longest common prefix among matching entries, or nothing if that
    prefix is no longer than what's already typed.

    Returns:
        The completed path, or None if there is nothing to add.
    """
    path = Path(partial)
    if partial == "" or partial.endswith("/"):
        directory, prefix = (path if partial else Path(".")), ""
    else:
        directory, prefix = path.parent, path.name

    try:
        matches = sorted(
            entry.name for entry in directory.iterdir() if entry.name.startswith(prefix)
        )
    except OSError:
        return None
    if not matches:
        return None

    common = os.path.commonprefix(matches)
    if common == prefix and len(matches) != 1:
        return None

    completed = directory / common if str(directory) != "." else Path(common)
    if len(matches) == 1 and (directory / matches[0]).is_dir():
        return f"{completed}/"
    return str(completed)


class _PathInput(Input):
    """Path entry field with shell-style Tab completion.

    A plain (non-priority) binding is enough to win over Screen's own
    default ``tab`` -> ``app.focus_next`` binding: Textual checks a
    focused widget's own bindings before walking up to its ancestors, so
    this only needs to out-rank Screen when *this* widget has focus.
    """

    BINDINGS = [Binding("tab", "complete", "Complete path", show=False)]

    def action_complete(self) -> None:
        completed = _complete_path(self.value)
        if completed is not None:
            self.value = completed
            self.cursor_position = len(completed)


class HomeScreen(Screen):
    """
    Poll for a mount to appear, check it, then push the Library screen.

    A mount is "valid" when it has a supported Rekordbox export
    (``MountProbe.is_dj_usb and MountProbe.is_supported``). Serato need not
    exist yet -- ``bootstrap_serato_library`` creates an empty one first when
    it doesn't, so a plain rekordbox stick is never a dead end.

    Nothing plugged in at all still gets a way out: once ``SCAN_TIMEOUT_S``
    passes with no mount ever appearing, this is treated exactly like a
    mount that was found and rejected -- the manual-path input appears,
    rather than leaving a bare spinner running forever with no way to act.
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
        self._seen_invalid = False
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
                yield _PathInput(
                    placeholder="Press enter to retry auto-scan, or enter an absolute path",
                    id=_INPUT_ID,
                )

    def on_mount(self) -> None:
        self._show_spinner()
        self.set_interval(self.POLL_INTERVAL_S, self.poll_mounts)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        value = event.value.strip()
        if not value:
            # An explicit retry gets a fresh look, not an instant re-print
            # of the same failure: _seen_invalid stays true forever once
            # set (that's what stops hopeful auto-checking after a real
            # rejection), so without resetting it here, poll_mounts()
            # would just show the identical error again with nothing on
            # screen ever changing -- indistinguishable from Enter having
            # done nothing at all.
            self._seen_invalid = False
            self._searching_since = time.monotonic()
            self.poll_mounts()
            return
        self._show_spinner()
        self.run_worker(self._open(Path(value)), exclusive=True)

    def poll_mounts(self) -> None:
        """One watch tick: check for new mounts and probe any that appeared."""
        if self.library is not None:
            return

        for change in self._watcher.poll():
            if change.kind is not MountChangeKind.APPEARED:
                continue
            probe = probe_mount(change.path)
            if probe is not None and probe.is_dj_usb and probe.is_supported:
                self._show_spinner()
                self.run_worker(self._open(change.path), exclusive=True)
                return
            self._seen_invalid = True

        timed_out = time.monotonic() - self._searching_since >= self.SCAN_TIMEOUT_S
        if not self._seen_invalid and timed_out:
            # Nothing has ever appeared to reject -- there's simply nothing
            # to find. Give up on quiet auto-scanning the same way an
            # actual rejection would, rather than spinning forever with no
            # way for the user to act.
            self._seen_invalid = True

        if self._seen_invalid:
            self._show_error(_NONE_FOUND)
        else:
            self._show_spinner()

    async def _open(self, mount: Path) -> None:
        """Bootstrap a Serato library if needed, open it, then hand off."""
        self.query_one(_PathInput).disabled = True
        try:
            await asyncio.to_thread(bootstrap_serato_library, mount)
            # open_library, and every later touch of library.rekordbox, must
            # run on the app's one dedicated thread -- see UsbversalApp.run_rekordbox.
            library = await self.app.run_rekordbox(open_library, mount)
            await self.app.run_rekordbox(lambda: len(library.rekordbox.list_playlists()))
        except (OSError, DatabaseNotFoundError, UnsupportedDatabaseError) as exc:
            self._seen_invalid = True
            self._show_error(f"{_NONE_FOUND} ({exc})")
            return
        self.library = library
        self.app.push_screen(LibraryScreen(library))

    def _show_spinner(self) -> None:
        self.query_one(f"#{_SPINNER_ID}", _Spinner).display = True
        status = self.query_one(f"#{_STATUS_ID}", Static)
        status.display = True
        # Dim, not red -- this is routine "still looking" information, not
        # a problem.
        status.update(Text(_SCANNING, style="dim"))
        self._hide_input()

    def _show_error(self, message: str) -> None:
        self.query_one(f"#{_SPINNER_ID}", _Spinner).display = False
        status = self.query_one(f"#{_STATUS_ID}", Static)
        status.display = True
        # Text(), not markup -- message can embed an arbitrary exception
        # string, which could itself contain "[...]" that markup parsing
        # would misread as a tag.
        status.update(Text(message, style="red"))
        self._reveal_input()

    def _hide_input(self) -> None:
        """Manual entry only makes sense once auto-scanning has actually
        failed at something, not while it's still quietly searching --
        disabled, not just hidden, so a hidden field can't silently eat
        keystrokes (Textual still auto-focuses a hidden-but-enabled widget
        when it's the only focusable one on screen)."""
        path_input = self.query_one(_PathInput)
        path_input.display = False
        path_input.disabled = True

    def _reveal_input(self) -> None:
        """Show and focus the input, but only on the transition into this
        state -- not on every later poll tick that re-confirms the same
        failure, which would otherwise steal focus back on a 1s timer."""
        path_input = self.query_one(_PathInput)
        if path_input.display:
            return
        path_input.display = True
        path_input.disabled = False
        path_input.focus()
