"""Deriving a rate and ETA from a job's progress events over time."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressEstimate:
    """
    Rate and time-to-completion derived from a job's progress so far.

    Attributes:
        rate_per_second: Units completed per second, averaged over the run so
            far. None until progress has actually advanced.
        eta_seconds: Estimated seconds remaining at that rate. None when the
            total is unknown, or the run has not advanced yet.
    """

    rate_per_second: float | None
    eta_seconds: float | None


class ProgressRateTracker:
    """
    Turns successive ``current``/``total`` samples into a rate and an ETA.

    Averages over the whole run rather than only the most recent interval:
    a sync job's per-track cost varies (a big MP3's tag rewrite next to a
    small WAV's), so a single slow or fast step should not swing the
    estimate the way a most-recent-interval rate would.
    """

    def __init__(self) -> None:
        self._start_current: int | None = None
        self._start_at: float | None = None

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
        if self._start_current is None:
            self._start_current = current
            self._start_at = at

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
