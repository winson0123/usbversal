"""Error taxonomy for frontends.

Job lifecycle errors live in ``app.jobs.exceptions``.
"""

from app.adapters.base import (
    AdapterError,
    DatabaseNotFoundError,
    SeratoLibraryNotFoundError,
    UnsupportedDatabaseError,
)
from app.adapters.serato.writer import CrateExistsError
from app.core.apply_plan import ApplyPlanError
from app.services.migration_service import (
    MigrationError,
    PlaylistNotFoundError,
    SeratoLibraryRequiredError,
)
from app.storage.rollback import (
    BackupNotFoundError,
    BackupVerificationError,
    MountMismatchError,
    RollbackError,
)

__all__ = [
    "AdapterError",
    "ApplyPlanError",
    "BackupNotFoundError",
    "BackupVerificationError",
    "CrateExistsError",
    "DatabaseNotFoundError",
    "MigrationError",
    "MountMismatchError",
    "PlaylistNotFoundError",
    "RollbackError",
    "SeratoLibraryNotFoundError",
    "SeratoLibraryRequiredError",
    "UnsupportedDatabaseError",
]
