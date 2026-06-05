"""Tests for Serato adapter and crate service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.base import SeratoLibraryNotFoundError
from app.adapters.serato.paths import list_crate_files, resolve_serato_library
from app.adapters.serato.reader import SeratoToolsAdapter, open_serato_library
from app.core.domain import SeratoLibrary
from app.services.crate_service import list_serato_crates


def test_resolve_serato_library(tmp_path: Path) -> None:
    """resolve_serato_library finds _Serato_/database V2."""
    serato = tmp_path / "_Serato_"
    serato.mkdir()
    (serato / "database V2").write_bytes(b"db")
    result = resolve_serato_library(tmp_path)
    assert result is not None
    assert result[1].name == "database V2"


def test_list_crate_files(tmp_path: Path) -> None:
    """list_crate_files returns .crate paths under Subcrates."""
    serato = tmp_path / "_Serato_"
    sub = serato / "Subcrates"
    sub.mkdir(parents=True)
    (sub / "Contents.crate").write_bytes(b"vrsn")
    (sub / "Other.crate").write_bytes(b"vrsn")
    paths = list_crate_files(serato)
    assert len(paths) == 2
    assert {p.stem for p in paths} == {"Contents", "Other"}


def test_open_raises_when_missing(tmp_path: Path) -> None:
    """open_serato_library raises when _Serato_ is absent."""
    with pytest.raises(SeratoLibraryNotFoundError):
        open_serato_library(tmp_path)


def test_serato_adapter_lists_crates() -> None:
    """SeratoToolsAdapter maps crate track paths to SeratoCrate."""
    library = SeratoLibrary(
        mount_path=Path("/mnt/usb"),
        serato_root=Path("/mnt/usb/_Serato_"),
        database_path=Path("/mnt/usb/_Serato_/database V2"),
        database_track_count=10,
    )
    mock_db = MagicMock()
    mock_crate = MagicMock()
    mock_crate.get_track_paths.return_value = ["Contents/a.mp3", "Contents/b.mp3"]

    with patch("app.adapters.serato.reader.list_crate_files") as list_files:
        list_files.return_value = [Path("/mnt/usb/_Serato_/Subcrates/Pocket.crate")]
        with patch("app.adapters.serato.reader.Crate", return_value=mock_crate):
            crates = SeratoToolsAdapter(library, mock_db).list_crates()

    assert len(crates) == 1
    assert crates[0].name == "Pocket"
    assert crates[0].track_count == 2


def test_list_serato_crates_integration() -> None:
    """Integration test on /mnt/usb when Serato library is present."""
    mount = Path("/mnt/usb")
    if not (mount / "_Serato_/database V2").is_file():
        pytest.skip("/mnt/usb Serato library not available")

    result = list_serato_crates(mount)
    assert result.library.database_track_count > 0
    assert len(result.crates) >= 1
    assert all(crate.track_count > 0 for crate in result.crates)
