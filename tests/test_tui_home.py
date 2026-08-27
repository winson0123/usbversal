"""Tests for the TUI Home screen (steps 1-2 of the target flow: Waiting/Detect)."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.screen import Screen
from textual.widgets import Static

from app.core.domain import MountPoint
from app.storage.mount_watch import MountWatcher
from app.storage.mounts import MountScanner
from app.tui.app import UsbversalApp
from app.tui.screens.home import HomePhase, HomeScreen
from app.tui.widgets.path_input import PathInput, match_candidates


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
async def test_search_times_out_and_reveals_manual_entry() -> None:
    """Nothing plugged in at all, ever, is not a permanent bare spinner --
    past SCAN_TIMEOUT_S it gives up the same way an actual rejection
    would, so the user isn't stuck with no way to act."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        home._searching_since = time.monotonic() - home.SCAN_TIMEOUT_S - 1

        home.poll_mounts()
        await pilot.pause()

        assert home.query_one("#spinner").display is False
        assert "Did not detect a valid DJ USB" in _status_text(home)
        path_input = home.query_one(PathInput)
        assert path_input.display is True
        assert path_input.disabled is False


@pytest.mark.asyncio
async def test_still_within_the_timeout_keeps_spinning() -> None:
    """Nothing found yet, but well under SCAN_TIMEOUT_S, is not a failure --
    still just quietly searching."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        home._searching_since = time.monotonic() - (home.SCAN_TIMEOUT_S - 0.5)

        home.poll_mounts()
        await pilot.pause()

        assert home.query_one("#spinner").display is True
        assert home.query_one(PathInput).display is False


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
        patch("app.tui.screens.home.prepare_library", return_value=fake_library),
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
        patch("app.tui.screens.home.prepare_library", side_effect=_raise),
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
        patch("app.tui.screens.home.prepare_library", return_value=fake_library),
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
        patch("app.services.library.open_library", return_value=fake_library),
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


def test_match_candidates_lists_every_matching_directory(tmp_path: Path) -> None:
    """All directories sharing the prefix come back, sorted, not just the
    one nearest the front -- this is what Tab cycles through."""
    (tmp_path / "usbstick2").mkdir()
    (tmp_path / "usbstick1").mkdir()

    matches = match_candidates(f"{tmp_path}/us")

    assert matches == [f"{tmp_path}/usbstick1/", f"{tmp_path}/usbstick2/"]


def test_match_candidates_excludes_files(tmp_path: Path) -> None:
    """A file can never be a mount root, so it's never offered."""
    (tmp_path / "usbstick").mkdir()
    (tmp_path / "usbstick.txt").write_text("not a directory")

    assert match_candidates(f"{tmp_path}/usbstick") == [f"{tmp_path}/usbstick/"]


def test_match_candidates_is_empty_when_nothing_matches(tmp_path: Path) -> None:
    """No matching directory, or an unreadable parent, is an empty list,
    not an error."""
    assert match_candidates(f"{tmp_path}/nope") == []
    assert match_candidates(f"{tmp_path}/nope/deeper") == []


def _force_error_state(home: HomeScreen) -> None:
    """Drive the screen into its failed/error state directly, the way a
    real failed auto-scan or a failed manual open would -- which is the
    only way the path input becomes visible and interactive at all."""
    home._enter(HomePhase.FAILED, "forced for test setup")


@pytest.mark.asyncio
async def test_searching_shows_spinner_and_hides_the_path_input() -> None:
    """Nothing plugged in yet is SEARCHING: caption plus spinner, path
    input hidden and disabled so it cannot eat keystrokes."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        home.poll_mounts()
        await pilot.pause()

        assert home.query_one("#spinner").display is True
        assert "Automatically detecting" in _status_text(home)
        path_input = home.query_one(PathInput)
        assert path_input.display is False
        assert path_input.disabled is True
        assert app.focused is not path_input


@pytest.mark.asyncio
async def test_tab_cycles_through_matching_directories(tmp_path: Path) -> None:
    """Tab on the path field steps through every matching directory one at
    a time, wrapping back to the first -- not moving focus away, and not
    just completing to a common prefix that's still ambiguous."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        _force_error_state(home)
        await pilot.pause()

        path_input = home.query_one(PathInput)
        path_input.value = f"{tmp_path}/"
        path_input.cursor_position = len(path_input.value)

        await pilot.press("tab")
        await pilot.pause()
        assert path_input.value == f"{tmp_path}/alpha/"
        assert app.focused is path_input

        await pilot.press("tab")
        await pilot.pause()
        assert path_input.value == f"{tmp_path}/beta/"

        await pilot.press("tab")
        await pilot.pause()
        assert path_input.value == f"{tmp_path}/alpha/"


@pytest.mark.asyncio
async def test_typing_after_a_tab_cycle_starts_a_fresh_one(tmp_path: Path) -> None:
    """Editing the value mid-cycle abandons the old candidate list rather
    than continuing to step through matches for the path before it was
    changed by hand."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alphabet").mkdir()
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        _force_error_state(home)
        await pilot.pause()

        path_input = home.query_one(PathInput)
        path_input.value = f"{tmp_path}/"
        path_input.cursor_position = len(path_input.value)
        await pilot.press("tab")
        await pilot.pause()
        assert path_input.value == f"{tmp_path}/alpha/"

        # Simulate hand-editing: change the value without going through Tab.
        path_input.value = f"{tmp_path}/alphabet"
        path_input.cursor_position = len(path_input.value)

        await pilot.press("tab")
        await pilot.pause()

        assert path_input.value == f"{tmp_path}/alphabet/"


@pytest.mark.asyncio
async def test_enter_on_empty_input_visibly_resumes_scanning() -> None:
    """Retrying must actually look like something happened -- not silently
    re-print the identical error, which is indistinguishable from Enter
    having done nothing at all."""
    watcher = MountWatcher(_FakeScanner([]))
    app = UsbversalApp(watcher)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        _force_error_state(home)
        await pilot.pause()
        assert home.query_one("#spinner").display is False

        await pilot.press("enter")
        await pilot.pause()

        assert home.query_one("#spinner").display is True
        assert home.query_one(PathInput).display is False
        assert home._phase is HomePhase.SEARCHING


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
        patch("app.tui.screens.home.prepare_library", return_value=fake_library) as prepare,
        patch("app.tui.screens.home.LibraryScreen", _DummyLibraryScreen),
    ):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            _force_error_state(home)
            await pilot.pause()
            path_input = home.query_one(PathInput)
            path_input.value = str(tmp_path)

            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            prepare.assert_called_once_with(tmp_path)
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

    with patch("app.tui.screens.home.prepare_library", side_effect=_raise):
        async with app.run_test() as pilot:
            await pilot.pause()
            home = app.screen
            _force_error_state(home)
            await pilot.pause()
            path_input = home.query_one(PathInput)
            path_input.value = str(tmp_path / "nope")

            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert home.library is None
            assert "Did not detect a valid DJ USB" in _status_text(home)
            assert path_input.disabled is False
            assert path_input.display is True
