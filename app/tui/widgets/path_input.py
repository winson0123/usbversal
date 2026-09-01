"""Path entry with Tab-cycling through matching directories."""

from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.widgets import Input


def match_candidates(partial: str) -> list[str]:
    """
    List every directory matching a partial path, for Tab-cycling.

    Args:
        partial: The path typed so far.

    Returns:
        Full path candidates, each with a trailing "/", sorted by name --
        or an empty list if the parent directory can't be listed or
        nothing matches. Directories only: the target is always a mount
        root, and a file can never be one.
    """
    path = Path(partial)
    if partial == "" or partial.endswith("/"):
        directory, prefix = (path if partial else Path(".")), ""
    else:
        directory, prefix = path.parent, path.name

    try:
        entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
    except OSError:
        return []

    candidates = []
    for entry in entries:
        if entry.name.startswith(prefix) and entry.is_dir():
            full = directory / entry.name if str(directory) != "." else Path(entry.name)
            candidates.append(f"{full}/")
    return candidates


class PathInput(Input):
    """Path entry field with Tab-cycling through matching directories.

    Each Tab press advances to the next matching directory, wrapping back
    to the first after the last, rather than completing to a common
    prefix, which still leaves an ambiguous path needing to be finished by
    hand. Retyping (the value no longer matching where the cycle left it)
    starts a fresh cycle from whatever's typed now.

    A plain (non-priority) binding is enough to win over Screen's own
    default ``tab`` -> ``app.focus_next`` binding: Textual checks a
    focused widget's own bindings before walking up to its ancestors, so
    this only needs to out-rank Screen when *this* widget has focus.
    """

    BINDINGS = [Binding("tab", "complete", "Complete path", show=False)]

    def __init__(self, *args: object, **kwargs: object) -> None:
        """
        Args:
            *args: Forwarded to ``Input``.
            **kwargs: Forwarded to ``Input``.
        """
        super().__init__(*args, **kwargs)
        self._cycle: tuple[list[str], int] | None = None

    def action_complete(self) -> None:
        """Advance to the next matching directory, or start a fresh cycle."""
        if self._cycle is not None:
            matches, index = self._cycle
            if self.value == matches[index]:
                index = (index + 1) % len(matches)
                self._set_value(matches[index])
                self._cycle = (matches, index)
                return

        matches = match_candidates(self.value)
        if not matches:
            return
        self._set_value(matches[0])
        self._cycle = (matches, 0)

    def _set_value(self, value: str) -> None:
        """Set the field value and move the cursor to the end.

        Args:
            value: Completed path to show.
        """
        self.value = value
        self.cursor_position = len(value)
