"""Resolve Serato library paths on a mount."""

from pathlib import Path

_SERATO_DIR = Path("_Serato_")
_DATABASE_V2 = _SERATO_DIR / "database V2"
_SUBCRATES = _SERATO_DIR / "Subcrates"


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
    database = serato_root / "database V2"
    if serato_root.is_dir() and database.is_file():
        return serato_root, database
    return None


def list_crate_files(serato_root: Path) -> list[Path]:
    """
    List .crate files under Subcrates/ (non-recursive).

    Args:
        serato_root: Path to _Serato_ directory.

    Returns:
        Sorted list of absolute paths to .crate files.
    """
    subcrates = serato_root / "Subcrates"
    if not subcrates.is_dir():
        return []
    return sorted(path.resolve() for path in subcrates.glob("*.crate") if path.is_file())
