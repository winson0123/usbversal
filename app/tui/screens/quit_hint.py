"""Popup shown when the user presses ``q`` instead of Ctrl+Q."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, CenterMiddle
from textual.screen import ModalScreen
from textual.widgets import Static

_HINT_ID = "quit-hint"
_HINT = "Need to use ^Q to quit"


class QuitHintScreen(ModalScreen[None]):
    """A short modal: quit is Ctrl+Q, not ``q``."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("enter", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
        Binding("ctrl+q", "app.quit", "Quit", show=False),
    ]

    DEFAULT_CSS = """
    QuitHintScreen {
        align: center middle;
        background: transparent;
    }
    QuitHintScreen #quit-hint {
        width: auto;
        padding: 1 2;
        border: heavy ansi_default;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        """Show the quit-key hint in the middle of the screen."""
        with CenterMiddle():
            with Center():
                yield Static(_HINT, id=_HINT_ID)
