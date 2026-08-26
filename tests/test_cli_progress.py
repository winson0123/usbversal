"""Tests for CLI progress rendering."""

from io import StringIO
from unittest.mock import patch

from app.cli.progress import CliProgressRenderer
from app.core.event_envelope import Event


def test_cli_progress_renders_job_progress(capsys) -> None:
    """CliProgressRenderer prints progress lines to stderr."""
    renderer = CliProgressRenderer(min_interval_s=0.0, verbose=True)
    renderer(
        Event(
            type="job.progress",
            job_id="abc",
            payload={"message": "Scan starting", "current": 0, "total": 1},
        )
    )
    captured = capsys.readouterr()
    assert "[0/1] Scan starting" in captured.err


def test_cli_progress_ignores_non_progress_events(capsys) -> None:
    """Non job.progress events produce no output."""
    renderer = CliProgressRenderer(min_interval_s=0.0, verbose=True)
    renderer(Event(type="job.started", job_id="abc", payload={}))
    captured = capsys.readouterr()
    assert captured.err == ""


def test_cli_progress_shows_rate_and_eta_once_it_has_two_samples(capsys) -> None:
    """A second event for the same job gets a rate and an ETA appended."""

    def event(current: int) -> Event:
        return Event(
            type="job.progress",
            job_id="abc",
            payload={"message": "Syncing", "current": current, "total": 100},
        )

    renderer = CliProgressRenderer(min_interval_s=0.0, verbose=True)
    with patch("app.cli.progress.time.monotonic", side_effect=[0.0, 10.0]):
        renderer(event(0))
        renderer(event(20))

    captured = capsys.readouterr()
    assert "2.0/s" in captured.err
    assert "eta 40s" in captured.err


def test_cli_progress_omits_rate_on_the_first_sample(capsys) -> None:
    """A single sample has no interval to derive a rate from."""
    renderer = CliProgressRenderer(min_interval_s=0.0, verbose=True)
    renderer(
        Event(
            type="job.progress",
            job_id="abc",
            payload={"message": "Syncing", "current": 0, "total": 100},
        )
    )

    captured = capsys.readouterr()
    assert "/s" not in captured.err


def test_cli_progress_tracks_separate_jobs_independently(capsys) -> None:
    """Two interleaved jobs do not pollute each other's rate estimate."""
    renderer = CliProgressRenderer(min_interval_s=0.0, verbose=True)
    with patch("app.cli.progress.time.monotonic", side_effect=[0.0, 0.0, 10.0]):
        renderer(Event(type="job.progress", job_id="a", payload={"current": 0, "total": 10}))
        renderer(Event(type="job.progress", job_id="b", payload={"current": 0, "total": 10}))
        renderer(Event(type="job.progress", job_id="a", payload={"current": 5, "total": 10}))

    captured = capsys.readouterr()
    assert "0.5/s" in captured.err


def test_cli_progress_throttles_rapid_events() -> None:
    """Throttled renderer suppresses rapid consecutive events."""
    renderer = CliProgressRenderer(min_interval_s=10.0, verbose=False)
    event = Event(type="job.progress", job_id="abc", payload={"message": "A"})
    with StringIO() as stderr:
        import sys

        original = sys.stderr
        sys.stderr = stderr
        try:
            renderer(event)
            renderer(event)
        finally:
            sys.stderr = original
        output = stderr.getvalue()
    assert output.count("A") == 1
