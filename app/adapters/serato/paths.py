"""Resolve Serato library paths on a mount."""

from pathlib import Path

_SERATO_DIR = "_Serato_"
_DATABASE_V2_NAME = "database V2"
_SUBCRATES_NAME = "Subcrates"


def serato_root_for(mount_path: Path) -> Path:
    """
    Return where _Serato_ belongs under a mount, whether or not it exists yet.

    Args:
        mount_path: Mount root (e.g. /media/$USER/MY_USB).

    Returns:
        Path to _Serato_.
    """
    return mount_path.resolve() / _SERATO_DIR


def database_v2_path(serato_root: Path) -> Path:
    """
    Return the database V2 path for a Serato library root.

    Args:
        serato_root: Path to the _Serato_ directory.

    Returns:
        Path to database V2 (may not exist yet).
    """
    return serato_root / _DATABASE_V2_NAME


def resolve_serato_library(mount_path: Path) -> tuple[Path, Path] | None:
    """
    Find the Serato library root and database V2 on a mount.

    Args:
        mount_path: Mount root (e.g. /media/$USER/MY_USB).

    Returns:
        Tuple of (serato_root, database_v2_path), or None if not found.
        A zero-byte ``database V2`` is treated as missing.
    """
    serato_root = serato_root_for(mount_path)
    database = database_v2_path(serato_root)
    if serato_root.is_dir() and database.is_file() and database.stat().st_size > 0:
        return serato_root, database
    return None


def subcrates_dir(serato_root: Path) -> Path:
    """
    Return the Subcrates directory for a Serato library root.

    Args:
        serato_root: Path to the _Serato_ directory.

    Returns:
        Path to Subcrates/ (may not exist yet).
    """
    return serato_root / _SUBCRATES_NAME


def list_crate_files(serato_root: Path) -> list[Path]:
    """
    List .crate files under Subcrates/ (non-recursive).

    Args:
        serato_root: Path to _Serato_ directory.

    Returns:
        Sorted list of absolute paths to .crate files.
    """
    subcrates = subcrates_dir(serato_root)
    if not subcrates.is_dir():
        return []
    return sorted(path.resolve() for path in subcrates.glob("*.crate") if path.is_file())
