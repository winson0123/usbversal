"""Structured discovery events."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class JobStarted:
    """
    Emitted when a background job begins execution.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        parameters: Input parameters for the job.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    parameters: dict[str, Any]
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobProgress:
    """
    Emitted to report incremental job progress.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        message: Human-readable progress description.
        current: Optional completed units.
        total: Optional total units.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    message: str
    current: int | None = None
    total: int | None = None
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobCompleted:
    """
    Emitted when a background job finishes successfully.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobFailed:
    """
    Emitted when a background job terminates with an error.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        error: Error message string.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    error: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobCancelled:
    """
    Emitted when a background job is cancelled.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)
