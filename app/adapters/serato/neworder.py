"""Reading and writing _Serato_/neworder.pref, the crate display order."""

from __future__ import annotations

from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

FILENAME = "neworder.pref"
_BEGIN = "[begin record]"
_END = "[end record]"
_CRATE_PREFIX = "[crate]"


def neworder_path(serato_root: Path) -> Path:
    """
    Return the neworder.pref path for a Serato library root.

    Args:
        serato_root: Path to the _Serato_ directory.

    Returns:
        Path to neworder.pref, which may not exist yet.
    """
    return serato_root / FILENAME


def read_crate_order(serato_root: Path) -> list[str]:
    """
    Read crate names in display order.

    Args:
        serato_root: Path to the _Serato_ directory.

    Returns:
        Crate names in order, empty when the file is absent or unreadable.
    """
    path = neworder_path(serato_root)
    if not path.is_file():
        return []
    try:
        text = path.read_bytes().decode("utf-16-be")
    except (OSError, UnicodeDecodeError):
        logger.warning("neworder_unreadable", path=str(path))
        return []
    return [
        line[len(_CRATE_PREFIX) :] for line in text.splitlines() if line.startswith(_CRATE_PREFIX)
    ]


def write_crate_order(serato_root: Path, crate_names: list[str]) -> Path:
    """
    Write crate names in display order.

    Args:
        serato_root: Path to the _Serato_ directory.
        crate_names: Crate names in the order Serato should show them.

    Returns:
        Path to the written file.
    """
    lines = [_BEGIN, *(f"{_CRATE_PREFIX}{name}" for name in crate_names), _END]
    payload = ("\n".join(lines) + "\n").encode("utf-16-be")

    path = neworder_path(serato_root)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    logger.info("neworder_written", path=str(path), crates=len(crate_names))
    return path


def merge_crate_order(serato_root: Path, new_names: list[str]) -> list[str]:
    """
    Append crate names that are not already listed, preserving existing order.

    Args:
        serato_root: Path to the _Serato_ directory.
        new_names: Crate names that should be present.

    Returns:
        The merged order that was written.
    """
    order = read_crate_order(serato_root)
    order.extend(name for name in new_names if name not in order)
    return order
