"""Tests for the TUI Home screen (steps 1-2 of the target flow: Waiting/Detect)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from textual.screen import Screen
from textual.widgets import Static

from app.core.domain import MountPoint
from app.storage.mount_watch import MountWatcher
from app.storage.mounts import MountScanner
from app.tui.app import UsbversalApp
from app.tui.screens.home import HomeScreen, _complete_path, _PathInput


class _FakeScanner(MountScanner):
    """A MountScanner whose result is fixed for one test."""

    def __init__(self, mounts: list[MountPoint]) -> None:
        self.mounts = mounts

    def list_mounts(self) -> list[MountPoint]:
        return self.mounts


class _DummyLibraryScreen(Screen):
    """Stands in for the real Library screen -- that screen's own behaviour
    is covered by tests/test_tui_library.py; these tests only need proof that
    Home handed off to it with the right library."""

    def __init__(self, library: object) -> None:
        super().__init__()
        self.library = library

    def compose(self):
        yield Static("dummy")


def _point(path: Path) -> MountPoint:
    return MountPoint(path=path, source="test")


def _status_text(screen: HomeScreen) -> str:
    """Read back the Home screen's status line as plain text."""
    return str(screen.query_one("#status", Static).render())


@pytest.mark.asyncio
async def test_shows_searching_with_nothing_mounted() -> None:
    """Nothing plugged in yet is the initial, and steady, state: the spinner
    runs under the banner, alongside a caption saying it's looking -- not
    silence, and not the red not-found error."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        home.poll_mounts()
        await pilot.pause()

        assert home.query_one("#spinner").display is True
        status = home.query_one("#status", Static)
        assert status.display is True
        assert "Automatically detecting" in _status_text(home)


@pytest.mark.asyncio
async def test_shows_none_found_for_a_mount_that_is_not_a_dj_usb(tmp_path: Path) -> None:
    """A mount that appears but fails the readiness probe is reported as such."""
    watcher = MountWatcher(_FakeScanner([_point(tmp_path)]))
    app = UsbversalApp(watcher)
    with patch("app.tui.screens.home.probe_mount", return_value=None):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            home.poll_mounts()
            await pilot.pause()

            assert "Did not detect a valid DJ USB" in _status_text(home)
            assert home.query_one("#spinner").display is False
            assert home.query_one("#status").display is True


@pytest.mark.asyncio
async def test_a_valid_mount_opens_the_library_and_hands_off(tmp_path: Path) -> None:
    """A mount that passes the probe is opened and the Library screen takes over."""
    watcher = MountWatcher(_FakeScanner([_point(tmp_path)]))
    app = UsbversalApp(watcher)

    fake_probe = type("P", (), {"is_dj_usb": True, "is_supported": True, "has_serato": False})()
    fake_library = type(
        "L", (), {"rekordbox": type("R", (), {"list_playlists": lambda self: [1, 2, 3]})()}
    )()

    with (
        patch("app.tui.screens.home.probe_mount", return_value=fake_probe),
        patch("app.tui.screens.home.bootstrap_serato_library"),
        patch("app.tui.screens.home.open_library", return_value=fake_library),
        patch("app.tui.screens.home.LibraryScreen", _DummyLibraryScreen),
    ):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            home.poll_mounts()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert home.library is fake_library
            assert isinstance(app.screen, _DummyLibraryScreen)
            assert app.screen.library is fake_library


@pytest.mark.asyncio
async def test_an_open_failure_is_reported_not_raised(tmp_path: Path) -> None:
    """A race between the probe and the open does not crash the app."""
    watcher = MountWatcher(_FakeScanner([_point(tmp_path)]))
    app = UsbversalApp(watcher)

    fake_probe = type("P", (), {"is_dj_usb": True, "is_supported": True, "has_serato": False})()

    def _raise(_mount: Path):
        raise FileNotFoundError("gone")

    with (
        patch("app.tui.screens.home.probe_mount", return_value=fake_probe),
        patch("app.tui.screens.home.bootstrap_serato_library"),
        patch("app.tui.screens.home.open_library", side_effect=_raise),
    ):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            home.poll_mounts()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert home.library is None
            assert isinstance(app.screen, HomeScreen)
            assert "Did not detect a valid DJ USB" in _status_text(home)


@pytest.mark.asyncio
async def test_stops_polling_once_a_library_is_open(tmp_path: Path) -> None:
    """A second poll after opening does not reopen or reset state."""
    watcher = MountWatcher(_FakeScanner([_point(tmp_path)]))
    app = UsbversalApp(watcher)

    fake_probe = type("P", (), {"is_dj_usb": True, "is_supported": True, "has_serato": False})()
    fake_library = type(
        "L", (), {"rekordbox": type("R", (), {"list_playlists": lambda self: []})()}
    )()

    with (
        patch("app.tui.screens.home.probe_mount", return_value=fake_probe) as probe,
        patch("app.tui.screens.home.bootstrap_serato_library"),
        patch("app.tui.screens.home.open_library", return_value=fake_library),
        patch("app.tui.screens.home.LibraryScreen", _DummyLibraryScreen),
    ):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            home.poll_mounts()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            home.poll_mounts()
            await pilot.pause()

            assert probe.call_count == 1


@pytest.mark.asyncio
async def test_a_rekordbox_only_stick_gets_a_serato_library_bootstrapped(tmp_path: Path) -> None:
    """A real, unpatched bootstrap runs -- the point of wiring it in here at all."""
    rb = tmp_path / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"stub")
    assert not (tmp_path / "_Serato_").exists()

    watcher = MountWatcher(_FakeScanner([_point(tmp_path)]))
    app = UsbversalApp(watcher)
    fake_probe = type("P", (), {"is_dj_usb": True, "is_supported": True, "has_serato": False})()
    fake_library = type(
        "L", (), {"rekordbox": type("R", (), {"list_playlists": lambda self: []})()}
    )()

    with (
        patch("app.tui.screens.home.probe_mount", return_value=fake_probe),
        patch("app.tui.screens.home.open_library", return_value=fake_library),
        patch("app.tui.screens.home.LibraryScreen", _DummyLibraryScreen),
    ):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            home.poll_mounts()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

    assert (tmp_path / "_Serato_" / "database V2").is_file()
    assert (tmp_path / "_Serato_" / "Subcrates").is_dir()


def test_complete_path_fills_the_common_prefix(tmp_path: Path) -> None:
    """Ambiguous matches complete only as far as they agree, shell-style."""
    (tmp_path / "usbstick1").mkdir()
    (tmp_path / "usbstick2").mkdir()

    assert _complete_path(f"{tmp_path}/us") == f"{tmp_path}/usbstick"


def test_complete_path_adds_a_trailing_slash_for_a_unique_directory(tmp_path: Path) -> None:
    """A single unmistakable match completes all the way, plus a slash."""
    (tmp_path / "onlyone").mkdir()

    assert _complete_path(f"{tmp_path}/only") == f"{tmp_path}/onlyone/"


def test_complete_path_returns_none_when_there_is_nothing_to_add(tmp_path: Path) -> None:
    """No matches, or a prefix that's already maximally completed among
    several still-ambiguous matches, is a no-op."""
    (tmp_path / "usbstick1").mkdir()
    (tmp_path / "usbstick2").mkdir()

    assert _complete_path(f"{tmp_path}/nope") is None
    assert _complete_path(f"{tmp_path}/usbstick") is None


def _force_error_state(home: HomeScreen) -> None:
    """Drive the screen into its failed/error state directly, the way a
    real failed auto-scan or a failed manual open would -- which is the
    only way the path input becomes visible and interactive at all."""
    home._show_error("forced for test setup")


@pytest.mark.asyncio
async def test_input_is_hidden_and_unfocused_while_still_searching() -> None:
    """The path input only makes sense once auto-scanning has failed at
    something -- it must not be visible, focusable, or interactive while
    the spinner is still quietly searching."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        home.poll_mounts()
        await pilot.pause()

        path_input = home.query_one(_PathInput)
        assert path_input.display is False
        assert path_input.disabled is True
        assert app.focused is not path_input


