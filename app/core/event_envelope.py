"""Normalized event envelope for the in-process event bus."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.events import (
    JobCancelled,
    JobCompleted,
    JobFailed,
    JobProgress,
    JobStarted,
)

EVENT_TYPE_BY_CLASS: dict[type, str] = {
    JobStarted: "job.started",
    JobProgress: "job.progress",
    JobCompleted: "job.completed",
    JobFailed: "job.failed",
    JobCancelled: "job.cancelled",
}


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Event:
    """
    Normalized event envelope published on the event bus.

    Attributes:
        type: Dot-separated event category (e.g. ``job.progress``).
        job_id: Optional job identifier when the event belongs to a job.
        payload: Event-specific data dictionary.
        timestamp: ISO-8601 UTC timestamp.
    """

    type: str
    job_id: str | None
    payload: dict[str, Any]
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the envelope to a plain dictionary.

        Returns:
            JSON-serializable dict with type, job_id, payload, and timestamp.
        """
        return asdict(self)


def wrap_event(raw: Any) -> Event:
    """
    Wrap a structured dataclass event in a normalized Event envelope.

    Args:
        raw: Event dataclass instance with optional ``to_dict()`` and ``job_id``.

    Returns:
        Event envelope with mapped type string and payload dict.
    """
    if isinstance(raw, Event):
        return raw

    event_type = EVENT_TYPE_BY_CLASS.get(type(raw), f"event.{type(raw).__name__.lower()}")
    payload = raw.to_dict() if hasattr(raw, "to_dict") else {"value": raw}
    job_id = getattr(raw, "job_id", None)
    timestamp = getattr(raw, "timestamp", _utc_now())
    return Event(type=event_type, job_id=job_id, payload=payload, timestamp=timestamp)
