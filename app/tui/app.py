"""The interactive TUI's top-level Textual application."""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from textual.app import App
from textual.binding import Binding

from app.services.library import MountWatcher
from app.tui.screens.home import HomeScreen

_T = TypeVar("_T")


class RekordboxThreadMixin:
    """
    Gives an App the one dedicated thread all ``UsbLibrary.rekordbox`` access
    must stay pinned to.

    rbox's ``PyOneLibrary`` is not ``Send`` -- pyo3 aborts the whole process
    if it is ever touched from a thread other than the one that created it --
    so every call that opens or reads through ``UsbLibrary.rekordbox`` must
    land on this one thread for the library's whole lifetime, never the
    shared default executor ``asyncio.to_thread`` uses, which does not
    guarantee the same worker thread twice.

    A plain mixin, not a Screen/Widget subclass: Textual dispatches
    ``on_mount`` (and other lifecycle messages) to *every* class in the MRO
    that defines one, not just the most-derived override, so a test harness
    that needs this thread cannot simply subclass ``UsbversalApp`` and
    override ``on_mount`` -- both versions would fire. Mixing this in
    alongside a bare ``App`` avoids that collision entirely.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._rekordbox_executor = ThreadPoolExecutor(max_workers=1)

    def _shutdown_rekordbox_thread(self) -> None:
        self._rekordbox_executor.shutdown(wait=False)

    async def run_rekordbox(self, func: Callable[..., _T], *args: object, **kwargs: object) -> _T:
        """
        Run a blocking call that touches ``UsbLibrary.rekordbox`` off the UI
        thread, on the one dedicated thread it must stay pinned to.

        Args:
            func: Blocking callable to run (e.g. ``open_library``, ``sync_playlists``).
            *args: Positional arguments for ``func``.
            **kwargs: Keyword arguments for ``func``.

        Returns:
            Whatever ``func`` returns.
        """
        loop = asyncio.get_running_loop()
        call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(self._rekordbox_executor, call)


class UsbversalApp(RekordboxThreadMixin, App):
    """
    Top-level Textual application shell.

    All five target-flow screens exist: Home (steps 1-2), Library (step 3),
    Progress and Done (steps 4-5, TASK-208) -- the full Waiting -> Detect ->
    Library -> Progress -> Done flow is reachable end to end.
    """

    TITLE = "usbversal"
    BINDINGS = [Binding("q", "quit", "Quit", show=True)]

    def __init__(self, watcher: MountWatcher | None = None) -> None:
        """
        Args:
            watcher: Mount watcher for the Home screen; defaults to a fresh
                one. Injectable for tests.
        """
        super().__init__()
        self._watcher = watcher

    def on_mount(self) -> None:
        self.push_screen(HomeScreen(self._watcher))

    def on_unmount(self) -> None:
        self._shutdown_rekordbox_thread()


def run() -> None:
    """Launch the TUI. Entry point for ``usbversal tui`` / ``python -m app.tui``."""
    UsbversalApp().run()
