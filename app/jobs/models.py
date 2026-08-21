"""Job state models and execution context."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.core.events import JobProgress


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


class JobState(StrEnum):
    """Lifecycle states for a background job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobRecord:
    """
    Record for a single job execution.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        state: Current lifecycle state.
        parameters: Input parameters passed at job creation.
        result: Successful return value when completed.
        error: Error message when failed.
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last update timestamp.
        cancel_requested: Whether cancellation was requested.
    """

    job_id: str
    job_type: str
    state: JobState
    parameters: dict[str, Any]
    result: Any = None
    error: str | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    cancel_requested: bool = False


@dataclass
class JobContext:
    """
    Runtime context passed to async job handlers.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        parameters: Input parameters for the job.
        cancel_event: Returns True when cancellation is requested.
        emit: Optional callback for structured events.
    """

    job_id: str
    job_type: str
    parameters: dict[str, Any]
    cancel_event: Callable[[], bool]
    emit: Callable[[Any], None] | None = None

    def check_cancelled(self) -> None:
        """
        Raise JobCancelledError if cancellation was requested.

        Raises:
            JobCancelledError: When the job cancel flag is set.
        """
        from app.jobs.exceptions import JobCancelledError

        if self.cancel_event():
            raise JobCancelledError(self.job_id)

    def progress(
        self,
        message: str,
        *,
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        """
        Emit a job progress event.

        Args:
            message: Human-readable progress description.
            current: Optional completed units.
            total: Optional total units.
        """
        if self.emit is None:
            return
        self.emit(
            JobProgress(
                job_id=self.job_id,
                job_type=self.job_type,
                message=message,
                current=current,
                total=total,
            )
        )
