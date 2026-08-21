"""Public error taxonomy for user-facing frontends.

The CLI -- and any future interactive frontend -- needs to map failures onto
messages and exit codes. Importing those exception types from the modules that
happen to raise them would make the frontend depend on adapter and storage
internals, so the taxonomy is re-exported here instead. Frontends import from
this module only.

Job lifecycle errors are deliberately absent: ``jobs`` sits above ``services``,
and frontends may import ``app.jobs.exceptions`` directly.
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
