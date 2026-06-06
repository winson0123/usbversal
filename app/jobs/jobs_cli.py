"""CLI-facing job list, cancel, and resume helpers."""

from app.jobs.serialization import record_summary
from app.jobs.store import JobStore


def list_persisted_jobs(*, store: JobStore | None = None) -> list[dict]:
    """
    Return summaries of all persisted jobs.

    Args:
        store: Optional JobStore override for tests.

    Returns:
        List of job summary dicts sorted by updated_at descending.
    """
    job_store = store or JobStore()
    job_store.recover_interrupted()
    return [record_summary(record) for record in job_store.list_all()]


def cancel_persisted_job(job_id: str, *, store: JobStore | None = None) -> dict:
    """
    Request cancellation for a persisted job.

    Args:
        job_id: Job identifier.
        store: Optional JobStore override for tests.

    Returns:
        Summary dict for the updated job record.

    Raises:
        JobNotFoundError: When the job file does not exist.
    """
    job_store = store or JobStore()
    record = job_store.request_cancel(job_id)
    return record_summary(record)


def resume_persisted_job(job_id: str, *, store: JobStore | None = None) -> dict:
    """
    Resume a failed or cancelled job and return its final summary.

    Scan jobs re-run discovery idempotently from persisted parameters.

    Args:
        job_id: Job identifier.
        store: Optional JobStore override for tests.

    Returns:
        Summary dict including final state after execution.

    Raises:
        JobNotFoundError: When the job file does not exist.
        JobNotResumableError: When the job state does not allow resume.
        JobCancelledError: When the resumed job is cancelled.
        RuntimeError: When the resumed job fails.
    """
    from app.jobs.scan_cli import resume_scan_job_sync

    job_store = store or JobStore()
    record = job_store.load(job_id)
    if record.job_type != "scan":
        raise RuntimeError(f"Resume not implemented for job type: {record.job_type}")

    resume_scan_job_sync(job_id, store=job_store)
    return record_summary(job_store.load(job_id))
