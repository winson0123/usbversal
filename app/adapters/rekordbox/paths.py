"""Resolve Rekordbox database paths on a mount."""

from pathlib import Path

from app.core.domain import RekordboxDbFormat

# Standard export layout under a mount root.
_REKORDBOX_DIR = Path("PIONEER/rekordbox")
_ONE_LIBRARY = _REKORDBOX_DIR / "exportLibrary.db"
_DEVICE_SQL = _REKORDBOX_DIR / "export.pdb"


def resolve_rekordbox_database(mount_path: Path) -> tuple[Path, RekordboxDbFormat] | None:
    """
    Find the best Rekordbox database file under a mount.

    Prefers One Library (exportLibrary.db) over classic DeviceSQL (export.pdb).

    Args:
        mount_path: Mount root (e.g. /media/$USER/MY_USB).

    Returns:
        Tuple of (database file path, format enum), or None if not found.
    """
    root = mount_path.resolve()
    one_lib = root / _ONE_LIBRARY
    if one_lib.is_file():
        return one_lib, RekordboxDbFormat.ONE_LIBRARY

    device_sql = root / _DEVICE_SQL
    if device_sql.is_file():
        return device_sql, RekordboxDbFormat.DEVICE_SQL

    return None
