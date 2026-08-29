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
from app.services.migration_service import (
    MigrationError,
    PlaylistNotFoundError,
    SeratoLibraryRequiredError,
)

__all__ = [
    "AdapterError",
    "CrateExistsError",
    "DatabaseNotFoundError",
    "MigrationError",
    "PlaylistNotFoundError",
    "SeratoLibraryNotFoundError",
    "SeratoLibraryRequiredError",
    "UnsupportedDatabaseError",
]
