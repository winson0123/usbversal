"""Sync Rekordbox analysis metadata into Serato MP3 tags for a playlist."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from rbox import OneLibrary

from app.adapters.base import WriteContext
from app.adapters.rekordbox import open_rekordbox_library
from app.adapters.rekordbox.analysis import build_key_name_map, read_track_analysis
from app.adapters.rekordbox.reader import RboxOneLibraryAdapter
from app.adapters.serato.analysis_writer import write_serato_analysis_to_mp3
from app.core.track_paths import normalize_track_path
from app.services.backup_service import backup_mount_for_migration
from app.services.migration_service import (
    MigrationError,
    SeratoLibraryRequiredError,
    _find_playlist,
)
from app.storage.backup import BackupResult, create_backup

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TrackAnalysisSyncPlan:
    """
    Planned analysis sync for one track.

    Attributes:
        rekordbox_path: Path from Rekordbox content.path.
        mp3_path: Resolved absolute MP3 path on mount.
        bpm: Rekordbox BPM when known.
        camelot_key: Target Serato TKEY.
        hot_cue_count: Number of hot cues in ANLZ.
        has_anlz: True when USBANLZ file exists.
    """

    rekordbox_path: str
    mp3_path: str
    bpm: float | None
    camelot_key: str | None
    hot_cue_count: int
    has_anlz: bool


@dataclass(frozen=True)
class AnalysisSyncResult:
    """
    Outcome of syncing analysis for a playlist.

    Attributes:
        playlist_id: Rekordbox playlist id.
        playlist_name: Playlist display name.
        plans: Per-track sync plans.
        backup: Backup taken before writes (None if dry_run).
        synced_tracks: Tracks written successfully.
        skipped_tracks: Tracks skipped with reason.
        dry_run: True when no backup or writes occurred.
    """

    playlist_id: int
    playlist_name: str
    plans: tuple[TrackAnalysisSyncPlan, ...]
    backup: BackupResult | None
    synced_tracks: tuple[str, ...]
    skipped_tracks: tuple[tuple[str, str], ...]
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize result for JSON CLI output.

        Returns:
            Dict with summary counts and per-track plans.
        """
        return {
            "dry_run": self.dry_run,
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist_name,
            "track_count": len(self.plans),
            "synced_count": len(self.synced_tracks),
            "skipped_count": len(self.skipped_tracks),
            "backup_id": self.backup.backup_id if self.backup else None,
            "plans": [
                {
                    "rekordbox_path": p.rekordbox_path,
                    "bpm": p.bpm,
                    "camelot_key": p.camelot_key,
                    "hot_cue_count": p.hot_cue_count,
                    "has_anlz": p.has_anlz,
                }
                for p in self.plans
            ],
            "synced_tracks": list(self.synced_tracks),
            "skipped": [{"path": p, "reason": r} for p, r in self.skipped_tracks],
        }


def build_analysis_sync_plan(
    mount: str | Path,
    *,
    playlist_id: int | None = None,
    playlist_name: str | None = None,
) -> tuple[int, str, tuple[TrackAnalysisSyncPlan, ...], OneLibrary]:
    """
    Build analysis sync plans for all tracks in a Rekordbox playlist.

    Args:
        mount: USB mount path.
        playlist_id: Rekordbox playlist id.
        playlist_name: Exact playlist name.

    Returns:
        Tuple of playlist id, name, plans, and open OneLibrary db.

    Raises:
        PlaylistNotFoundError: Playlist missing.
        MigrationError: Unsupported Rekordbox format.
    """
    mount_path = Path(mount).resolve()
    rb_adapter = open_rekordbox_library(mount_path)
    if not isinstance(rb_adapter, RboxOneLibraryAdapter):
        raise MigrationError("Analysis sync requires Rekordbox One Library (exportLibrary.db)")

    db = rb_adapter.database
    playlists = tuple(rb_adapter.list_playlists())
    playlist = _find_playlist(playlists, playlist_id=playlist_id, playlist_name=playlist_name)
    key_names = build_key_name_map(db)

    plans: list[TrackAnalysisSyncPlan] = []
    for content in db.get_playlist_contents(playlist.id):
        analysis = read_track_analysis(db, mount_path, content, key_names=key_names)
        mp3 = mount_path / analysis.path.lstrip("/")
        plans.append(
            TrackAnalysisSyncPlan(
                rekordbox_path=analysis.path,
                mp3_path=str(mp3),
                bpm=analysis.bpm,
                camelot_key=analysis.camelot_key,
                hot_cue_count=len(analysis.hot_cues),
                has_anlz=analysis.anlz_path is not None,
            ),
        )

    return playlist.id, playlist.name, tuple(plans), db


