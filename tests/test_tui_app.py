"""Tests for the TUI app shell, in particular the dedicated Rekordbox thread.

rbox's PyOneLibrary is not Send: pyo3 aborts the whole process if it is ever
touched from a thread other than the one that created it. Every call that
opens or reads through UsbLibrary.rekordbox must go through
run_rekordbox so it stays pinned to one thread for the library's whole
session -- this is what a real stick caught in practice (see TASK-206-208
follow-up) that mocked-library tests could not, since a mock has no thread
affinity to violate.
"""

import threading

import pytest
from textual.app import App
from textual.screen import Screen

from app.tui.app import RekordboxThreadMixin, UsbversalApp
from app.tui.screens.home import HomeScreen


class _Harness(RekordboxThreadMixin, App):
    """A bare app with nothing but the mixin -- no on_mount at all."""


@pytest.mark.asyncio
async def test_run_rekordbox_calls_land_on_the_same_thread() -> None:
    """Two separate run_rekordbox calls execute on the identical OS thread."""
    app = _Harness()
    async with app.run_test():
        first = await app.run_rekordbox(threading.get_ident)
        second = await app.run_rekordbox(threading.get_ident)

        assert first == second


@pytest.mark.asyncio
async def test_run_rekordbox_thread_is_not_the_event_loop_thread() -> None:
    """The dedicated thread is a real background thread, not the UI thread."""
    app = _Harness()
    async with app.run_test():
        ui_thread = threading.get_ident()

        worker_thread = await app.run_rekordbox(threading.get_ident)

        assert worker_thread != ui_thread


@pytest.mark.asyncio
async def test_run_rekordbox_passes_args_and_kwargs_through() -> None:
    """Positional and keyword arguments reach the wrapped callable intact."""
    app = _Harness()

    def combine(a, b, *, sep="-"):
        return f"{a}{sep}{b}"

    async with app.run_test():
        result = await app.run_rekordbox(combine, "x", "y", sep="+")

        assert result == "x+y"


@pytest.mark.asyncio
async def test_usbversal_app_pushes_exactly_one_home_screen() -> None:
    """UsbversalApp mixes the thread in without triggering the double-dispatch
    that subclassing it (rather than mixing in directly) would cause."""
    app = UsbversalApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        assert isinstance(app.screen, HomeScreen)
        assert len(app.screen_stack) == 2  # the default screen, plus Home


class _FakeLibraryScreen(Screen):
    """Stands in for Home/Library/Progress, each of which holds the open
    UsbLibrary on a public ``library`` attribute."""

    def __init__(self) -> None:
        """Hold a dummy library reference the quit path must clear."""
        super().__init__()
        self.library = object()


@pytest.mark.asyncio
async def test_quit_clears_library_references_on_the_rekordbox_thread() -> None:
    """Quitting must null out every screen's library reference itself, on the
    dedicated thread, rather than let Textual's own teardown be what drops
    the last reference to a pyo3 PyOneLibrary from the main thread."""
    app = UsbversalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = _FakeLibraryScreen()
        second = _FakeLibraryScreen()
        await app.push_screen(first)
        await app.push_screen(second)
        await pilot.pause()

        await app.action_quit()

        assert first.library is None
        assert second.library is None
