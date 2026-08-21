"""Async job runner."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.event_bus import EventBus
from app.core.events import JobCancelled, JobCompleted, JobFailed, JobStarted
from app.jobs.exceptions import JobCancelledError, JobNotFoundError, UnknownJobTypeError
from app.jobs.models import JobContext, JobRecord, JobState
from app.jobs.registry import JobRegistry

logger = structlog.get_logger(__name__)

JobHandler = Callable[[JobContext], Awaitable[Any]]


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


class JobRunner:
    """
    Schedules asyncio tasks for registered job types.

    Blocking adapter and storage I/O runs inside handlers via
    ``asyncio.to_thread``.
    """

    def __init__(
        self,
        handlers: dict[str, JobHandler],
        *,
        registry: JobRegistry | None = None,
        bus: EventBus | None = None,
    ) -> None:
        """
        Initialize a runner.

        Args:
            handlers: Job type to coroutine handler map.
            registry: Job record store; defaults to a new in-memory registry.
            bus: Optional EventBus for event delivery.
        """
        self._handlers = dict(handlers)
        self._registry = registry or JobRegistry()
        self._bus = bus
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._cancel_flags: dict[str, bool] = {}

    async def start(self, job_type: str, parameters: dict[str, Any] | None = None) -> str:
        """
        Create and schedule a job.

        Args:
            job_type: Registered handler key.
            parameters: Job input parameters.

        Returns:
            Job id string.

        Raises:
            UnknownJobTypeError: When no handler is registered.
        """
        if job_type not in self._handlers:
            raise UnknownJobTypeError(job_type)

        job_id = uuid.uuid4().hex[:12]
        params = dict(parameters or {})
        self._registry.add(
            JobRecord(
                job_id=job_id,
                job_type=job_type,
                state=JobState.PENDING,
                parameters=params,
            )
        )
        self._cancel_flags[job_id] = False
        self._tasks[job_id] = asyncio.create_task(
            self._execute(job_id, job_type, params),
            name=f"job-{job_type}-{job_id}",
        )
        return job_id

    async def wait(self, job_id: str) -> JobRecord:
        """
        Await job completion and return the final record.

        Args:
            job_id: Job identifier returned from start().

        Returns:
            Final JobRecord with terminal state.

        Raises:
            JobNotFoundError: When the job id is unknown.
        """
        try:
            task = self._tasks[job_id]
        except KeyError as exc:
            raise JobNotFoundError(job_id) from exc

        await task
        return self._registry.get(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        """
        Request cooperative cancellation for a running job.

        Args:
            job_id: Job identifier to cancel.

        Returns:
            Updated JobRecord.

        Raises:
            JobNotFoundError: When the job id is unknown.
        """
        record = self._registry.get(job_id)
        self._cancel_flags[job_id] = True
        record.cancel_requested = True
        record.updated_at = _utc_now()
        if record.state == JobState.PENDING:
            record.state = JobState.CANCELLED
        return record

    def _publish(self, event: Any) -> None:
        """Dispatch an event to the bus."""
        if self._bus is not None:
            self._bus.publish(event)

    async def _execute(self, job_id: str, job_type: str, parameters: dict[str, Any]) -> None:
        """
        Run a job handler and update registry state.

        Args:
            job_id: Job identifier.
            job_type: Handler lookup key.
            parameters: Job input parameters.
        """
        handler = self._handlers[job_type]
        record = self._registry.update_state(job_id, JobState.RUNNING)
        record.updated_at = _utc_now()
        self._publish(JobStarted(job_id=job_id, job_type=job_type, parameters=parameters))

        ctx = JobContext(
            job_id=job_id,
            job_type=job_type,
            parameters=parameters,
            cancel_event=lambda: self._cancel_flags.get(job_id, False),
            emit=self._publish,
        )

        try:
            result = await handler(ctx)
        except JobCancelledError:
            self._finish(job_id, JobState.CANCELLED)
            self._publish(JobCancelled(job_id=job_id, job_type=job_type))
            return
        except Exception as exc:
            self._finish(job_id, JobState.FAILED, error=str(exc))
            self._publish(JobFailed(job_id=job_id, job_type=job_type, error=str(exc)))
            logger.exception("job_failed", job_id=job_id, job_type=job_type)
            return

        if self._cancel_flags.get(job_id, False):
            self._finish(job_id, JobState.CANCELLED)
            self._publish(JobCancelled(job_id=job_id, job_type=job_type))
            return

        self._finish(job_id, JobState.COMPLETED, result=result)
        self._publish(JobCompleted(job_id=job_id, job_type=job_type))

    def _finish(self, job_id: str, state: JobState, **fields: Any) -> None:
        """Apply a terminal state to a job record."""
        record = self._registry.update_state(job_id, state, **fields)
        if state == JobState.CANCELLED:
            record.cancel_requested = True
        record.updated_at = _utc_now()
