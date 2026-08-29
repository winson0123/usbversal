"""Tests for job progress rate and ETA estimation."""

import pytest

from app.jobs.progress_rate import ProgressRateTracker, format_duration


def test_a_single_sample_yields_no_estimate() -> None:
    """One sample has no interval to derive a rate from."""
    tracker = ProgressRateTracker()

    estimate = tracker.observe(current=0, total=10, at=0.0)

    assert estimate.rate_per_second is None
    assert estimate.eta_seconds is None


def test_rate_is_units_over_elapsed_time() -> None:
    """Ten units in five seconds is two units per second."""
    tracker = ProgressRateTracker()
    tracker.observe(current=0, total=100, at=0.0)

    estimate = tracker.observe(current=10, total=100, at=5.0)

    assert estimate.rate_per_second == 2.0


def test_eta_is_remaining_work_over_rate() -> None:
    """At 2 units/s with 80 remaining, the ETA is 40 seconds."""
    tracker = ProgressRateTracker()
    tracker.observe(current=0, total=100, at=0.0)

    estimate = tracker.observe(current=20, total=100, at=10.0)

    assert estimate.eta_seconds == 40.0


def test_rate_uses_every_sample_since_the_first() -> None:
    """A slow first step is not erased by a fast second one."""
    tracker = ProgressRateTracker()
    tracker.observe(current=0, total=100, at=0.0)
    tracker.observe(current=1, total=100, at=10.0)

    estimate = tracker.observe(current=11, total=100, at=15.0)

    # 11 units over 15 seconds, not 10 units over the last 5.
    assert estimate.rate_per_second == pytest.approx(11 / 15)


def test_interleaved_speeds_do_not_swing_eta_by_minutes() -> None:
    """Skip and rewrite tracks interleaved must not make remaining time yo-yo."""
    tracker = ProgressRateTracker()
    tracker.observe(current=0, total=200, at=0.0)
    etas: list[float] = []
    at = 0.0
    for step in range(1, 81):
        at += 2.0 if step % 2 else 0.02
        estimate = tracker.observe(current=step, total=200, at=at)
        assert estimate.eta_seconds is not None
        etas.append(estimate.eta_seconds)

    settled = etas[20:]
    increases = [
        settled[index] - settled[index - 1]
        for index in range(1, len(settled))
        if settled[index] > settled[index - 1]
    ]
    assert increases
    assert max(increases) < 8.0
    assert settled[-1] < settled[0]
    assert estimate.eta_seconds == pytest.approx((200 - 80) * at / 80)


def test_no_total_yields_a_rate_but_no_eta() -> None:
    """A rate can be reported without knowing how much work remains."""
    tracker = ProgressRateTracker()
    tracker.observe(current=0, total=None, at=0.0)

    estimate = tracker.observe(current=5, total=None, at=5.0)

    assert estimate.rate_per_second == 1.0
    assert estimate.eta_seconds is None


def test_no_progress_yet_yields_no_estimate_even_with_elapsed_time() -> None:
    """Time passing with no units completed is not a zero rate, it's unknown."""
    tracker = ProgressRateTracker()
    tracker.observe(current=5, total=100, at=0.0)

    estimate = tracker.observe(current=5, total=100, at=10.0)

    assert estimate.rate_per_second is None
    assert estimate.eta_seconds is None


def test_reaching_the_total_reports_zero_eta() -> None:
    """A completed run has nothing left, not a division by zero."""
    tracker = ProgressRateTracker()
    tracker.observe(current=0, total=10, at=0.0)

    estimate = tracker.observe(current=10, total=10, at=5.0)

    assert estimate.eta_seconds == 0.0


def test_a_second_tracker_starts_with_no_memory_of_the_first() -> None:
    """Trackers do not share state -- each starts fresh from its first sample."""
    first = ProgressRateTracker()
    first.observe(current=0, total=10, at=0.0)
    first.observe(current=5, total=10, at=100.0)

    second = ProgressRateTracker()
    second.observe(current=0, total=10, at=0.0)
    estimate = second.observe(current=1, total=10, at=1.0)

    assert estimate.rate_per_second == 1.0


def test_format_duration_under_a_minute_is_just_seconds() -> None:
    """A short ETA has no minutes component."""
    assert format_duration(45) == "45s"


def test_format_duration_over_a_minute_includes_minutes() -> None:
    """A longer ETA is minutes and seconds."""
    assert format_duration(90) == "1m30s"
