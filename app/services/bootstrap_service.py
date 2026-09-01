"""Bootstrapping an empty Serato library on a rekordbox-only stick.

On a Rekordbox stick with no ``_Serato_``, sync has nowhere to write.
This creates the minimum a fresh Serato install would have, an empty
index, so the rest of the sync path can run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from app.adapters.serato.neworder import write_crate_order
from app.adapters.serato.paths import (
    database_v2_path,
    resolve_serato_library,
    serato_root_for,
    subcrates_dir,
)
from app.adapters.serato.writer import create_empty_database_v2
from app.storage.mounts import resolve_mount_path

logger = structlog.get_logger(__name__)

_REKORDBOX_RELATIVE = (
    "PIONEER/rekordbox/exportLibrary.db",
    "PIONEER/rekordbox/export.pdb",
    "PIONEER/rekordbox/exportExt.pdb",
)


@dataclass(frozen=True)
class BootstrapResult:
    """
    Outcome of a bootstrap attempt.

    Attributes:
        serato_root: Path to _Serato_ (created by this call, or already present).
        created: True when this call actually created a new library.
    """

    serato_root: Path
    created: bool


def rekordbox_files_on_mount(mount_path: Path) -> list[Path]:
    """
    Resolve existing Rekordbox database files under a mount.

    Args:
        mount_path: USB or library root (e.g. /media/$USER/MY_USB).

    Returns:
        Absolute paths that exist on disk.
    """
    mount = mount_path.resolve()
    found: list[Path] = []
    for relative in _REKORDBOX_RELATIVE:
        candidate = mount / relative
        if candidate.is_file():
            found.append(candidate)
    return found


def bootstrap_serato_library(mount: str | Path) -> BootstrapResult:
    """
    Create an empty, valid Serato library on a mount that has none yet.

    Writes only inside ``_Serato_/``: the directory itself, ``Subcrates/``, an
    empty ``database V2`` (just the ``vrsn`` header), and an empty
    ``neworder.pref``. Nothing under ``PIONEER/`` or ``Contents/`` is ever
    touched. A mount that already has a Serato library is left completely
    alone and reported as not created. This only fills a gap. It never
    merges into or replaces something that exists. A zero-byte
    ``database V2`` is treated as missing.

    Args:
        mount: Mount path containing a Rekordbox export.

    Returns:
        BootstrapResult describing what happened.

    Raises:
        FileNotFoundError: No Rekordbox database files exist on the mount.
    """
    mount_path = resolve_mount_path(mount)
    if resolve_serato_library(mount_path) is not None:
        logger.info("serato_library_already_present", mount=str(mount_path))
        return BootstrapResult(serato_root=serato_root_for(mount_path), created=False)

    if not rekordbox_files_on_mount(mount_path):
        raise FileNotFoundError(f"No Rekordbox database files found under {mount_path}")

    serato_root = serato_root_for(mount_path)
    subcrates_dir(serato_root).mkdir(parents=True, exist_ok=True)
    create_empty_database_v2(database_v2_path(serato_root))
    write_crate_order(serato_root, [])

    logger.info("serato_library_bootstrapped", serato_root=str(serato_root))
    return BootstrapResult(serato_root=serato_root, created=True)
