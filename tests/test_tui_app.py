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

from app.tui.app import (
    RekordboxThreadMixin,
    UsbversalApp,
    conpty_alt_screen_is_slow,
    rewrite_alt_screen,
    suppress_alt_screen,
)
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
async def test_quit_parks_library_handles_without_dropping_them_yet() -> None:
    """Quit must take every screen's library off the stack immediately so
    Textual can tear down without Drop, but keep the objects alive on the
    app until unmount drops them on the rekordbox thread."""
    app = UsbversalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        first = _FakeLibraryScreen()
        second = _FakeLibraryScreen()
        held = [first.library, second.library]
        await app.push_screen(first)
        await app.push_screen(second)
        await pilot.pause()

        await app.action_quit()

        assert first.library is None
        assert second.library is None
        assert app._held_libraries == held


@pytest.mark.asyncio
async def test_drop_parked_libraries_runs_on_the_rekordbox_thread() -> None:
    """Clearing the park list (the Drop) must run on the dedicated thread,
    not the UI thread that parked the handles."""
    app = UsbversalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        creator = await app.run_rekordbox(threading.get_ident)
        app._held_libraries.append(object())

        def drop_and_id() -> int:
            """Drop parked handles, then report which thread ran the Drop."""
            app._drop_parked_libraries()
            return threading.get_ident()

        dropped_on = await app.run_rekordbox(drop_and_id)

        assert dropped_on == creator
        assert app._held_libraries == []


@pytest.mark.asyncio
async def test_quit_from_home_does_not_hop_to_the_rekordbox_thread() -> None:
    """With nothing open, quit is just park-nothing plus exit -- no thread hop."""
    app = UsbversalApp()
    hops = 0
    original = app.run_rekordbox

    async def counting(func, *args, **kwargs):
        """Count hops through run_rekordbox, then forward to the original."""
        nonlocal hops
        hops += 1
        return await original(func, *args, **kwargs)

    app.run_rekordbox = counting  # type: ignore[method-assign]
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.action_quit()

    assert hops == 0


def test_rewrite_alt_screen_swaps_on_and_off_for_a_clear() -> None:
    """1049 h/l become a viewport clear, including when concatenated."""
    assert rewrite_alt_screen("\x1b[?1049h") == "\x1b[2J\x1b[H"
    assert rewrite_alt_screen("\x1b[?1049l\x1b[?25h") == "\x1b[2J\x1b[H\x1b[?25h"
    assert rewrite_alt_screen("hello") == "hello"


def test_conpty_alt_screen_is_slow_on_wsl_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """WSL's kernel release string is enough to skip the alt screen."""
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.setattr("app.tui.app.platform.release", lambda: "6.6.114.1-microsoft-standard-WSL2")

    assert conpty_alt_screen_is_slow() is True


def test_conpty_alt_screen_is_slow_on_windows_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows Terminal advertises itself with WT_SESSION."""
    monkeypatch.setenv("WT_SESSION", "some-guid")
    monkeypatch.setattr("app.tui.app.platform.release", lambda: "24H2")

    assert conpty_alt_screen_is_slow() is True


def test_conpty_alt_screen_is_not_slow_on_plain_linux(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normal Linux desktop should keep the alt screen (instant restore)."""
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.setattr("app.tui.app.platform.release", lambda: "6.8.0-generic")

    assert conpty_alt_screen_is_slow() is False


def test_suppress_alt_screen_filters_driver_writes() -> None:
    """The installed write wrapper rewrites 1049 sequences and passes the rest."""
    written: list[str] = []

    class _Driver:
        def write(self, text: str) -> None:
            """Record what would have gone to the terminal."""
            written.append(text)

    driver = _Driver()
    suppress_alt_screen(driver)  # type: ignore[arg-type]
    driver.write("\x1b[?1049h")
    driver.write("payload")
    driver.write("\x1b[?1049l\x1b[?25h")

    assert written == ["\x1b[2J\x1b[H", "payload", "\x1b[2J\x1b[H\x1b[?25h"]
