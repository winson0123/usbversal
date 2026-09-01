"""Tests for sync failure listing and the host error.log."""

from pathlib import Path

from app.services.sync_errors import (
    SyncFailure,
    failures_from_report,
    format_failure_lines,
    write_error_log,
)
from app.services.sync_service import PlaylistSyncResult, SyncReport
from app.storage.host import host_volume_dir


def _report(**overrides) -> SyncReport:
    """Build a SyncReport with defaults a test can override."""
    fields = {
        "mount": Path("/mnt/usb"),
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


def test_write_error_log_sits_in_the_host_volume_dir(tmp_path: Path) -> None:
    """error.log is written under the volume's host data directory, not the USB."""
    mount = tmp_path / "WONSIN"
    mount.mkdir()
    failures = (SyncFailure("Song.mp3", "Contents/Song.mp3", "too tight"),)

    written = write_error_log(mount, failures)

    assert written is not None
    assert written == host_volume_dir(mount) / "error.log"
    assert written.parent.name == "WONSIN"
    assert not (mount / "error.log").exists()
    text = written.read_text(encoding="utf-8")
    assert "Song.mp3" in text
    assert "Contents/Song.mp3" in text
    assert "too tight" in text


def test_write_error_log_skips_an_empty_run(tmp_path: Path) -> None:
    """A clean sync does not create error.log."""
    mount = tmp_path / "WONSIN"
    mount.mkdir()
    assert write_error_log(mount, ()) is None
    assert not (host_volume_dir(mount) / "error.log").exists()