def sync_playlist_analysis(
    mount: str | Path,
    *,
    playlist_id: int | None = None,
    playlist_name: str | None = None,
    dry_run: bool = False,
    backup_root: str | Path | None = None,
) -> AnalysisSyncResult:
    """
    Copy Rekordbox analysis (BPM, key, beatgrid, hot cues) into Serato MP3 tags.

    Serato reads analysis from ID3 GEOB tags on each file, not from database V2.
    Waveform overview data is not copied in this milestone.

    Args:
        mount: USB mount with Rekordbox and Serato libraries.
        playlist_id: Rekordbox playlist id.
        playlist_name: Exact playlist name.
        dry_run: Plan only; no backup or tag writes.
        backup_root: Optional backups directory parent.

    Returns:
        AnalysisSyncResult with per-track outcomes.

    Raises:
        SeratoLibraryRequiredError: When Serato is missing (playlist should be on Serato stick).
    """
    from app.adapters.serato.paths import resolve_serato_library

    mount_path = Path(mount).resolve()
    if resolve_serato_library(mount_path) is None:
        raise SeratoLibraryRequiredError(f"No Serato library under {mount_path}")

    pid, pname, plans, db = build_analysis_sync_plan(
        mount_path,
        playlist_id=playlist_id,
        playlist_name=playlist_name,
    )
    key_names = build_key_name_map(db)

    if dry_run:
        return AnalysisSyncResult(
            playlist_id=pid,
            playlist_name=pname,
            plans=plans,
            backup=None,
            synced_tracks=(),
            skipped_tracks=(),
            dry_run=True,
        )

    mp3_paths = [Path(p.mp3_path) for p in plans if Path(p.mp3_path).is_file()]
    root = Path(backup_root).resolve() if backup_root else None
    backup = backup_mount_for_migration(mount_path, backup_root=root)
    if mp3_paths:
        mp3_backup = create_backup(
            source_mount=mount_path,
            files=mp3_paths,
            backup_root=root or (mount_path / "backups"),
            backup_id=f"{backup.backup_id}-mp3",
        )
        logger.info("analysis_mp3_backup", backup_id=mp3_backup.backup_id, files=len(mp3_paths))

    write_context = WriteContext(backup_path=backup.backup_dir)
    synced: list[str] = []
    skipped: list[tuple[str, str]] = []

    for content in db.get_playlist_contents(pid):
        analysis = read_track_analysis(db, mount_path, content, key_names=key_names)
        mp3 = mount_path / analysis.path.lstrip("/")
        if not mp3.is_file():
            skipped.append((analysis.path, "mp3 missing on mount"))
            continue
        if analysis.bpm is None and not analysis.hot_cues and analysis.camelot_key is None:
            skipped.append((analysis.path, "no analysis fields to copy"))
            continue
        try:
            write_serato_analysis_to_mp3(mp3, analysis, write_context)
            synced.append(normalize_track_path(analysis.path))
        except (OSError, ValueError) as exc:
            skipped.append((analysis.path, str(exc)))
            logger.warning("analysis_sync_failed", path=str(mp3), error=str(exc))

    logger.info(
        "analysis_sync_completed",
        playlist=pname,
        synced=len(synced),
        skipped=len(skipped),
    )
    return AnalysisSyncResult(
        playlist_id=pid,
        playlist_name=pname,
        plans=plans,
        backup=backup,
        synced_tracks=tuple(synced),
        skipped_tracks=tuple(skipped),
        dry_run=False,
    )
