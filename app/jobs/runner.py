"""Async job runner and handler registry."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.event_bus import EventBus
from app.core.events import JobCancelled, JobCompleted, JobFailed, JobStarted
from app.jobs.exceptions import JobCancelledError, JobNotFoundError, UnknownJobTypeError
from app.jobs.models import JobCheckpoint, JobContext, JobRecord, JobState
from app.jobs.registry import JobRegistry
from app.jobs.scan_job import JobHandler, run_scan_job
from app.jobs.store import JobStore

logger = structlog.get_logger(__name__)

DEFAULT_HANDLERS: dict[str, JobHandler] = {
    "scan": run_scan_job,
}


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


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
        store: JobStore | None = None,
        bus: EventBus | None = None,
    ) -> None:
        """
        Initialize a runner with optional registry and handlers.

        Args:
            registry: Job record store; defaults to a new in-memory registry.
            handlers: Job type to coroutine handler map; defaults to built-ins.
            store: Optional JobStore for persistence and cross-process cancel.
            bus: Optional EventBus for normalized event delivery.
        """
        self._registry = registry or JobRegistry()
        self._handlers = handlers if handlers is not None else DEFAULT_HANDLERS.copy()
        self._store = store
        self._bus = bus
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._cancel_flags: dict[str, bool] = {}
        if self._store is not None:
            self._store.recover_interrupted()

    async def start(
        self,
        job_type: str,
        parameters: dict[str, Any] | None = None,
        *,
        job_id: str | None = None,
        checkpoint: JobCheckpoint | None = None,
    ) -> str:
        """
        Create and schedule a job.

        Args:
            job_type: Registered handler key.
            parameters: Job input parameters.
            job_id: Optional existing job id (used by resume).
            checkpoint: Optional checkpoint metadata for resumed jobs.

        Returns:
            Job id string.

        Raises:
            UnknownJobTypeError: When no handler is registered.
        """
        if job_type not in self._handlers:
            raise UnknownJobTypeError(job_type)

        new_id = job_id or uuid.uuid4().hex[:12]
        params = dict(parameters or {})
        if checkpoint is not None:
            params["_checkpoint"] = checkpoint

        record = JobRecord(
            job_id=new_id,
            job_type=job_type,
            state=JobState.PENDING,
            parameters=params,
            checkpoint=checkpoint or JobCheckpoint(),
        )
        self._registry.add(record)
        self._persist(record)
        self._cancel_flags[new_id] = False

        self._tasks[new_id] = asyncio.create_task(
            self._execute(new_id, job_type, params),
            name=f"job-{job_type}-{new_id}",
        )
        return new_id

    async def resume(self, job_id: str) -> str:
        """
        Resume a failed or cancelled job from persisted metadata.

        Args:
            job_id: Job identifier to resume.

        Returns:
            Same job id string now scheduled for execution.

        Raises:
            JobNotFoundError: When the job is not on disk.
            JobNotResumableError: When the job state does not allow resume.
        """
        if self._store is None:
            raise RuntimeError("JobStore is required for resume")

        record = self._store.prepare_resume(job_id)
        self._registry.add(record)
        params = dict(record.parameters)
        params["_checkpoint"] = record.checkpoint
        self._cancel_flags[job_id] = False

        self._tasks[job_id] = asyncio.create_task(
            self._execute(job_id, record.job_type, params),
            name=f"job-{record.job_type}-{job_id}",
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
        self._persist(record)
        return record

    def _persist(self, record: JobRecord) -> None:
        """Write a record to the optional JobStore."""
        if self._store is None:
            return
        self._store.save(record)

    def _is_cancelled(self, job_id: str) -> bool:
        """Return True when in-memory or persisted cancel was requested."""
        if self._cancel_flags.get(job_id, False):
            return True
        if self._store is not None and self._store.is_cancel_requested(job_id):
            self._cancel_flags[job_id] = True
            return True
        return False

    def _save_checkpoint(
        self,
        job_id: str,
        *,
        step_index: int,
        step_name: str,
        partial_results: dict[str, Any] | None = None,
    ) -> None:
        """Update checkpoint fields on the in-memory and persisted record."""
        record = self._registry.get(job_id)
        record.checkpoint.step_index = step_index
        record.checkpoint.step_name = step_name
        if partial_results is not None:
            record.checkpoint.partial_results = partial_results
        record.updated_at = _utc_now()
        self._persist(record)

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
        self._persist(record)
        self._publish(JobStarted(job_id=job_id, job_type=job_type, parameters=parameters))

        ctx = JobContext(
            job_id=job_id,
            job_type=job_type,
            parameters=parameters,
            cancel_event=lambda: self._is_cancelled(job_id),
            emit=self._publish,
            save_checkpoint=lambda **kwargs: self._save_checkpoint(job_id, **kwargs),
        )

        try:
            result = await handler(ctx)
        except JobCancelledError:
            record = self._registry.update_state(job_id, JobState.CANCELLED)
            record.cancel_requested = True
            record.updated_at = _utc_now()
            self._persist(record)
            self._publish(JobCancelled(job_id=job_id, job_type=job_type))
            return
        except Exception as exc:
            message = str(exc)
            record = self._registry.update_state(job_id, JobState.FAILED, error=message)
            record.updated_at = _utc_now()
            self._persist(record)
            self._publish(JobFailed(job_id=job_id, job_type=job_type, error=message))
            logger.exception("job_failed", job_id=job_id, job_type=job_type)
            return

        if self._is_cancelled(job_id):
            record = self._registry.update_state(job_id, JobState.CANCELLED)
            record.cancel_requested = True
            record.updated_at = _utc_now()
            self._persist(record)
            self._publish(JobCancelled(job_id=job_id, job_type=job_type))
            return

        record = self._registry.update_state(job_id, JobState.COMPLETED, result=result)
        record.updated_at = _utc_now()
        self._persist(record)
        self._publish(JobCompleted(job_id=job_id, job_type=job_type))
