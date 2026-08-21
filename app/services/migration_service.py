"""Rekordbox playlist to Serato crate migration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.adapters.base import WriteContext
from app.adapters.rekordbox import open_rekordbox_library
from app.adapters.serato import read_database_track_paths
from app.adapters.serato.paths import resolve_serato_library
from app.adapters.serato.writer import sanitize_crate_name, write_crate
from app.core.domain import Playlist
from app.core.track_paths import build_serato_path_index, normalize_track_path
from app.services.backup_service import backup_mount_for_migration
from app.storage.backup import BackupResult
from app.storage.mounts import resolve_mount_path

logger = structlog.get_logger(__name__)


class MigrationError(Exception):
    """Base error for playlist migration."""


class PlaylistNotFoundError(MigrationError):
    """Raised when the requested Rekordbox playlist cannot be resolved."""


class SeratoLibraryRequiredError(MigrationError):
    """Raised when Serato library is missing on the mount."""


@dataclass(frozen=True)
class PlaylistMigrationPlan:
    """
    Resolved migration plan before any write.

    Attributes:
        playlist_id: Rekordbox playlist id.
        playlist_name: Rekordbox playlist display name.
        crate_name: Sanitized Serato crate filename stem.
        serato_paths: Paths to write (Serato-canonical, playlist order).
        skipped_paths: Rekordbox paths with no Serato index match.
        rekordbox_paths: All Rekordbox paths in playlist order.
    """

    playlist_id: int
    playlist_name: str
    crate_name: str
    serato_paths: tuple[str, ...]
    skipped_paths: tuple[str, ...]
    rekordbox_paths: tuple[str, ...]


@dataclass(frozen=True)
class PlaylistMigrationResult:
    """
    Outcome of a playlist migration operation.

    Attributes:
        plan: Resolved path mapping and target crate name.
        backup: Backup taken before write (None when dry_run).
        crate_path: Written crate path (None when dry_run).
        dry_run: True when no backup or write was performed.
    """

    plan: PlaylistMigrationPlan
    backup: BackupResult | None
    crate_path: Path | None
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize result to a JSON-friendly dictionary.

        Returns:
            Dict with plan summary and paths.
        """
        return {
            "dry_run": self.dry_run,
            "playlist_id": self.plan.playlist_id,
            "playlist_name": self.plan.playlist_name,
            "crate_name": self.plan.crate_name,
            "rekordbox_track_count": len(self.plan.rekordbox_paths),
            "serato_track_count": len(self.plan.serato_paths),
            "skipped_count": len(self.plan.skipped_paths),
            "skipped_paths": list(self.plan.skipped_paths),
            "serato_paths": list(self.plan.serato_paths),
            "backup_id": self.backup.backup_id if self.backup else None,
            "crate_path": str(self.crate_path) if self.crate_path else None,
        }


def _find_playlist(
    playlists: tuple[Playlist, ...],
    *,
    playlist_id: int | None,
    playlist_name: str | None,
) -> Playlist:
    """
    Resolve a single non-folder playlist by id or exact name.

    Args:
        playlists: All playlists from Rekordbox.
        playlist_id: Rekordbox playlist id (optional).
        playlist_name: Exact playlist name match (optional).

    Returns:
        Matching Playlist.

    Raises:
        PlaylistNotFoundError: No match or ambiguous name.
        ValueError: Neither id nor name provided.
    """
    if playlist_id is not None:
        for playlist in playlists:
            if playlist.id == playlist_id:
                if playlist.is_folder:
                    raise PlaylistNotFoundError(f"Playlist {playlist_id} is a folder")
                return playlist
        raise PlaylistNotFoundError(f"Playlist not found: {playlist_id}")

    if playlist_name is None:
        raise ValueError("Either playlist_id or playlist_name is required")

    matches = [p for p in playlists if not p.is_folder and p.name == playlist_name]
    if not matches:
        raise PlaylistNotFoundError(f"Playlist not found: {playlist_name!r}")
    if len(matches) > 1:
        raise PlaylistNotFoundError(f"Multiple playlists named {playlist_name!r}")
    return matches[0]


