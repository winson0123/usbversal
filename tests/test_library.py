"""Tests for mount probing and the session library handle."""

from pathlib import Path

import pytest

from app.core.domain import RekordboxDbFormat
from app.services.library import open_library, probe_mount
from tests.conftest import EMPTY_DATABASE_V2


def _rekordbox_stick(root: Path) -> Path:
    """Create a mount with a Rekordbox export present."""
    rb = root / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"stub")
    return root


def test_probe_returns_none_for_missing_path(tmp_path: Path) -> None:
    """A path that does not exist is not a stick."""
    assert probe_mount(tmp_path / "nope") is None


def test_probe_returns_none_for_empty_mount_point(tmp_path: Path) -> None:
    """An unplugged stick leaves an empty mount point behind; that is no stick."""
    assert probe_mount(tmp_path) is None


def test_probe_detects_rekordbox_only_stick(tmp_path: Path) -> None:
    """A plain Rekordbox export is a DJ USB that still needs Serato bootstrapping."""
    probe = probe_mount(_rekordbox_stick(tmp_path))

    assert probe is not None
    assert probe.is_dj_usb is True
    assert probe.is_supported is True
    assert probe.has_serato is False
    assert probe.rekordbox_format is RekordboxDbFormat.ONE_LIBRARY


def test_probe_detects_serato_alongside_rekordbox(tmp_path: Path) -> None:
    """Both libraries are reported when both are present."""
    _rekordbox_stick(tmp_path)
    serato = tmp_path / "_Serato_"
    serato.mkdir()
    (serato / "database V2").write_bytes(EMPTY_DATABASE_V2)

    probe = probe_mount(tmp_path)

    assert probe is not None
    assert probe.has_serato is True
    assert probe.serato_root == serato


def test_probe_reports_unsupported_pdb_format(tmp_path: Path) -> None:
    """A DeviceSQL-only stick is a DJ USB but unreadable."""
    rb = tmp_path / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "export.pdb").write_bytes(b"stub")

    probe = probe_mount(tmp_path)

    assert probe is not None
    assert probe.is_dj_usb is True
    assert probe.is_supported is False


def test_probe_non_dj_media_is_not_a_dj_usb(tmp_path: Path) -> None:
    """A stick with unrelated content is detected but not a DJ USB."""
    (tmp_path / "holiday.jpg").write_bytes(b"x")

    probe = probe_mount(tmp_path)

    assert probe is not None
    assert probe.is_dj_usb is False


def test_open_library_rejects_non_dj_mount(tmp_path: Path) -> None:
    """Opening a mount with no Rekordbox export fails."""
    (tmp_path / "holiday.jpg").write_bytes(b"x")
    with pytest.raises(FileNotFoundError):
        open_library(tmp_path)


def test_probe_serialises_for_json_output(tmp_path: Path) -> None:
    """to_dict exposes the verdict for machine-readable output."""
    probe = probe_mount(_rekordbox_stick(tmp_path))
    assert probe is not None

    payload = probe.to_dict()

    assert payload["is_dj_usb"] is True
    assert payload["has_serato"] is False
    assert payload["rekordbox_format"] == "exportLibrary.db"
