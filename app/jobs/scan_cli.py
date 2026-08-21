"""Convenience helpers for running jobs from synchronous callers."""

import asyncio
from typing import Any

from app.core.event_bus import EventBus
from app.jobs.exceptions import JobCancelledError
from app.jobs.models import JobState
from app.jobs.runner import JobRunner
from app.jobs.store import JobStore
from app.services.scan_service import ScanResult
from app.storage.mounts import resolve_mount_path


def _default_runner(*, store: JobStore | None = None, bus: EventBus | None = None) -> JobRunner:
    """
    Build a JobRunner with persisted job metadata.

    Args:
        store: Optional JobStore override for tests.
        bus: Optional EventBus for normalized event delivery.

    Returns:
        JobRunner backed by a JobStore.
    """
    return JobRunner(store=store or JobStore(), bus=bus)


async def run_scan_async(
    *,
    mount: str | None = None,
    store: JobStore | None = None,
    bus: EventBus | None = None,
) -> ScanResult:
    """
    Run a scan job to completion via JobRunner.

    Args:
        mount: Optional single mount path to scan.

    Returns:
        ScanResult from the completed scan job.

    Raises:
        JobCancelledError: When the scan job is cancelled.
        RuntimeError: When the scan job fails with an error.
    """
    # Validate before scheduling: a bad path is user error, not a job failure.
    # Letting it through would persist a failed job record and log a traceback
    # for what is really "you typed the wrong mount".
    if mount is not None:
        resolve_mount_path(mount)

    runner = _default_runner(store=store, bus=bus)
    job_id = await runner.start("scan", {"mount": mount})
    record = await runner.wait(job_id)
    return _result_from_record(record)


async def resume_scan_async(
    job_id: str,
    *,
    store: JobStore | None = None,
    bus: EventBus | None = None,
) -> ScanResult:
    """
    Resume a failed or cancelled scan job from persisted metadata.

    Args:
        job_id: Persisted job identifier.

    Returns:
        ScanResult from the completed resumed scan job.

    Raises:
        JobCancelledError: When the scan job is cancelled.
        RuntimeError: When the scan job fails with an error.
    """
    runner = _default_runner(store=store, bus=bus)
    await runner.resume(job_id)
    record = await runner.wait(job_id)
    return _result_from_record(record)


def run_scan_job_sync(
    *,
    mount: str | None = None,
    store: JobStore | None = None,
    bus: EventBus | None = None,
) -> ScanResult:
    """
    Blocking wrapper for run_scan_async suitable for CLI use.

    Args:
        mount: Optional single mount path to scan.

    Returns:
        ScanResult from the completed scan job.

    Raises:
        JobCancelledError: When the scan job is cancelled.
        RuntimeError: When the scan job fails with an error.
        OSError: Propagated from underlying mount or filesystem I/O.
    """
    return asyncio.run(run_scan_async(mount=mount, store=store, bus=bus))


def resume_scan_job_sync(
    job_id: str,
    *,
    store: JobStore | None = None,
    bus: EventBus | None = None,
) -> ScanResult:
    """
    Blocking wrapper for resume_scan_async suitable for CLI use.

    Args:
        job_id: Persisted job identifier.

    Returns:
        ScanResult from the completed resumed scan job.

    Raises:
        JobCancelledError: When the scan job is cancelled.
        RuntimeError: When the scan job fails with an error.
    """
    return asyncio.run(resume_scan_async(job_id, store=store, bus=bus))


def _result_from_record(record: Any) -> ScanResult:
    """
    Extract a successful job result or raise for terminal failure states.

    Args:
        record: Completed JobRecord from JobRunner.wait().

    Returns:
        The job result value when state is completed.

    Raises:
        JobCancelledError: When the job was cancelled.
        RuntimeError: When the job failed.
    """
    if record.state == JobState.COMPLETED:
        return record.result
    if record.state == JobState.CANCELLED:
        raise JobCancelledError(record.job_id)
    if record.state == JobState.FAILED:
        raise RuntimeError(record.error or "Job failed")
    raise RuntimeError(f"Unexpected job state: {record.state}")
