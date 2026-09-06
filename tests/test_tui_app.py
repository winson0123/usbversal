"""Tests for the TUI app shell, in particular the dedicated Rekordbox thread.

rbox's PyOneLibrary is not Send: pyo3 aborts the whole process if it is ever
touched from a thread other than the one that created it. Every call that
opens or reads through UsbLibrary.rekordbox must go through
run_rekordbox so it stays pinned to one thread for the library's whole
session. This is what a real stick caught in practice (see TASK-206-208
follow-up) that mocked-library tests could not, since a mock has no thread
affinity to violate.
"""

import threading

import pytest
from textual.app import App
from textual.command import CommandPalette
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
    """A bare app with nothing but the mixin, no on_mount at all."""


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
async def test_usbversal_app_pushes_exactly_one_home_screen() -> None:
    """UsbversalApp mixes the thread in without triggering the double-dispatch
    that subclassing it (rather than mixing in directly) would cause."""
    app = UsbversalApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        assert isinstance(app.screen, HomeScreen)
        assert len(app.screen_stack) == 2  # the default screen, plus Home




def test_command_palette_is_disabled() -> None:
    """Theme picker and other stock palette commands must not be reachable."""
    assert UsbversalApp.ENABLE_COMMAND_PALETTE is False


@pytest.mark.asyncio
async def test_ctrl_p_does_not_open_command_palette() -> None:
    """ctrl+p is Textual's palette binding; with the palette off it is a no-op."""
    app = UsbversalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()

        assert isinstance(app.screen, HomeScreen)
        assert not any(isinstance(screen, CommandPalette) for screen in app.screen_stack)


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
    """With nothing open, quit is just park-nothing plus exit. No thread hop."""
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


def _quit_hint_notes(app: UsbversalApp) -> list[tuple[str, str]]:
    """
    Return ``(title, message)`` for each on-screen notification.

    Args:
        app: Running TUI.

    Returns:
        Title and message of every current notification.
    """
    return [(note.title, note.message) for note in app._notifications]


@pytest.mark.asyncio
async def test_plain_q_does_not_quit() -> None:
    """A stray q must not exit; it uses the same toast as Ctrl+C."""
    app = UsbversalApp()
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        assert _quit_hint_notes(app) == [
            ("Do you want to quit?", "Press [b]ctrl+q[/b] to quit the app")
        ]
        assert app.is_running


@pytest.mark.asyncio
async def test_ctrl_c_shows_the_same_quit_hint_as_q() -> None:
    """Ctrl+C must not exit; it toasts the real quit key."""
    app = UsbversalApp()
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert _quit_hint_notes(app) == [
            ("Do you want to quit?", "Press [b]ctrl+q[/b] to quit the app")
        ]
        assert app.is_running


@pytest.mark.asyncio
async def test_ctrl_q_quits() -> None:
    """Ctrl+Q is the quit key."""
    app = UsbversalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert not app.is_running


def test_rewrite_alt_screen_swaps_on_and_off_for_a_clear() -> None:
    """1049 h/l become a viewport clear, including when concatenated."""
    assert rewrite_alt_screen("\x1b[?1049h") == "\x1b[2J\x1b[H"
    assert rewrite_alt_screen("\x1b[?1049l\x1b[?25h") == "\x1b[2J\x1b[H\x1b[?25h"
    assert rewrite_alt_screen("hello") == "hello"


@pytest.mark.parametrize(
    ("release", "wt_session", "expected"),
    [
        ("6.6.114.1-microsoft-standard-WSL2", None, True),
        ("24H2", "some-guid", True),
        ("6.8.0-generic", None, False),
    ],
)
def test_conpty_alt_screen_is_slow(
    monkeypatch: pytest.MonkeyPatch,
    release: str,
    wt_session: str | None,
    expected: bool,
) -> None:
    """Skip the alt screen on WSL or Windows Terminal; keep it on plain Linux."""
    if wt_session is None:
        monkeypatch.delenv("WT_SESSION", raising=False)
    else:
        monkeypatch.setenv("WT_SESSION", wt_session)
    monkeypatch.setattr("app.tui.app.platform.release", lambda: release)

    assert conpty_alt_screen_is_slow() is expected


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
