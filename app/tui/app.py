"""The interactive TUI's top-level Textual application."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from app.services.library import MountWatcher
from app.tui.screens.home import HomeScreen


class UsbversalApp(App):
    """
    Top-level Textual application shell.

    Home (steps 1-2) and Library (step 3) exist; Progress and Done
    (steps 4-5, running an actual sync) are TASK-208.
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


def run() -> None:
    """Launch the TUI. Entry point for ``usbversal tui`` / ``python -m app.tui``."""
    UsbversalApp().run()
