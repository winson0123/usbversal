"""CLI subscribers for event bus progress output."""

import sys
import time

from app.core.event_envelope import Event


class CliProgressRenderer:
    """
    Render ``job.progress`` events to stderr with optional throttling.

    Attributes:
        min_interval_s: Minimum seconds between rendered progress lines.
        verbose: When True, emit every progress event without throttling.
    """

    def __init__(self, *, min_interval_s: float = 0.1, verbose: bool = False) -> None:
        """
        Initialize the renderer.

        Args:
            min_interval_s: Minimum interval between progress lines.
            verbose: Disable throttling when True.
        """
        self._min_interval_s = min_interval_s
        self._verbose = verbose
        self._last_emit_at = 0.0

    def __call__(self, event: Event) -> None:
        """
        Print a human-readable progress line for job.progress events.

        Args:
            event: Normalized event envelope from the bus.
        """
        if event.type != "job.progress":
            return

        if not self._verbose:
            now = time.monotonic()
            if now - self._last_emit_at < self._min_interval_s:
                return
            self._last_emit_at = now

        message = str(event.payload.get("message", ""))
        current = event.payload.get("current")
        total = event.payload.get("total")
        if current is not None and total is not None:
            line = f"[{current}/{total}] {message}"
        else:
            line = message
        print(line, file=sys.stderr)
