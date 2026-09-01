"""Serato crate write adapter."""

from __future__ import annotations

import copy
from pathlib import Path

import structlog
from serato_tools.crate import Crate
from serato_tools.database_v2 import DatabaseV2

from app.adapters.serato.atomic import replace_flushed
from app.adapters.serato.naming import crate_name_slash_aliases, sanitize_crate_name
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

    Just the ``vrsn`` header, what a fresh Serato install has before
    anything is imported or analysed. Never call this when a database V2
    already exists at the target path: **merge, never regenerate**
    (`merge_never_regenerate_vendor_index`) is a hard rule for a real
    vendor index, and this function does not check for one.

    Args:
        database_path: Where to write the new database V2 file.
    """
    payload = b"vrsn" + len(_DATABASE_V2_VERSION).to_bytes(4, "big") + _DATABASE_V2_VERSION
    database_path.parent.mkdir(parents=True, exist_ok=True)
    replace_flushed(database_path, payload)
    logger.info("serato_database_v2_created", path=str(database_path))


def write_crate(
    *,
    serato_root: Path,
    crate_name: str,
    track_paths: list[str],
    overwrite: bool = False,
) -> Path:
    """
    Write a new or replacement Serato crate file under Subcrates/.

    The crate is built on a sibling staging file, then committed with
    ``replace_flushed`` so the live path is not truncated before the
    bytes are on disk.

    Args:
        serato_root: Path to _Serato_ directory.
        crate_name: Crate filename stem (sanitized playlist name).
        track_paths: Serato-relative paths to add in order.
        overwrite: Replace an existing non-empty .crate file when True.
            A zero-byte leftover is overwritten even when this is False.

    Returns:
        Absolute path to the written .crate file.

    Raises:
        CrateExistsError: Target crate exists and overwrite is False.
    """
    subcrates = subcrates_dir(serato_root)
    subcrates.mkdir(parents=True, exist_ok=True)
    stem = sanitize_crate_name(crate_name)
    crate_path = (subcrates / f"{stem}.crate").resolve()
    if crate_path.is_file() and crate_path.stat().st_size > 0 and not overwrite:
        raise CrateExistsError(f"Crate already exists: {crate_path} (use --overwrite)")
    for alias in crate_name_slash_aliases(stem)[1:]:
        leftover = (subcrates / f"{alias}.crate").resolve()
        if leftover.is_file() and leftover != crate_path:
            leftover.unlink()
            logger.info("serato_legacy_slash_crate_removed", path=str(leftover))
    staging = crate_path.with_name(f".{crate_path.stem}.tmp.crate")
    if staging.is_file():
        staging.unlink()
    crate = Crate(str(staging))
    # Crate.DEFAULT_ENTRIES is class-level and add_track mutates it, so a new
    # crate inherits tracks added to any earlier one. Start from a private copy
    # holding only the header fields.
    crate.entries = [copy.deepcopy(entry) for entry in crate.entries if str(entry[0]) != "otrk"]
    for path in track_paths:
        crate.add_track(path)
    try:
        crate.save(str(staging))
        replace_flushed(crate_path, staging.read_bytes())
    finally:
        if staging.is_file():
            staging.unlink()
    logger.info(
        "serato_crate_written",
        path=str(crate_path),
        track_count=len(track_paths),
    )
    return crate_path


def write_volume_parent_crate(*, serato_root: Path, volume: str) -> Path:
    """
    Write an empty crate named after the thumbdrive.

    Serato treats this file as the folder wrapping every ``{volume}%%…``
    child crate.

    Args:
        serato_root: Path to ``_Serato_``.
        volume: Sanitized volume label from ``volume_label_for``.

    Returns:
        Path to the written parent ``.crate`` file.
    """
    return write_crate(
        serato_root=serato_root,
        crate_name=volume,
        track_paths=[],
        overwrite=True,
    )


def append_database_tracks(
    *,
    database_path: Path,
    records: list[list[tuple[str, object]]],
) -> int:
    """
    Append track records to a Serato database V2 file.

    Args:
        database_path: Path to the database V2 file.
        records: Field lists, one per new track, in Serato field order.

    Returns:
        Number of records appended.
    """
    if not records:
        return 0

    database = DatabaseV2(file=str(database_path))
    for fields in records:
        database.entries.append(("otrk", fields))
    # entries is a decoded view; _dump flushes it back into the bytes save() writes.
    database._dump()

    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    database.save(str(temporary))
    replace_flushed(database_path, temporary.read_bytes())
    logger.info(
        "serato_database_tracks_appended",
        path=str(database_path),
        added=len(records),
    )
    return len(records)
