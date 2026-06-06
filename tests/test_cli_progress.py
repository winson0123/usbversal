"""Tests for CLI progress rendering."""

from io import StringIO

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
