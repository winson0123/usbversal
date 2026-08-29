"""Deriving a rate and ETA from a job's progress events over time."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

_WINDOW = 8


@dataclass(frozen=True)
class ProgressEstimate:
    """
    Rate and time-to-completion derived from a job's progress so far.

    Attributes:
        rate_per_second: Units completed per second, averaged over the recent
            window. None until progress has actually advanced.
        eta_seconds: Estimated seconds remaining at that rate. None when the
            total is unknown, or the run has not advanced yet.
    """

    rate_per_second: float | None
    eta_seconds: float | None


class ProgressRateTracker:
    """
    Turns successive ``current``/``total`` samples into a rate and an ETA.

    Averages over the last ``_WINDOW`` progress advances, not the whole run.
    Cheap early steps (index writes, reused backup objects) would otherwise
    keep the rate high and the ETA climbing once slower tag writes begin.
    """

    def __init__(self) -> None:
        self._samples: deque[tuple[float, int]] = deque(maxlen=_WINDOW)

    def observe(self, *, current: int, total: int | None, at: float) -> ProgressEstimate:
        """
        Record one progress sample and return the estimate after it.

        Args:
            current: Units completed so far.
            total: Units the job expects to complete, when known.
            at: Monotonic timestamp of this sample, in seconds.

        Returns:
            The rate/ETA estimate incorporating this sample.
        """
        if not self._samples or current != self._samples[-1][1]:
            self._samples.append((at, current))
        if len(self._samples) < 2:
            return ProgressEstimate(rate_per_second=None, eta_seconds=None)

        start_at, start_current = self._samples[0]
        elapsed = at - start_at
        completed = current - start_current
        if elapsed <= 0 or completed <= 0:
            return ProgressEstimate(rate_per_second=None, eta_seconds=None)

        rate = completed / elapsed
        if total is None:
            return ProgressEstimate(rate_per_second=rate, eta_seconds=None)

        remaining = total - current
        eta = remaining / rate if remaining > 0 else 0.0
        return ProgressEstimate(rate_per_second=rate, eta_seconds=eta)


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds as ``Xs`` or ``XmYYs``.

    Shared by the CLI progress renderer and the TUI progress screen so an ETA
    reads the same way in both.

    Args:
        seconds: Duration to format.

    Returns:
        A short, human-readable duration string.
    """
    whole = round(seconds)
    minutes, secs = divmod(whole, 60)
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"
