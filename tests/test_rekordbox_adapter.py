"""Tests for Rekordbox adapter and playlist service."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.adapters.base import DatabaseNotFoundError, UnsupportedDatabaseError, WriteContext
from app.adapters.rekordbox.paths import resolve_rekordbox_database
from app.adapters.rekordbox.reader import RboxOneLibraryAdapter, open_rekordbox_library
from app.core.domain import RekordboxDbFormat, RekordboxLibrary
from app.services.playlist_service import list_rekordbox_playlists


def test_write_context_requires_existing_backup(tmp_path: Path) -> None:
    """WriteContext rejects missing backup paths."""
    with pytest.raises(ValueError, match="backup_path"):
        WriteContext(backup_path=tmp_path / "missing")


def test_resolve_prefers_export_library_db(tmp_path: Path) -> None:
    """resolve_rekordbox_database prefers exportLibrary.db over export.pdb."""
    rb = tmp_path / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "export.pdb").write_bytes(b"not sqlite")
    (rb / "exportLibrary.db").write_bytes(b"encrypted")

    path, fmt = resolve_rekordbox_database(tmp_path)
    assert path.name == "exportLibrary.db"
    assert fmt == RekordboxDbFormat.ONE_LIBRARY


def test_resolve_device_sql_only(tmp_path: Path) -> None:
    """resolve returns export.pdb when One Library is absent."""
    rb = tmp_path / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "export.pdb").write_bytes(b"devicesql")

    path, fmt = resolve_rekordbox_database(tmp_path)
    assert fmt == RekordboxDbFormat.DEVICE_SQL


def test_open_raises_when_no_database(tmp_path: Path) -> None:
    """open_rekordbox_library raises when mount has no Rekordbox files."""
    with pytest.raises(DatabaseNotFoundError):
        open_rekordbox_library(tmp_path)


def test_open_raises_for_device_sql_only(tmp_path: Path) -> None:
    """export.pdb without exportLibrary.db is not yet supported."""
    rb = tmp_path / "PIONEER/rekordbox"
    rb.mkdir(parents=True)
    (rb / "export.pdb").write_bytes(b"x")

    with pytest.raises(UnsupportedDatabaseError, match="DeviceSQL"):
        open_rekordbox_library(tmp_path)


def test_rbox_adapter_maps_playlists() -> None:
    """RboxOneLibraryAdapter maps rbox playlist rows to domain models."""
    library = RekordboxLibrary(
        mount_path=Path("/mnt/usb"),
        database_path=Path("/mnt/usb/PIONEER/rekordbox/exportLibrary.db"),
        db_format=RekordboxDbFormat.ONE_LIBRARY,
    )
    row = MagicMock()
    row.id = 18
    row.name = "House"
    row.parent_id = 17
    row.items = []

    db = MagicMock()
    db.get_playlists.return_value = [row]

    from rbox.enums import PlaylistType

    row.attribute = PlaylistType.Folder
    playlists = RboxOneLibraryAdapter(library, db).list_playlists()

    assert len(playlists) == 1
    assert playlists[0].name == "House"
    assert playlists[0].parent_id == 17
    assert playlists[0].is_folder is True


def test_list_rekordbox_playlists_integration() -> None:
    """Integration test against /mnt/usb when exportLibrary.db is present."""
    mount = Path("/mnt/usb")
    db_file = mount / "PIONEER/rekordbox/exportLibrary.db"
    if not db_file.is_file():
        pytest.skip("/mnt/usb exportLibrary.db not available")

    result = list_rekordbox_playlists(mount)
    assert result.library.db_format == RekordboxDbFormat.ONE_LIBRARY
    assert len(result.playlists) > 0
    assert any(p.name == "House" for p in result.playlists)
