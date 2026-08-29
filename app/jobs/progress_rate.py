"""Deriving a rate and ETA from a job's progress events over time."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressEstimate:
    """
    Rate and time-to-completion derived from a job's progress so far.

    Attributes:
        rate_per_second: Units completed per second since this tracker started.
            None until progress has actually advanced.
        eta_seconds: Estimated seconds remaining at that rate. None when the
            total is unknown, or the run has not advanced yet.
    """

    rate_per_second: float | None
    eta_seconds: float | None


class ProgressRateTracker:
    """
    Turns successive ``current``/``total`` samples into a rate and an ETA.

    Uses every sample since this instance started, not a short recent window.
    The progress screen already starts a new tracker when the phase changes,
    so index, analysis, and crates each get their own average. A short window
    made the ETA climb and drop as skip and rewrite tracks interleaved.
    """

    def __init__(self) -> None:
        self._start_at: float | None = None
        self._start_current: int | None = None

    def observe(self, *, current: int, total: int | None, at: float) -> ProgressEstimate:
        """
        Record one progress sample and return the estimate after it.

        Rate is units completed since the first sample, divided by elapsed
        time since that sample. Remaining time is leftover units over that
        rate.

        Args:
            current: Units completed so far.
            total: Units the job expects to complete, when known.
            at: Monotonic timestamp of this sample, in seconds.

        Returns:
            The rate/ETA estimate incorporating this sample.
        """
        if self._start_at is None or self._start_current is None:
            self._start_at = at
            self._start_current = current
            return ProgressEstimate(rate_per_second=None, eta_seconds=None)

        elapsed = at - self._start_at
        completed = current - self._start_current
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

    Shared by the TUI progress screen so an ETA reads as a short countdown.

    Args:
        seconds: Duration to format.

    Returns:
        A short, human-readable duration string.
    """
    whole = round(seconds)
    minutes, secs = divmod(whole, 60)
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"
