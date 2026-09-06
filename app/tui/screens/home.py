"""Home screen: wait for a DJ USB, then open it.

Watches for a mount and checks it for a readable Rekordbox export.
When two or more valid sticks are present, the user picks one.
"""

from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, CenterMiddle
from textual.screen import Screen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from app.services.cancellation import OperationCancelled
from app.services.errors import AdapterError, DatabaseNotFoundError, UnsupportedDatabaseError
from app.services.library import (
    MountChangeKind,
    MountWatcher,
    UsbLibrary,
    mount_display_name,
    prepare_library,
    probe_mount,
)
from app.services.sync_service import playlist_tree_sync_states
from app.tui.screens.library import LibraryScreen
from app.tui.widgets.path_input import PathInput
from app.tui.widgets.scan_bar import ScanBar

_NONE_FOUND = "Did not detect a valid DJ USB."
_RETRY_HINT = "Press 'Enter' to retry auto-scan…"
_SCANNING = "Automatically detecting for a DJ USB…"
_CHOOSE = "Choose a DJ USB…"
_OPENING = "Opening the DJ USB…"
_CHECKING = "Checking analysis…"
_BANNER_ID = "banner"
_SPINNER_ID = "spinner"
_STATUS_ID = "status"
_INPUT_ID = "path-input"
_MOUNT_LIST_ID = "mount-list"


_BANNER = """\
░█░█░█▀▀░█▀▄░█░█░█▀▀░█▀▄░█▀▀░█▀█░█░░
░█░█░▀▀█░█▀▄░▀▄▀░█▀▀░█▀▄░▀▀█░█▀█░█░░
░▀▀▀░▀▀▀░▀▀░░░▀░░▀▀▀░▀░▀░▀▀▀░▀░▀░▀▀▀"""


class HomePhase(StrEnum):
    """Visible Home screen phase. Polling only transitions; render follows."""

    SEARCHING = "searching"
    CHOOSING = "choosing"
    FAILED = "failed"
    OPENING = "opening"
    CHECKING = "checking"
    READY = "ready"


def _busy_caption(phase: HomePhase) -> Text:
    """
    One status line for the current spinning Home phase.

    SEARCHING, OPENING, and CHECKING are successive captions on the
    same banner screen, not stacked lines.

    Args:
        phase: SEARCHING, OPENING, or CHECKING.

    Returns:
        Dim single-line caption for ``phase``.
    """
    if phase is HomePhase.CHECKING:
        return Text(_CHECKING, style="dim")
    if phase is HomePhase.OPENING:
        return Text(_OPENING, style="dim")
    return Text(_SCANNING, style="dim")


