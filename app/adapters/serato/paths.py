"""Resolve Serato library paths on a mount."""

from pathlib import Path

_SERATO_DIR = "_Serato_"
_DATABASE_V2_NAME = "database V2"
_SUBCRATES_NAME = "Subcrates"


def resolve_serato_library(mount_path: Path) -> tuple[Path, Path] | None:
    """
    Find the Serato library root and database V2 on a mount.

    Args:
        mount_path: Mount root (e.g. /mnt/usb).

    Returns:
        Tuple of (serato_root, database_v2_path), or None if not found.
    """
    root = mount_path.resolve()
    serato_root = root / _SERATO_DIR
    database = serato_root / _DATABASE_V2_NAME
    if serato_root.is_dir() and database.is_file():
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