def build_migration_plan(
    mount: str | Path,
    *,
    playlist_id: int | None = None,
    playlist_name: str | None = None,
) -> PlaylistMigrationPlan:
    """
    Build a Rekordbox→Serato migration plan without writing.

    Args:
        mount: Mount path (e.g. /mnt/usb).
        playlist_id: Rekordbox playlist id.
        playlist_name: Rekordbox playlist name (exact match).

    Returns:
        PlaylistMigrationPlan with matched and skipped paths.

    Raises:
        PlaylistNotFoundError: Playlist missing or is a folder.
        SeratoLibraryRequiredError: No Serato library on mount.
        UnsupportedDatabaseError: Rekordbox format unsupported.
    """
    mount_path = resolve_mount_path(mount)
    serato = resolve_serato_library(mount_path)
    if serato is None:
        raise SeratoLibraryRequiredError(f"No Serato library under {mount_path}")

    _, database_path = serato
    rb_adapter = open_rekordbox_library(mount_path)
    if not hasattr(rb_adapter, "get_playlist_track_paths"):
        raise MigrationError("Migration requires Rekordbox One Library (exportLibrary.db)")

    playlists = tuple(rb_adapter.list_playlists())
    playlist = _find_playlist(
        playlists,
        playlist_id=playlist_id,
        playlist_name=playlist_name,
    )

    rekordbox_paths = tuple(rb_adapter.get_playlist_track_paths(playlist.id))
    index = build_serato_path_index(read_database_track_paths(database_path))

    serato_paths: list[str] = []
    skipped: list[str] = []
    for rb_path in rekordbox_paths:
        key = normalize_track_path(rb_path)
        canonical = index.get(key)
        if canonical is None:
            skipped.append(rb_path)
        else:
            serato_paths.append(canonical)

    crate_name = sanitize_crate_name(playlist.name)
    logger.info(
        "migration_plan_built",
        playlist_id=playlist.id,
        playlist_name=playlist.name,
        matched=len(serato_paths),
        skipped=len(skipped),
    )
    return PlaylistMigrationPlan(
        playlist_id=playlist.id,
        playlist_name=playlist.name,
        crate_name=crate_name,
        serato_paths=tuple(serato_paths),
        skipped_paths=tuple(skipped),
        rekordbox_paths=rekordbox_paths,
    )


def migrate_playlist_to_crate(
    mount: str | Path,
    *,
    playlist_id: int | None = None,
    playlist_name: str | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
    backup_root: str | Path | None = None,
) -> PlaylistMigrationResult:
    """
    Copy a Rekordbox playlist to a new Serato crate file (backup-gated).

    Args:
        mount: Mount path containing Rekordbox and Serato libraries.
        playlist_id: Rekordbox playlist id.
        playlist_name: Rekordbox playlist name (exact).
        dry_run: When True, only build and return the plan.
        overwrite: Replace an existing Subcrates/<name>.crate file.
        backup_root: Optional backups parent directory.

    Returns:
        PlaylistMigrationResult with backup and crate path when not dry_run.

    Raises:
        CrateExistsError: Target crate exists and overwrite is False.
        MigrationError: Subclasses for specific failures.
    """
    mount_path = resolve_mount_path(mount)
    plan = build_migration_plan(
        mount_path,
        playlist_id=playlist_id,
        playlist_name=playlist_name,
    )

    if dry_run:
        return PlaylistMigrationResult(plan=plan, backup=None, crate_path=None, dry_run=True)

    if not plan.serato_paths:
        raise MigrationError(
            f"No tracks from playlist {plan.playlist_name!r} match the Serato library index",
        )

    backup = backup_mount_for_migration(mount_path, backup_root=backup_root)
    serato = resolve_serato_library(mount_path)
    if serato is None:
        raise SeratoLibraryRequiredError(f"No Serato library under {mount_path}")
    serato_root, _ = serato

    write_context = WriteContext(backup_path=backup.backup_dir)
    crate_path = write_crate(
        serato_root=serato_root,
        crate_name=plan.crate_name,
        track_paths=list(plan.serato_paths),
        write_context=write_context,
        overwrite=overwrite,
    )
    return PlaylistMigrationResult(
        plan=plan,
        backup=backup,
        crate_path=crate_path,
        dry_run=False,
    )
