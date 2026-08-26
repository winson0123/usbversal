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
from app.tui.screens.home import HomeScreen


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
    """Nothing plugged in yet is the initial, and steady, state."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        home.poll_mounts()
        await pilot.pause()

        assert "Searching for valid DJ USBs" in _status_text(home)


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
