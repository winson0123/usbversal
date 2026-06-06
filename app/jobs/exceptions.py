"""Job orchestration exceptions."""


class JobError(Exception):
    """Base class for job-related errors."""


class JobNotFoundError(JobError):
    """Raised when a job id is not in the registry."""

    def __init__(self, job_id: str) -> None:
        """
        Initialize with the missing job id.

        Args:
            job_id: Identifier that was not found.
        """
        super().__init__(f"Job not found: {job_id}")
        self.job_id = job_id


class UnknownJobTypeError(JobError):
    """Raised when no handler is registered for a job type."""

    def __init__(self, job_type: str) -> None:
        """
        Initialize with the unknown job type.

        Args:
            job_type: Job type string with no registered handler.
        """
        super().__init__(f"Unknown job type: {job_type}")
        self.job_type = job_type


class JobCancelledError(JobError):
    """Raised when a job is cancelled before or during execution."""

    def __init__(self, job_id: str) -> None:
        """
        Initialize with the cancelled job id.

        Args:
            job_id: Identifier of the cancelled job.
        """
        super().__init__(f"Job cancelled: {job_id}")
        self.job_id = job_id


class JobNotResumableError(JobError):
    """Raised when a job cannot be resumed from its current state."""

    def __init__(self, job_id: str, state: str) -> None:
        """
        Initialize with the job id and current state.

        Args:
            job_id: Identifier of the job.
            state: Current state string that blocks resume.
        """
        super().__init__(f"Job {job_id} is not resumable (state={state})")
        self.job_id = job_id
        self.state = state
