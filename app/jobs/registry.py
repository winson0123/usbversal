"""In-memory job registry."""

from app.jobs.exceptions import JobNotFoundError
from app.jobs.models import JobRecord, JobState

_UNSET = object()


class JobRegistry:
    """
    Maps job ids to job records for a single process.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._records: dict[str, JobRecord] = {}

    def add(self, record: JobRecord) -> None:
        """
        Store a new job record.

        Args:
            record: Job record to register.
        """
        self._records[record.job_id] = record

    def get(self, job_id: str) -> JobRecord:
        """
        Return a job record by id.

        Args:
            job_id: Job identifier.

        Returns:
            Matching JobRecord.

        Raises:
            JobNotFoundError: When no record exists for the id.
        """
        try:
            return self._records[job_id]
        except KeyError as exc:
            raise JobNotFoundError(job_id) from exc

    def update_state(
        self,
        job_id: str,
        state: JobState,
        *,
        result: object = _UNSET,
        error: str | None = _UNSET,
    ) -> JobRecord:
        """
        Update lifecycle fields on an existing record.

        Args:
            job_id: Job identifier.
            state: New lifecycle state.
            result: Optional successful result value.
            error: Optional error message.

        Returns:
            Updated JobRecord.

        Raises:
            JobNotFoundError: When no record exists for the id.
        """
        record = self.get(job_id)
        record.state = state
        if result is not _UNSET:
            record.result = result
        if error is not _UNSET:
            record.error = error
        return record

    def list_all(self) -> list[JobRecord]:
        """
        Return all registered job records.

        Returns:
            List of JobRecord instances in insertion order.
        """
        return list(self._records.values())
