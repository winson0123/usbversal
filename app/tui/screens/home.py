"""Home screen: steps 1 (Waiting) and 2 (Detect) of the target flow.

Watches for a mount appearing and checks whatever appears for Rekordbox
export validity, entirely through the cheap primitives TASK-202/203 built --
no ``LibraryDiscovery`` walk runs on this screen.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Center, CenterMiddle
from textual.screen import Screen
from textual.widgets import Static

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
_BANNER_ID = "banner"
_SPINNER_ID = "spinner"
_STATUS_ID = "status"
_SPINNER_INTERVAL_S = 0.1
_SPINNER_FRAMES = ("◐", "◓", "◑", "◒")

_BANNER = """\
░█░█░█▀▀░█▀▄░█░█░█▀▀░█▀▄░█▀▀░█▀█░█░░
░█░█░▀▀█░█▀▄░▀▄▀░█▀▀░█▀▄░▀▀█░█▀█░█░░
░▀▀▀░▀▀▀░▀▀░░░▀░░▀▀▀░▀░▀░▀▀▀░▀░▀░▀▀▀"""


class _Spinner(Static):
    """A single spinning glyph. No colour of its own -- whatever the
    terminal's default foreground is, is what this renders in."""

    def on_mount(self) -> None:
        self._frame = 0
        self.update(_SPINNER_FRAMES[0])
        self.set_interval(_SPINNER_INTERVAL_S, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(_SPINNER_FRAMES)
        self.update(_SPINNER_FRAMES[self._frame])


class HomeScreen(Screen):
    """
    Poll for a mount to appear, check it, then push the Library screen.

    A mount is "valid" when it has a supported Rekordbox export
    (``MountProbe.is_dj_usb and MountProbe.is_supported``). Serato need not
    exist yet -- ``bootstrap_serato_library`` creates an empty one first when
    it doesn't, so a plain rekordbox stick is never a dead end.
    """

    DEFAULT_CSS = """
    HomeScreen #banner, HomeScreen #spinner, HomeScreen #status {
        width: auto;
        text-align: center;
    }
    HomeScreen #spinner, HomeScreen #status {
        margin-top: 1;
    }
    """

    POLL_INTERVAL_S = 1.0

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
        self.library: UsbLibrary | None = None

    def compose(self) -> ComposeResult:
        with CenterMiddle():
            with Center():
                yield Static(_BANNER, id=_BANNER_ID)
            with Center():
                yield _Spinner(id=_SPINNER_ID)
            with Center():
                yield Static("", id=_STATUS_ID)

    def on_mount(self) -> None:
        self.query_one(f"#{_STATUS_ID}", Static).display = False
        self.set_interval(self.POLL_INTERVAL_S, self.poll_mounts)

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

        if self._seen_invalid:
            self._show_error(_NONE_FOUND)
        else:
            self._show_spinner()

    async def _open(self, mount: Path) -> None:
        """Bootstrap a Serato library if needed, open it, then hand off."""
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
        self.query_one(f"#{_STATUS_ID}", Static).display = False

    def _show_error(self, message: str) -> None:
        self.query_one(f"#{_SPINNER_ID}", _Spinner).display = False
        status = self.query_one(f"#{_STATUS_ID}", Static)
        status.display = True
        status.update(f"[red]{message}[/red]")
