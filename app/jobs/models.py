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
class JobCheckpoint:
    """
    Resume metadata for multi-step jobs.

    Attributes:
        step_index: Last successfully completed step index.
        step_name: Human-readable step identifier.
        backup_ids: Backup ids already created for this job.
        partial_results: Paths or other data already processed.
    """

    step_index: int = 0
    step_name: str = ""
    backup_ids: list[str] = field(default_factory=list)
    partial_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobRecord:
    """
    Record for a single job execution.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key (e.g. ``scan``).
        state: Current lifecycle state.
        parameters: Input parameters passed at job creation.
        result: Successful return value when completed.
        error: Error message when failed.
        created_at: ISO-8601 UTC creation timestamp.
        updated_at: ISO-8601 UTC last update timestamp.
        cancel_requested: Whether cancellation was requested.
        checkpoint: Resume metadata for multi-step jobs.
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
    checkpoint: JobCheckpoint = field(default_factory=JobCheckpoint)


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
        save_checkpoint: Optional callback to persist checkpoint metadata.
    """

    job_id: str
    job_type: str
    parameters: dict[str, Any]
    cancel_event: Callable[[], bool]
    emit: Callable[[Any], None] | None = None
    save_checkpoint: Callable[..., None] | None = None

    @property
    def checkpoint(self) -> JobCheckpoint:
        """
        Return checkpoint metadata from parameters when resuming.

        Returns:
            JobCheckpoint from parameters or an empty checkpoint.
        """
        raw = self.parameters.get("_checkpoint")
        if isinstance(raw, JobCheckpoint):
            return raw
        if isinstance(raw, dict):
            return JobCheckpoint(
                step_index=int(raw.get("step_index", 0)),
                step_name=str(raw.get("step_name", "")),
                backup_ids=list(raw.get("backup_ids") or []),
                partial_results=dict(raw.get("partial_results") or {}),
            )
        return JobCheckpoint()

    @property
    def is_resume(self) -> bool:
        """
        Return whether this execution is resuming a prior job attempt.

        Returns:
            True when the ``_resume`` parameter flag is set.
        """
        return bool(self.parameters.get("_resume"))

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

    def update_checkpoint(
        self,
        *,
        step_index: int,
        step_name: str,
        partial_results: dict[str, Any] | None = None,
        backup_ids: list[str] | None = None,
    ) -> None:
        """
        Persist checkpoint metadata for resume.

        Args:
            step_index: Last completed step index.
            step_name: Human-readable step name.
            partial_results: Optional partial results to store.
            backup_ids: Optional backup ids to store.
        """
        if self.save_checkpoint is None:
            return
        self.save_checkpoint(
            step_index=step_index,
            step_name=step_name,
            partial_results=partial_results,
            backup_ids=backup_ids,
        )
