"""Tests for normalized event envelopes."""

from app.core.event_envelope import Event, wrap_event
from app.core.events import JobProgress


def test_wrap_job_progress_event() -> None:
    """JobProgress maps to job.progress with payload fields."""
    raw = JobProgress(
        job_id="abc",
        job_type="scan",
        message="Scan starting",
        current=0,
        total=1,
    )
    envelope = wrap_event(raw)
    assert envelope.type == "job.progress"
    assert envelope.job_id == "abc"
    assert envelope.payload["message"] == "Scan starting"
    assert envelope.payload["current"] == 0


def test_event_to_dict() -> None:
    """Event envelope serializes to a plain dictionary."""
    event = Event(type="job.started", job_id="x", payload={"job_type": "scan"})
    data = event.to_dict()
    assert data["type"] == "job.started"
    assert data["job_id"] == "x"
