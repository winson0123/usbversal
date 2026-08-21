"""Serato crate write adapter (backup-gated)."""

from __future__ import annotations

from pathlib import Path

import structlog
from serato_tools.crate import Crate

from app.adapters.base import WriteContext
from app.adapters.serato.naming import sanitize_crate_name
from app.adapters.serato.paths import subcrates_dir
from app.adapters.serato.tlv import encode_field

logger = structlog.get_logger(__name__)


class CrateExistsError(Exception):
    """Raised when a target crate file already exists and overwrite is disabled."""


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

    Existing bytes are never re-encoded: new ``otrk`` records are concatenated
    onto the file as-is, so records this tool does not understand cannot be
    altered or dropped.

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

    existing = database_path.read_bytes()
    appended = b"".join(encode_field("otrk", fields) for fields in records)
    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    temporary.write_bytes(existing + appended)
    temporary.replace(database_path)
    logger.info(
        "serato_database_tracks_appended",
        path=str(database_path),
        added=len(records),
        bytes_added=len(appended),
    )
    return len(records)
