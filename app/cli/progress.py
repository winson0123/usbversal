"""CLI subscribers for event bus progress output."""

import sys
import time

from app.core.event_envelope import Event
from app.jobs.progress_rate import ProgressRateTracker, format_duration


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
        if not self._should_emit(now):
            return
        print(_progress_line(event, now, self._trackers), file=sys.stderr)

    def _should_emit(self, now: float) -> bool:
        """Return True when this event should be printed, honouring the throttle."""
        if self._verbose:
            return True
        if now - self._last_emit_at < self._min_interval_s:
            return False
        self._last_emit_at = now
        return True


def _progress_line(event: Event, now: float, trackers: dict[str, ProgressRateTracker]) -> str:
    """
    Format one job.progress event as a stderr line.

    Args:
        event: Normalized progress event.
        now: Monotonic timestamp of this render.
        trackers: Per-job rate trackers, mutated when counts are present.

    Returns:
        Human-readable progress line, without a trailing newline.
    """
    message = str(event.payload.get("message", ""))
    current = event.payload.get("current")
    total = event.payload.get("total")
    if current is None or total is None:
        return message
    tracker = trackers.setdefault(event.job_id, ProgressRateTracker())
    estimate = tracker.observe(current=current, total=total, at=now)
    return _counted_line(message, current, total, estimate)


def _counted_line(message: str, current: object, total: object, estimate: object) -> str:
    """Append rate and ETA to a ``[current/total]`` progress line."""
    line = f"[{current}/{total}] {message}"
    if estimate.rate_per_second is None:
        return line
    line += f" ({estimate.rate_per_second:.1f}/s"
    if estimate.eta_seconds is not None:
        line += f", eta {format_duration(estimate.eta_seconds)}"
    return line + ")"
