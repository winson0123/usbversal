"""Tests for sync failure listing and the host error.log."""

from pathlib import Path

from app.services.sync_errors import (
    SyncFailure,
    failures_from_report,
    format_failure_lines,
    write_error_log,
)
from app.services.sync_service import PlaylistSyncResult, SyncReport


def _report(**overrides) -> SyncReport:
    """Build a SyncReport with defaults a test can override."""
    fields = {
        "mount": Path("/mnt/usb"),
        "dry_run": False,
        "backup_id": "20260101T000000Z",
        "records_added": 0,
        "results": (),
        "analysis_errors": (),
    }
    fields.update(overrides)
    return SyncReport(**fields)


def test_failures_from_report_splits_title_path_and_reason() -> None:
    """Analysis errors become filename, path, and reason."""
    report = _report(analysis_errors=("Contents/Artist/Song.mp3: bad grid",))
    (failure,) = failures_from_report(report)
    assert failure.title == "Song.mp3"
    assert failure.path == "Contents/Artist/Song.mp3"
    assert failure.reason == "bad grid"


def test_failures_from_report_includes_crate_errors() -> None:
    """A crate that failed to write is listed with the playlist name."""
    report = _report(
        results=(PlaylistSyncResult(1, "Untagged", "WONSIN%%Untagged", 0, "disk full"),)
    )
    (failure,) = failures_from_report(report)
    assert failure.title == "Untagged"
    assert failure.path == "WONSIN%%Untagged"
    assert failure.reason == "disk full"


def test_format_failure_lines_is_title_path_reason() -> None:
    """The Done log and error.log share the same three-line block."""
    text = format_failure_lines(SyncFailure("Song.mp3", "Contents/Song.mp3", "too tight"))
    assert text == "Song.mp3\nContents/Song.mp3\ntoo tight"


def test_write_error_log_sits_next_to_host_backups(tmp_path: Path, monkeypatch) -> None:
    """error.log is written under the volume's host backup directory."""
    monkeypatch.setenv("USBVERSAL_BACKUP_ROOT", str(tmp_path / "host-backups"))
    mount = tmp_path / "WONSIN"
    mount.mkdir()
    failures = (SyncFailure("Song.mp3", "Contents/Song.mp3", "too tight"),)

    written = write_error_log(mount, failures, backup_id="20260101T000000Z")

    assert written is not None
    assert written.name == "error.log"
    assert written.parent.name == "WONSIN"
    text = written.read_text(encoding="utf-8")
    assert "backup_id=20260101T000000Z" in text
    assert "Song.mp3" in text
    assert "Contents/Song.mp3" in text
    assert "too tight" in text


def test_write_error_log_skips_an_empty_run(tmp_path: Path, monkeypatch) -> None:
    """A clean sync does not create error.log."""
    monkeypatch.setenv("USBVERSAL_BACKUP_ROOT", str(tmp_path / "host-backups"))
    assert write_error_log(tmp_path / "WONSIN", ()) is None
    assert not (tmp_path / "host-backups").exists()
