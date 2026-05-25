"""Tests for DJ library detection heuristics."""

from pathlib import Path

from app.core.domain import LibraryType
from app.storage.discovery import LibraryDiscovery


def test_detect_rekordbox_pioneer_path(tmp_path: Path) -> None:
    """Detect Rekordbox when PIONEER/rekordbox exists."""
    rb_root = tmp_path / "PIONEER" / "rekordbox"
    rb_root.mkdir(parents=True)
    (rb_root / "master.db").write_bytes(b"")

    discovery = LibraryDiscovery(max_depth=6)
    results = discovery.detect_on_mount(tmp_path)

    types = {r.library_type for r in results}
    assert LibraryType.REKORDBOX in types
    assert any(r.confidence >= 0.85 for r in results if r.library_type == LibraryType.REKORDBOX)


def test_detect_rekordbox_export_pdb(tmp_path: Path) -> None:
    """Detect Rekordbox export.pdb file."""
    lib_dir = tmp_path / "some" / "export"
    lib_dir.mkdir(parents=True)
    (lib_dir / "export.pdb").write_bytes(b"SQLite format 3\x00")

    results = LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path)
    assert any(
        r.library_type == LibraryType.REKORDBOX and "export.pdb" in r.indicators[0] for r in results
    )


def test_detect_serato_serato_folder(tmp_path: Path) -> None:
    """Detect Serato when Serato/database V2 layout exists."""
    serato = tmp_path / "Serato"
    serato.mkdir()
    (serato / "database V2").write_bytes(b"stub")

    results = LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path)
    assert any(r.library_type == LibraryType.SERATO for r in results)


def test_detect_serato_underscore_folder(tmp_path: Path) -> None:
    """Detect Serato _Serato_ directory."""
    (tmp_path / "_Serato_").mkdir()
    (tmp_path / "_Serato_" / "database V2").write_bytes(b"x")

    results = LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path)
    assert any(r.library_type == LibraryType.SERATO and r.confidence >= 0.9 for r in results)


def test_empty_mount_returns_no_libraries(tmp_path: Path) -> None:
    """Empty mount produces no library detections."""
    results = LibraryDiscovery().detect_on_mount(tmp_path)
    assert results == []


def test_missing_mount_returns_empty() -> None:
    """Non-existent mount path returns empty list."""
    results = LibraryDiscovery().detect_on_mount(Path("/nonexistent_mount_xyz"))
    assert results == []
