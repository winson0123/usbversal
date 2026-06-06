"""Tests for the in-process event bus."""

from app.core.event_bus import EventBus
from app.core.event_envelope import Event
from app.core.events import JobProgress


def test_publish_delivers_wrapped_event() -> None:
    """Subscribers receive normalized Event envelopes."""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)

    bus.publish(
        JobProgress(
            job_id="job1",
            job_type="scan",
            message="Working",
            current=1,
            total=2,
        )
    )

    assert len(received) == 1
    assert received[0].type == "job.progress"
    assert received[0].job_id == "job1"
    assert received[0].payload["message"] == "Working"


def test_subscriber_failure_is_isolated() -> None:
    """One failing subscriber does not block others."""
    bus = EventBus()
    seen: list[str] = []

    def failing(_event: Event) -> None:
        raise RuntimeError("boom")

    bus.subscribe(failing)
    bus.subscribe(lambda event: seen.append(event.type))

    bus.publish(
        JobProgress(
            job_id="job1",
            job_type="scan",
            message="Working",
        )
    )

    assert seen == ["job.progress"]
