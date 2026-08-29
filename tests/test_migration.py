"""Tests for Rekordbox to Serato playlist migration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.base import WriteContext
from app.adapters.serato.writer import CrateExistsError, sanitize_crate_name, write_crate
from app.core.domain import Playlist, RekordboxDbFormat, RekordboxLibrary
from app.services.migration_service import (
    PlaylistNotFoundError,
    build_migration_plan,
    migrate_playlist_to_crate,
)
from app.storage.backup import BackupManifest
from tests.conftest import make_library


def test_sanitize_crate_name() -> None:
    """sanitize_crate_name removes invalid filename characters."""
    assert sanitize_crate_name("My: Playlist?") == "My_ Playlist_"
    assert sanitize_crate_name("Afro / Afro House") == "Afro \uff0f Afro House"
    assert sanitize_crate_name("   ") == "Untitled"


def test_write_crate_creates_file(tmp_path: Path, make_backup) -> None:
    """write_crate creates a .crate with track entries."""
    serato = tmp_path / "_Serato_"
    serato.mkdir()
    backup = make_backup()

    crate_path = write_crate(
        serato_root=serato,
        crate_name="Pocket",
        track_paths=["Contents/a.mp3", "Contents/b.mp3"],
        write_context=WriteContext(backup_path=backup.backup_dir),
    )
    assert crate_path.is_file()
    assert crate_path.name == "Pocket.crate"


def test_write_crate_exists_without_overwrite(tmp_path: Path, make_backup) -> None:
    """write_crate raises when crate exists and overwrite is False."""
    serato = tmp_path / "_Serato_"
    sub = serato / "Subcrates"
    sub.mkdir(parents=True)
    (sub / "Pocket.crate").write_bytes(b"existing")
    backup = make_backup()

    with pytest.raises(CrateExistsError):
        write_crate(
            serato_root=serato,
            crate_name="Pocket",
            track_paths=["Contents/a.mp3"],
            write_context=WriteContext(backup_path=backup.backup_dir),
            overwrite=False,
        )


def test_build_migration_plan_with_mocks(tmp_path: Path) -> None:
    """build_migration_plan maps Rekordbox paths through Serato index."""
    mount = tmp_path / "usb"
    mount.mkdir()
    (mount / "_Serato_").mkdir()
    (mount / "_Serato_" / "database V2").write_bytes(b"db")
    (mount / "PIONEER" / "rekordbox").mkdir(parents=True)
    (mount / "PIONEER" / "rekordbox" / "exportLibrary.db").write_bytes(b"rb")

    library = RekordboxLibrary(
        mount_path=mount,
        database_path=mount / "PIONEER/rekordbox/exportLibrary.db",
        db_format=RekordboxDbFormat.ONE_LIBRARY,
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False, track_count=2)

    mock_adapter = MagicMock()
    mock_adapter.library = library
    mock_adapter.list_playlists.return_value = [playlist]
    mock_adapter.get_playlist_track_paths.return_value = [
        "/Contents/Artist/track.mp3",
        "/Contents/Missing/track.mp3",
    ]

    with patch(
        "app.services.migration_service.read_database_track_paths",
        return_value=["Contents/Artist/track.mp3"],
    ):
        plan = build_migration_plan(make_library(mount, mock_adapter), playlist_id=1)

    assert plan.playlist_name == "Pocket"
    assert plan.serato_paths == ("Contents/Artist/track.mp3",)
    assert len(plan.skipped_paths) == 1


def test_migrate_playlist_dry_run(tmp_path: Path) -> None:
    """migrate_playlist_to_crate dry_run does not create backup or crate."""
    mount = tmp_path / "usb"
    mount.mkdir()
    (mount / "_Serato_").mkdir()
    (mount / "_Serato_" / "database V2").write_bytes(b"db")

    with patch(
        "app.services.migration_service.build_migration_plan",
    ) as build_plan:
        from app.services.migration_service import PlaylistMigrationPlan

        build_plan.return_value = PlaylistMigrationPlan(
            playlist_id=1,
            playlist_name="Pocket",
            crate_name="Pocket",
            serato_paths=("Contents/a.mp3",),
            skipped_paths=(),
            rekordbox_paths=("/Contents/a.mp3",),
        )
        result = migrate_playlist_to_crate(
            make_library(mount, MagicMock()), playlist_id=1, dry_run=True
        )

    assert result.dry_run is True
    assert result.backup is None
    assert result.crate_path is None


def test_build_migration_plan_playlist_not_found(tmp_path: Path) -> None:
    """build_migration_plan raises when playlist id is missing."""
    mount = tmp_path / "usb"
    mount.mkdir()
    (mount / "_Serato_").mkdir()
    (mount / "_Serato_" / "database V2").write_bytes(b"db")
    (mount / "PIONEER" / "rekordbox").mkdir(parents=True)
    (mount / "PIONEER" / "rekordbox" / "exportLibrary.db").write_bytes(b"rb")

    mock_adapter = MagicMock()
    mock_adapter.list_playlists.return_value = []

    with pytest.raises(PlaylistNotFoundError):
        build_migration_plan(make_library(mount, mock_adapter), playlist_id=99)


def test_migrate_playlist_end_to_end(tmp_path: Path) -> None:
    """Full migration on synthetic mount with mocked rbox and serato DB."""
    mount = tmp_path / "usb"
    serato = mount / "_Serato_"
    sub = serato / "Subcrates"
    sub.mkdir(parents=True)
    (serato / "database V2").write_bytes(b"db")
    rb = mount / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"rb")

    library = RekordboxLibrary(
        mount_path=mount,
        database_path=rb / "exportLibrary.db",
        db_format=RekordboxDbFormat.ONE_LIBRARY,
    )
    playlist = Playlist(id=1, name="Pocket", parent_id=None, is_folder=False)

    mock_adapter = MagicMock()
    mock_adapter.library = library
    mock_adapter.list_playlists.return_value = [playlist]
    mock_adapter.get_playlist_track_paths.return_value = ["/Contents/Artist/track.mp3"]

    with patch(
        "app.services.migration_service.read_database_track_paths",
        return_value=["Contents/Artist/track.mp3"],
    ):
        result = migrate_playlist_to_crate(make_library(mount, mock_adapter), playlist_id=1)

    assert result.crate_path is not None
    assert result.crate_path.name == "Pocket.crate"
    assert result.backup is not None
    assert BackupManifest.load(result.backup.backup_dir).backup_id == result.backup.backup_id
