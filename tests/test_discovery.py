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


def test_detect_serato_database_v2_file(tmp_path: Path) -> None:
    """A loose `database V2` file is detected on its own."""
    loose = tmp_path / "Music"
    loose.mkdir()
    (loose / "database V2").write_bytes(b"x")

    results = LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path)

    assert any(
        r.library_type == LibraryType.SERATO and r.path.name == "database V2" for r in results
    )


def test_serato_database_v2_under_serato_dir_outranks_plain_marker(tmp_path: Path) -> None:
    """`Serato/database V2` keeps the higher parent-qualified confidence."""
    serato = tmp_path / "Serato"
    serato.mkdir()
    (serato / "database V2").write_bytes(b"x")

    results = LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path)

    db_hits = [r for r in results if r.path.name == "database V2"]
    assert len(db_hits) == 1, "path should be deduplicated, not listed twice"
    assert db_hits[0].confidence == 0.90


def test_crate_files_only_count_inside_subcrates(tmp_path: Path) -> None:
    """A .crate outside a Subcrates/ ancestor is not a Serato signal."""
    stray = tmp_path / "Crates"
    stray.mkdir()
    (stray / "Z.crate").write_bytes(b"x")

    assert LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path) == []


def test_detection_is_case_insensitive_for_directories(tmp_path: Path) -> None:
    """Directory markers match regardless of case (vfat sticks vary)."""
    rb = tmp_path / "pioneer" / "REKORDBOX"
    rb.mkdir(parents=True)
    (rb / "export.pdb").write_bytes(b"x")

    results = LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path)

    assert any(r.library_type == LibraryType.REKORDBOX and r.confidence == 0.95 for r in results)


def test_higher_confidence_marker_wins_for_same_path(tmp_path: Path) -> None:
    """PIONEER/rekordbox (0.95) outranks the bare `rekordbox` marker (0.70)."""
    rb = tmp_path / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)

    results = LibraryDiscovery(max_depth=6).detect_on_mount(tmp_path)
    hits = [r for r in results if r.path == rb.resolve()]

    assert len(hits) == 1
    assert hits[0].confidence == 0.95