class HomeScreen(Screen):
    """
    Poll for a mount to appear, check it, then push the Library screen.

    A mount is "valid" when it has a supported Rekordbox export
    (``MountProbe.is_dj_usb and MountProbe.is_supported``). Serato need not
    exist yet. ``prepare_library`` creates an empty one first when
    it doesn't, so a plain rekordbox stick is never a dead end.

    One valid stick opens automatically. Two or more enter ``CHOOSING``
    so the operator picks a volume. ``SEARCHING`` lasts until a mount is
    accepted, rejected, or ``SCAN_TIMEOUT_S`` passes with nothing to find.
    ``FAILED`` shows the manual-path input so the user can retry or type
    a path.
    """

    DEFAULT_CSS = """
    HomeScreen #banner, HomeScreen #spinner, HomeScreen #status {
        width: auto;
        text-align: center;
    }
    HomeScreen #spinner, HomeScreen #status {
        margin-top: 1;
    }
    HomeScreen #mount-list {
        width: 46;
        height: auto;
        max-height: 8;
        margin-top: 1;
    }
    HomeScreen #path-input {
        width: 46;
        margin-top: 1;
    }
    """

    POLL_INTERVAL_S = 1.0
    SCAN_TIMEOUT_S = 3.0

    def __init__(self, watcher: MountWatcher | None = None) -> None:
        """
        Args:
            watcher: Mount watcher to poll; defaults to a fresh one. Injectable
                so tests can drive it with a fake scanner instead of the real
                filesystem.
        """
        super().__init__()
        self._watcher = watcher or MountWatcher()
        self._phase = HomePhase.SEARCHING
        self._error = _NONE_FOUND
        self._searching_since = time.monotonic()
        self._candidates: dict[Path, str] = {}
        self.library: UsbLibrary | None = None

    def compose(self) -> ComposeResult:
        with CenterMiddle():
            with Center():
                yield Static(_BANNER, id=_BANNER_ID)
            with Center():
                yield ScanBar(id=_SPINNER_ID)
            with Center():
                yield Static("", id=_STATUS_ID)
            with Center():
                mount_list = OptionList(id=_MOUNT_LIST_ID)
                mount_list.display = False
                yield mount_list
            with Center():
                yield PathInput(
                    placeholder="or enter an absolute path…",
                    id=_INPUT_ID,
                )

    def on_mount(self) -> None:
        self._show_phase()
        self.set_interval(self.POLL_INTERVAL_S, self.poll_mounts)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        value = event.value.strip()
        if not value:
            self._enter(HomePhase.SEARCHING)
            self.poll_mounts()
            return
        self._enter(HomePhase.OPENING)
        self.run_worker(self._open(Path(value)), exclusive=True)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """
        Open the mount the user highlighted and confirmed.

        Args:
            event: Selection from the multi-USB chooser list.
        """
        event.stop()
        if self._phase is not HomePhase.CHOOSING:
            return
        option_id = event.option_id
        if not option_id:
            return
        mount = Path(option_id)
        if mount not in self._candidates:
            return
        self._enter(HomePhase.OPENING)
        self.run_worker(self._open(mount), exclusive=True)

    def poll_mounts(self) -> None:
        """One watch tick: update candidates, then open, choose, or fail."""
        if self._phase in (HomePhase.OPENING, HomePhase.CHECKING, HomePhase.READY):
            return
        saw_invalid = False
        for change in self._watcher.poll():
            if change.kind is MountChangeKind.DISAPPEARED:
                self._candidates.pop(change.path, None)
                continue
            if change.kind is not MountChangeKind.APPEARED:
                continue
            probe = probe_mount(change.path)
            if probe is not None and probe.is_dj_usb and probe.is_supported:
                self._candidates[change.path] = mount_display_name(change.path)
            else:
                saw_invalid = True
        self._apply_candidates(saw_invalid=saw_invalid)

    def _apply_candidates(self, *, saw_invalid: bool) -> None:
        """
        Decide the next Home phase from the current candidate set.

        Args:
            saw_invalid: True when this poll saw at least one mount that
                is not a supported DJ USB.
        """
        count = len(self._candidates)
        if count >= 2:
            self._enter(HomePhase.CHOOSING)
            self._refresh_mount_list()
            return
        if count == 1:
            mount = next(iter(self._candidates))
            self._enter(HomePhase.OPENING)
            self.run_worker(self._open(mount), exclusive=True)
            return
        if self._phase is HomePhase.CHOOSING:
            self._enter(HomePhase.SEARCHING)
        if saw_invalid:
            self._enter(HomePhase.FAILED)
            return
        if (
            self._phase is HomePhase.SEARCHING
            and time.monotonic() - self._searching_since >= self.SCAN_TIMEOUT_S
        ):
            self._enter(HomePhase.FAILED)

    def _refresh_mount_list(self) -> None:
        """Replace the chooser options from ``self._candidates``."""
        mount_list = self.query_one(f"#{_MOUNT_LIST_ID}", OptionList)
        previous = mount_list.highlighted
        options = [
            Option(label, id=str(path))
            for path, label in sorted(
                self._candidates.items(), key=lambda item: (item[1].casefold(), str(item[0]))
            )
        ]
        mount_list.clear_options()
        mount_list.add_options(options)
        if options:
            index = previous if previous is not None else 0
            mount_list.highlighted = min(index, len(options) - 1)

    async def _open(self, mount: Path) -> None:
        """
        Prepare the session, check analysis on Home, then push Library.

        The scan bar stays on this screen (and keeps ticking) until the
        tree states are ready, so Library does not open mid-check.

        Args:
            mount: Path that passed the DJ-USB probe, or a typed path.
        """
        try:
            # prepare_library opens Rekordbox, so it must stay on the app's
            # one dedicated thread. See UsbversalApp.run_rekordbox.
            library = await self.app.run_rekordbox(prepare_library, mount)
        except (OSError, AdapterError, DatabaseNotFoundError, UnsupportedDatabaseError) as exc:
            self._enter(HomePhase.FAILED, f"{_NONE_FOUND} ({exc})")
            return
        self.library = library
        self._enter(HomePhase.CHECKING)
        try:
            states = await self.app.run_rekordbox(
                playlist_tree_sync_states, library, check_analysis=True
            )
        except OperationCancelled:
            return
        except (OSError, AdapterError, DatabaseNotFoundError, UnsupportedDatabaseError) as exc:
            self._enter(HomePhase.FAILED, f"{_NONE_FOUND} ({exc})")
            return
        self._enter(HomePhase.READY)
        self.app.push_screen(LibraryScreen(library, states=states))

    def _enter(self, phase: HomePhase, error: str = _NONE_FOUND) -> None:
        """
        Move to `phase` and render only when the visible state changes.

        Args:
            phase: Next Home phase.
            error: Status text used when entering ``FAILED``.
        """
        if phase is HomePhase.SEARCHING and self._phase is not HomePhase.SEARCHING:
            self._searching_since = time.monotonic()
        if phase is self._phase and (phase is not HomePhase.FAILED or error == self._error):
            return
        self._phase = phase
        self._error = error
        if phase is not HomePhase.READY:
            self._show_phase()

    def _show_phase(self) -> None:
        """Apply spinner, status, list, and path-input widgets from ``self._phase``."""
        spinner = self.query_one(f"#{_SPINNER_ID}", ScanBar)
        status = self.query_one(f"#{_STATUS_ID}", Static)
        path_input = self.query_one(PathInput)
        mount_list = self.query_one(f"#{_MOUNT_LIST_ID}", OptionList)

        if self._phase is HomePhase.CHOOSING:
            spinner.display = False
            status.display = True
            status.update(Text(_CHOOSE, style="dim"))
            mount_list.display = True
            path_input.display = True
            path_input.disabled = False
            mount_list.focus()
            return

        mount_list.display = False
        mount_list.clear_options()

        if self._phase is HomePhase.FAILED:
            spinner.display = False
            status.display = True
            # Text(), not markup. The message can embed an arbitrary
            # exception string, which could itself contain "[...]" that
            # markup parsing would misread as a tag. The retry hint lives
            # here, not in the input's placeholder: the status line has
            # the whole screen's width, while the input box is fixed and
            # narrow.
            status.update(Text(f"{self._error} {_RETRY_HINT}", style="red"))
            path_input.display = True
            path_input.disabled = False
            path_input.focus()
            return

        spinner.display = True
        status.display = True
        # Dim, not red. This is routine "still looking" information.
        status.update(_busy_caption(self._phase))
        # Hide and disable it. Textual still auto-focuses a
        # hidden-but-enabled widget when it is the only focusable one.
        path_input.display = False
        path_input.disabled = True
