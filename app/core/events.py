"""Structured discovery events."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class LibraryScanStarted:
    """
    Emitted when a scan operation begins.

    Attributes:
        mounts: Mount paths that will be scanned.
        timestamp: ISO-8601 UTC timestamp.
    """

    mounts: tuple[str, ...]
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class LibraryDetected:
    """
    Emitted when a DJ library is detected on a mount.

    Attributes:
        path: Detected library path.
        library_type: Vendor type string.
        confidence: Heuristic confidence score.
        mount_path: Parent mount path.
        indicators: Detection marker descriptions.
        timestamp: ISO-8601 UTC timestamp.
    """

    path: str
    library_type: str
    confidence: float
    mount_path: str
    indicators: tuple[str, ...]
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobStarted:
    """
    Emitted when a background job begins execution.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        parameters: Input parameters for the job.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    parameters: dict[str, Any]
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobProgress:
    """
    Emitted to report incremental job progress.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        message: Human-readable progress description.
        current: Optional completed units.
        total: Optional total units.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    message: str
    current: int | None = None
    total: int | None = None
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobCompleted:
    """
    Emitted when a background job finishes successfully.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobFailed:
    """
    Emitted when a background job terminates with an error.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        error: Error message string.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    error: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class JobCancelled:
    """
    Emitted when a background job is cancelled.

    Attributes:
        job_id: Unique job identifier.
        job_type: Registered handler key.
        timestamp: ISO-8601 UTC timestamp.
    """

    job_id: str
    job_type: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class LibraryScanCompleted:
    """
    Emitted when a scan operation finishes.

    Attributes:
        mount_count: Number of mounts scanned.
        library_count: Number of libraries detected.
        timestamp: ISO-8601 UTC timestamp.
    """

    mount_count: int
    library_count: int
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)
