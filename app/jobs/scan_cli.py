"""Convenience helpers for running jobs from synchronous callers."""

import asyncio
from typing import Any

from app.jobs.exceptions import JobCancelledError
from app.jobs.models import JobState
from app.jobs.runner import JobRunner
from app.services.scan_service import ScanResult


async def run_scan_async(*, mount: str | None = None) -> ScanResult:
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
    runner = JobRunner()
    job_id = await runner.start("scan", {"mount": mount})
    record = await runner.wait(job_id)
    return _result_from_record(record)


def run_scan_job_sync(*, mount: str | None = None) -> ScanResult:
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
    return asyncio.run(run_scan_async(mount=mount))


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
