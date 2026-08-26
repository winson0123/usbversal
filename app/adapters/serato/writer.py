"""Serato crate write adapter (backup-gated)."""

from __future__ import annotations

import copy
from pathlib import Path

import structlog
from serato_tools.crate import Crate
from serato_tools.database_v2 import DatabaseV2

from app.adapters.base import WriteContext
from app.adapters.serato.naming import sanitize_crate_name
from app.adapters.serato.paths import subcrates_dir

logger = structlog.get_logger(__name__)

# The version string a fresh Serato install writes into an empty database V2,
# before anything has been analysed or imported. [verified] in
# docs/schemas/serato-schema-notes.md.
_DATABASE_V2_VERSION = "2.0/Serato Scratch LIVE Database".encode("utf-16-be")


class CrateExistsError(Exception):
    """Raised when a target crate file already exists and overwrite is disabled."""


def create_empty_database_v2(database_path: Path) -> None:
    """
    Write a fresh, empty, structurally valid database V2 file.

    Just the ``vrsn`` header -- what a fresh Serato install has before
    anything is imported or analysed. Never call this when a database V2
    already exists at the target path: **merge, never regenerate**
    (`merge_never_regenerate_vendor_index`) is a hard rule for a real
    vendor index, and this function does not check for one.

    Args:
        database_path: Where to write the new database V2 file.
    """
    payload = b"vrsn" + len(_DATABASE_V2_VERSION).to_bytes(4, "big") + _DATABASE_V2_VERSION
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(database_path)
    logger.info("serato_database_v2_created", path=str(database_path))


def write_crate(
    *,
    serato_root: Path,
    crate_name: str,
    track_paths: list[str],
    write_context: WriteContext,
    overwrite: bool = False,
) -> Path:
    """
    Write a new or replacement Serato crate file under Subcrates/.

    Args:
        serato_root: Path to _Serato_ directory.
        crate_name: Crate filename stem (sanitized playlist name).
        track_paths: Serato-relative paths to add in order.
        write_context: Validated backup context (required before any write).
        overwrite: Replace an existing .crate file when True.

    Returns:
        Absolute path to the written .crate file.

    Raises:
        CrateExistsError: Target crate exists and overwrite is False.
        ValueError: If write_context backup_path is invalid.
    """
    _ = write_context  # validated in WriteContext.__post_init__
    subcrates = subcrates_dir(serato_root)
    subcrates.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_crate_name(crate_name)
    crate_path = (subcrates / f"{safe_name}.crate").resolve()

    if crate_path.is_file() and not overwrite:
        raise CrateExistsError(f"Crate already exists: {crate_path} (use --overwrite)")

    if crate_path.is_file():
        crate_path.unlink()
        logger.info("serato_crate_removed_for_overwrite", path=str(crate_path))

    crate = Crate(str(crate_path))
    # Crate.DEFAULT_ENTRIES is class-level and add_track mutates it, so a new
    # crate inherits tracks added to any earlier one. Start from a private copy
    # holding only the header fields.
    crate.entries = [copy.deepcopy(entry) for entry in crate.entries if str(entry[0]) != "otrk"]
    for path in track_paths:
        crate.add_track(path)
    crate.save(str(crate_path))
    logger.info(
        "serato_crate_written",
        path=str(crate_path),
        track_count=len(track_paths),
    )
    return crate_path


def append_database_tracks(
    *,
    database_path: Path,
    records: list[list[tuple[str, object]]],
    write_context: WriteContext,
) -> int:
    """
    Append track records to a Serato database V2 file.

    Args:
        database_path: Path to the database V2 file.
        records: Field lists, one per new track, in Serato field order.
        write_context: Validated backup context, required before any write.

    Returns:
        Number of records appended.
    """
    _ = write_context
    if not records:
        return 0

    database = DatabaseV2(file=str(database_path))
    for fields in records:
        database.entries.append(("otrk", fields))
    # entries is a decoded view; _dump flushes it back into the bytes save() writes.
    database._dump()

    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    database.save(str(temporary))
    temporary.replace(database_path)
    logger.info(
        "serato_database_tracks_appended",
        path=str(database_path),
        added=len(records),
    )
    return len(records)
