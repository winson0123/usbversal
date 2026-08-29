"""The interactive TUI's top-level Textual application."""

from __future__ import annotations

import asyncio
import functools
import gc
import os
import platform
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from textual.app import App
from textual.binding import Binding
from textual.driver import Driver

from app.services.library import MountWatcher
from app.tui.screens.home import HomeScreen

_T = TypeVar("_T")
_MISSING = object()
_ALT_SCREEN_ON = "\x1b[?1049h"
_ALT_SCREEN_OFF = "\x1b[?1049l"
_CLEAR_SCREEN = "\x1b[2J\x1b[H"


def rewrite_alt_screen(text: str) -> str:
    """
    Replace alt-screen on/off sequences with a viewport clear.

    Args:
        text: Bytes the driver is about to write, possibly containing
            ``CSI ? 1049 h/l`` alone or concatenated with other sequences.

    Returns:
        The same text, with those sequences swapped for clear-and-home.
    """
    if _ALT_SCREEN_ON not in text and _ALT_SCREEN_OFF not in text:
        return text
    return text.replace(_ALT_SCREEN_ON, _CLEAR_SCREEN).replace(_ALT_SCREEN_OFF, _CLEAR_SCREEN)


def conpty_alt_screen_is_slow() -> bool:
    """
    True on Windows Terminal / WSL ConPTY.

    Leaving the alternate screen there blocks for about a second while
    the terminal syncs the cursor across buffers. Other hosts return
    from ``CSI ? 1049 l`` immediately and should keep the alt screen.

    Returns:
        Whether this process should draw on the main buffer instead.
    """
    if os.environ.get("WT_SESSION"):
        return True
    release = platform.release().lower()
    return "microsoft" in release or "wsl" in release


def suppress_alt_screen(driver: Driver) -> None:
    """
    Make ``driver.write`` never enter or leave the alternate screen.

    Args:
        driver: Textual driver whose ``write`` should be filtered.
    """
    write = driver.write

    def write_on_main_buffer(text: str) -> None:
        """Write ``text`` after stripping alt-screen sequences."""
        write(rewrite_alt_screen(text))

    driver.write = write_on_main_buffer  # type: ignore[method-assign]


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
        """Start the dedicated rekordbox worker and an empty park list."""
        super().__init__(*args, **kwargs)
        self._rekordbox_executor = ThreadPoolExecutor(max_workers=1)
        # Live UsbLibrary handles parked here on quit so Textual can tear
        # the screen stack down without being the one that drops them.
        self._held_libraries: list[object] = []

    def _drop_parked_libraries(self) -> None:
        """
        Drop every parked ``UsbLibrary`` on this thread and collect.

        Must run on the dedicated rekordbox thread: clearing the list is
        what drops the last Python reference to ``PyOneLibrary``, and
        pyo3 aborts if that Drop runs anywhere else.
        """
        self._held_libraries.clear()
        gc.collect()

    def _shutdown_rekordbox_thread(self) -> None:
        """
        Drop parked library handles on the rekordbox thread, then join it.

        Called from ``on_unmount``, after Textual has already left the
        alternate screen -- the user sees the shell again while Drop
        finishes, rather than staring at a frozen last frame.
        """
        try:
            if self._held_libraries:
                self._rekordbox_executor.submit(self._drop_parked_libraries).result()
        finally:
            self._rekordbox_executor.shutdown(wait=True)

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
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, key_display="^Q"),
        Binding("q", "quit_hint", "Quit", show=False),
    ]

    # Textual's built-in dark theme still leaks through on a few stock
    # widgets even with ansi_color=True: none of these have a :ansi rule of
    # their own covering their background (Tree's covers text/guides only),
    # so they default to a near-black hex ($footer-background, $surface).
    # This neutralizes them to the terminal's own colours, same as
    # everything else. Functional highlights (the tree cursor, the progress
    # bar fill) are left alone; they convey real information, not a theme.
    CSS = """
    Footer, FooterKey, .footer-key--key, .footer-key--description {
        background: transparent;
        color: ansi_default;
    }
    Tree {
        background: transparent;
    }
    RichLog {
        background: transparent;
        color: ansi_default;
    }
    """

    def __init__(self, watcher: MountWatcher | None = None) -> None:
        """
        Args:
            watcher: Mount watcher for the Home screen; defaults to a fresh
                one. Injectable for tests.
        """
        # ansi_color=True: use the terminal's own default/ANSI colours
        # instead of Textual's built-in theme, whose $background/$foreground
        # are fixed hex values (a near-black regardless of the user's actual
        # terminal palette).
        super().__init__(ansi_color=True)
        self._watcher = watcher

    def on_mount(self) -> None:
        self.push_screen(HomeScreen(self._watcher))

    def _build_driver(
        self,
        headless: bool,
        inline: bool,
        mouse: bool,
        size: tuple[int, int] | None,
    ) -> Driver:
        """
        Build Textual's driver, skipping the alt screen on ConPTY.

        ``CSI ? 1049 l`` is the one-second pause still visible after
        TASK-232: Windows Terminal waits to sync the cursor across
        buffers. Drawing on the main buffer and clearing on exit avoids
        that swap. Headless and inline runs are left alone.

        Args:
            headless: No terminal I/O (tests).
            inline: Draw under the prompt instead of taking the screen.
            mouse: Enable mouse reporting.
            size: Forced terminal size, or None to detect.

        Returns:
            The driver Textual will use for this run.
        """
        driver = super()._build_driver(headless, inline, mouse, size)
        if not headless and not inline and conpty_alt_screen_is_slow():
            suppress_alt_screen(driver)
        return driver

    def action_quit_hint(self) -> None:
        """Show that quit is Ctrl+Q. A stray ``q`` must not exit."""
        self.notify("Need to use ^Q to quit")

    async def action_quit(self) -> None:
        """Park library handles and leave the UI; Drop runs after unmount."""
        self._park_library_handles()
        await super().action_quit()

    def _park_library_handles(self) -> None:
        """
        Move every screen's ``library`` onto this app so Textual can
        unmount the stack without dropping ``PyOneLibrary``.

        Safe on the UI thread: this only re-points Python references. The
        objects stay alive in ``_held_libraries`` until
        ``_drop_parked_libraries`` runs on the rekordbox thread, after
        the terminal has already been restored.
        """
        for screen in self.screen_stack:
            if getattr(screen, "library", _MISSING) is _MISSING:
                continue
            library = screen.library
            if library is not None:
                self._held_libraries.append(library)
            screen.library = None

    def on_unmount(self) -> None:
        """Drop parked Rekordbox handles on their thread, then join it."""
        self._shutdown_rekordbox_thread()


def run() -> None:
    """Launch the TUI. Entry point for ``usbversal`` / ``python -m app.tui``."""
    UsbversalApp().run()
