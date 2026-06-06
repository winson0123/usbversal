"""Persist job records and cancellation metadata to disk."""

import json
from datetime import UTC, datetime
from pathlib import Path

import structlog

from app.jobs.exceptions import JobNotFoundError, JobNotResumableError
from app.jobs.models import JobRecord, JobState
from app.jobs.paths import get_jobs_dir
from app.jobs.serialization import record_from_dict, record_to_dict

logger = structlog.get_logger(__name__)

RESUMABLE_STATES = frozenset({JobState.FAILED, JobState.CANCELLED})


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


class JobStore:
    """
    Read and write job records as JSON files under the config jobs directory.

    Each job is stored at ``<jobs_dir>/<job_id>.json``.
    """

    def __init__(self, jobs_dir: Path | None = None) -> None:
        """
        Initialize the store with an optional jobs directory override.

        Args:
            jobs_dir: Directory for job JSON files; defaults to get_jobs_dir().
        """
        self._jobs_dir = jobs_dir or get_jobs_dir()

    @property
    def jobs_dir(self) -> Path:
        """Return the jobs directory path."""
        return self._jobs_dir

    def save(self, record: JobRecord) -> None:
        """
        Persist a job record to disk.

        Args:
            record: Job record to write.
        """
        record.updated_at = _utc_now()
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        path = self._job_path(record.job_id)
        payload = record_to_dict(record)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def load(self, job_id: str) -> JobRecord:
        """
        Load a job record from disk.

        Args:
            job_id: Job identifier.

        Returns:
            Loaded JobRecord.

        Raises:
            JobNotFoundError: When the job file does not exist.
        """
        path = self._job_path(job_id)
        if not path.is_file():
            raise JobNotFoundError(job_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return record_from_dict(data)

    def list_all(self) -> list[JobRecord]:
        """
        Return all persisted job records sorted by updated_at descending.

        Returns:
            List of JobRecord instances.
        """
        if not self._jobs_dir.is_dir():
            return []

        records: list[JobRecord] = []
        for path in self._jobs_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(record_from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                logger.warning("job_record_invalid", path=str(path))
        records.sort(key=lambda record: record.updated_at, reverse=True)
        return records

    def request_cancel(self, job_id: str) -> JobRecord:
        """
        Mark a job for cooperative cancellation and persist the request.

        Pending jobs are immediately marked cancelled. Running jobs receive
        a cancel flag checked by the active JobRunner.

        Args:
            job_id: Job identifier.

        Returns:
            Updated JobRecord.

        Raises:
            JobNotFoundError: When the job file does not exist.
        """
        record = self.load(job_id)
        if record.state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
            return record

        record.cancel_requested = True
        record.updated_at = _utc_now()
        if record.state == JobState.PENDING:
            record.state = JobState.CANCELLED
        self.save(record)
        return record

    def recover_interrupted(self) -> list[JobRecord]:
        """
        Mark stale running jobs as failed after process exit.

        Returns:
            List of records that were converted to failed.
        """
        recovered: list[JobRecord] = []
        for record in self.list_all():
            if record.state != JobState.RUNNING:
                continue
            record.state = JobState.FAILED
            record.error = "Interrupted (process exited while running)"
            record.updated_at = _utc_now()
            self.save(record)
            recovered.append(record)
        return recovered

    def prepare_resume(self, job_id: str) -> JobRecord:
        """
        Validate and reset a job record for resume.

        Args:
            job_id: Job identifier.

        Returns:
            Updated JobRecord ready to be scheduled again.

        Raises:
            JobNotFoundError: When the job file does not exist.
            JobNotResumableError: When the job is not in a resumable state.
        """
        record = self.load(job_id)
        if record.state not in RESUMABLE_STATES:
            raise JobNotResumableError(job_id, record.state.value)

        record.state = JobState.PENDING
        record.error = None
        record.cancel_requested = False
        record.updated_at = _utc_now()
        self.save(record)
        return record

    def update_checkpoint(
        self,
        job_id: str,
        *,
        step_index: int | None = None,
        step_name: str | None = None,
        backup_ids: list[str] | None = None,
        partial_results: dict | None = None,
    ) -> JobRecord:
        """
        Update checkpoint fields on a persisted job record.

        Args:
            job_id: Job identifier.
            step_index: Optional new step index.
            step_name: Optional new step name.
            backup_ids: Optional backup id list replacement.
            partial_results: Optional partial results dict replacement.

        Returns:
            Updated JobRecord.

        Raises:
            JobNotFoundError: When the job file does not exist.
        """
        record = self.load(job_id)
        checkpoint = record.checkpoint
        if step_index is not None:
            checkpoint.step_index = step_index
        if step_name is not None:
            checkpoint.step_name = step_name
        if backup_ids is not None:
            checkpoint.backup_ids = backup_ids
        if partial_results is not None:
            checkpoint.partial_results = partial_results
        record.checkpoint = checkpoint
        self.save(record)
        return record

    def is_cancel_requested(self, job_id: str) -> bool:
        """
        Return whether cancellation was requested for a job.

        Args:
            job_id: Job identifier.

        Returns:
            True when cancel_requested is set in the persisted record.
        """
        try:
            return self.load(job_id).cancel_requested
        except JobNotFoundError:
            return False

    def _job_path(self, job_id: str) -> Path:
        """Return the JSON file path for a job id."""
        return self._jobs_dir / f"{job_id}.json"
