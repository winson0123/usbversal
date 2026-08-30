"""Sweeping scan bar used on Home and the Library Tracks pane.

A bright point sweeps left to right over a dotted bar -- e.g.
``[·•●·]`` -- rather than a single pulsing glyph. The resting fill is
the same smallest dot the trail fades into, so the bar never looks
like it has empty gaps.
"""

from __future__ import annotations

from textual.widgets import Static

_SPINNER_INTERVAL_S = 0.1
_BAR_WIDTH = 4
_SPINNER_FRAME_COUNT = _BAR_WIDTH + 2


def scan_bar_frame(head: int) -> str:
    """
    One frame of the sweeping scan bar, with the bright point at `head`.

    Args:
        head: Cell index of the bright point.

    Returns:
        Bracketed bar string such as ``[·•●·]``.
    """
    cells = []
    for i in range(_BAR_WIDTH):
        dist = head - i
        if dist == 0:
            cells.append("●")
        elif dist == 1:
            cells.append("•")
        else:
            cells.append("·")
    return "[" + "".join(cells) + "]"


class ScanBar(Static):
    """A sweeping scan bar in the terminal's default foreground."""

    def on_mount(self) -> None:
        """Start the sweep and keep ticking until the widget unmounts."""
        self._frame = 0
        self.update(scan_bar_frame(self._frame))
        self.set_interval(_SPINNER_INTERVAL_S, self._tick)

    def _tick(self) -> None:
        """Advance one frame of the sweep."""
        self._frame = (self._frame + 1) % _SPINNER_FRAME_COUNT
        self.update(scan_bar_frame(self._frame))
