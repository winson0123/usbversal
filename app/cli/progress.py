"""CLI subscribers for event bus progress output."""

import sys
import time

from app.core.event_envelope import Event
from app.jobs.progress_rate import ProgressRateTracker


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as ``Xs`` or ``XmYYs``."""
    whole = round(seconds)
    minutes, secs = divmod(whole, 60)
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"


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
        self._trackers: dict[str, ProgressRateTracker] = {}

    def __call__(self, event: Event) -> None:
        """
        Print a human-readable progress line for job.progress events.

        Args:
            event: Normalized event envelope from the bus.
        """
        if event.type != "job.progress":
            return

        now = time.monotonic()
        if not self._verbose:
            if now - self._last_emit_at < self._min_interval_s:
                return
            self._last_emit_at = now

        message = str(event.payload.get("message", ""))
        current = event.payload.get("current")
        total = event.payload.get("total")
        if current is not None and total is not None:
            line = f"[{current}/{total}] {message}"
            tracker = self._trackers.setdefault(event.job_id, ProgressRateTracker())
            estimate = tracker.observe(current=current, total=total, at=now)
            if estimate.rate_per_second is not None:
                line += f" ({estimate.rate_per_second:.1f}/s"
                if estimate.eta_seconds is not None:
                    line += f", eta {_format_duration(estimate.eta_seconds)}"
                line += ")"
        else:
            line = message
        print(line, file=sys.stderr)
