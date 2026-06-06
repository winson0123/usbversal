"""Async job runner and handler registry."""

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

import structlog

from app.core.events import JobCancelled, JobCompleted, JobFailed, JobStarted
from app.jobs.exceptions import JobCancelledError, JobNotFoundError, UnknownJobTypeError
from app.jobs.models import JobContext, JobRecord, JobState
from app.jobs.registry import JobRegistry
from app.jobs.scan_job import JobHandler, run_scan_job

logger = structlog.get_logger(__name__)

DEFAULT_HANDLERS: dict[str, JobHandler] = {
    "scan": run_scan_job,
}


class JobRunner:
    """
    Schedules asyncio tasks for registered job types.

    Blocking adapter and storage I/O should run inside handlers via
    ``asyncio.to_thread`` (see scan job).
    """

    def __init__(
        self,
        *,
        registry: JobRegistry | None = None,
        handlers: dict[str, JobHandler] | None = None,
        emit: Callable[[Any], None] | None = None,
    ) -> None:
        """
        Initialize a runner with optional registry and handlers.

        Args:
            registry: Job record store; defaults to a new in-memory registry.
            handlers: Job type to coroutine handler map; defaults to built-ins.
            emit: Optional callback for job lifecycle and progress events.
        """
        self._registry = registry or JobRegistry()
        self._handlers = handlers if handlers is not None else DEFAULT_HANDLERS.copy()
        self._emit = emit
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._cancel_flags: dict[str, bool] = {}

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """
        Register or replace a job handler.

        Args:
            job_type: Handler lookup key.
            handler: Async callable accepting JobContext.
        """
        self._handlers[job_type] = handler

    async def start(self, job_type: str, parameters: dict[str, Any] | None = None) -> str:
        """
        Create and schedule a job.

        Args:
            job_type: Registered handler key.
            parameters: Job input parameters.

        Returns:
            New job id string.

        Raises:
            UnknownJobTypeError: When no handler is registered.
        """
        if job_type not in self._handlers:
            raise UnknownJobTypeError(job_type)

        job_id = uuid.uuid4().hex[:12]
        params = parameters or {}
        record = JobRecord(
            job_id=job_id,
            job_type=job_type,
            state=JobState.PENDING,
            parameters=params,
        )
        self._registry.add(record)
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

    def cancel(self, job_id: str) -> None:
        """
        Request cooperative cancellation for a running job.

        Args:
            job_id: Job identifier to cancel.

        Raises:
            JobNotFoundError: When the job id is unknown.
        """
        self._registry.get(job_id)
        self._cancel_flags[job_id] = True

    def get(self, job_id: str) -> JobRecord:
        """
        Return the current job record.

        Args:
            job_id: Job identifier.

        Returns:
            Current JobRecord snapshot.
        """
        return self._registry.get(job_id)

    def list_jobs(self) -> list[JobRecord]:
        """
        Return all job records known to this runner.

        Returns:
            List of JobRecord instances.
        """
        return self._registry.list_all()

    def _publish(self, event: Any) -> None:
        """Dispatch an event to the optional emitter."""
        if self._emit is None:
            return
        try:
            self._emit(event)
        except Exception:
            logger.exception("job_event_emit_failed", event_type=type(event).__name__)

    async def _execute(self, job_id: str, job_type: str, parameters: dict[str, Any]) -> None:
        """
        Run a job handler and update registry state.

        Args:
            job_id: Job identifier.
            job_type: Handler lookup key.
            parameters: Job input parameters.
        """
        handler = self._handlers[job_type]
        self._registry.update_state(job_id, JobState.RUNNING)
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
            self._registry.update_state(job_id, JobState.CANCELLED)
            self._publish(JobCancelled(job_id=job_id, job_type=job_type))
            return
        except Exception as exc:
            message = str(exc)
            self._registry.update_state(job_id, JobState.FAILED, error=message)
            self._publish(JobFailed(job_id=job_id, job_type=job_type, error=message))
            logger.exception("job_failed", job_id=job_id, job_type=job_type)
            return

        if self._cancel_flags.get(job_id, False):
            self._registry.update_state(job_id, JobState.CANCELLED)
            self._publish(JobCancelled(job_id=job_id, job_type=job_type))
            return

        self._registry.update_state(job_id, JobState.COMPLETED, result=result)
        self._publish(JobCompleted(job_id=job_id, job_type=job_type))