@pytest.mark.asyncio
async def test_tab_completes_the_path_input(tmp_path: Path) -> None:
    """Tab on the path field completes it, rather than moving focus away."""
    (tmp_path / "usbstick").mkdir()
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        _force_error_state(home)
        await pilot.pause()

        path_input = home.query_one(_PathInput)
        path_input.value = f"{tmp_path}/usb"
        path_input.cursor_position = len(path_input.value)

        await pilot.press("tab")
        await pilot.pause()

        assert path_input.value == f"{tmp_path}/usbstick/"
        assert app.focused is path_input


@pytest.mark.asyncio
async def test_enter_on_an_empty_input_retries_the_scan_immediately() -> None:
    """Enter with nothing typed re-polls right away, instead of waiting for
    the next tick -- the "insert it now and press enter" path."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        _force_error_state(home)
        await pilot.pause()

        with patch.object(home, "poll_mounts") as poll_mounts:
            await pilot.press("enter")
            await pilot.pause()

            poll_mounts.assert_called_once()


@pytest.mark.asyncio
async def test_enter_with_a_typed_path_opens_that_library(tmp_path: Path) -> None:
    """A manually typed path is opened directly, without waiting for the
    watcher to notice it -- the "optionally enter the path" case."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)

    fake_library = type(
        "L", (), {"rekordbox": type("R", (), {"list_playlists": lambda self: [1, 2]})()}
    )()

    with (
        patch("app.tui.screens.home.bootstrap_serato_library"),
        patch("app.tui.screens.home.open_library", return_value=fake_library) as open_library,
        patch("app.tui.screens.home.LibraryScreen", _DummyLibraryScreen),
    ):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            _force_error_state(home)
            await pilot.pause()
            path_input = home.query_one(_PathInput)
            path_input.value = str(tmp_path)

            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            open_library.assert_called_once_with(tmp_path)
            assert home.library is fake_library
            assert isinstance(app.screen, _DummyLibraryScreen)


@pytest.mark.asyncio
async def test_a_typed_path_that_fails_to_open_re_enables_the_input(tmp_path: Path) -> None:
    """A bad manually typed path reports the error and lets the user retype,
    rather than leaving the field disabled forever."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)

    def _raise(_mount: Path):
        raise FileNotFoundError("gone")

    with patch("app.tui.screens.home.bootstrap_serato_library", side_effect=_raise):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            _force_error_state(home)
            await pilot.pause()
            path_input = home.query_one(_PathInput)
            path_input.value = str(tmp_path / "nope")

            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert home.library is None
            assert "Did not detect a valid DJ USB" in _status_text(home)
            assert path_input.disabled is False
            assert path_input.display is True
