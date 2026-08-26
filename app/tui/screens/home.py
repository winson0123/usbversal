"""Home screen: steps 1 (Waiting) and 2 (Detect) of the target flow.

Watches for a mount appearing and checks whatever appears for Rekordbox
export validity, entirely through the cheap primitives TASK-202/203 built --
no ``LibraryDiscovery`` walk runs on this screen.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Static

from app.services.errors import DatabaseNotFoundError, UnsupportedDatabaseError
from app.services.library import (
    MountChangeKind,
    MountWatcher,
    UsbLibrary,
    open_library,
    probe_mount,
)
from app.tui.screens.library import LibraryScreen

_SEARCHING = "Searching for valid DJ USBs…"
_NONE_FOUND = "Did not detect a valid DJ USB"
_STATUS_ID = "status"


class HomeScreen(Screen):
    """
    Poll for a mount to appear, check it, then push the Library screen.

    A mount is "valid" when it has a supported Rekordbox export
    (``MountProbe.is_dj_usb and MountProbe.is_supported``) -- Serato need not
    exist yet (bootstrapping one is TASK-076, not this screen's job).
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
        with Container():
            yield Static(_SEARCHING, id=_STATUS_ID)

    def on_mount(self) -> None:
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
                self._show(f"Opening {change.path}…")
                self.run_worker(self._open(change.path), exclusive=True)
                return
            self._seen_invalid = True

        self._show(_NONE_FOUND if self._seen_invalid else _SEARCHING)

    async def _open(self, mount: Path) -> None:
        """Open the library off the event loop thread, then report readiness."""
        try:
            library = await asyncio.to_thread(open_library, mount)
        except (OSError, DatabaseNotFoundError, UnsupportedDatabaseError) as exc:
            self._seen_invalid = True
            self._show(f"{_NONE_FOUND} ({exc})")
            return
        self.library = library
        count = len(library.rekordbox.list_playlists())
        self._show(f"Ready: {mount.name} — {count} playlists")
        self.app.push_screen(LibraryScreen(library))

    def _show(self, message: str) -> None:
        self.query_one(f"#{_STATUS_ID}", Static).update(message)
