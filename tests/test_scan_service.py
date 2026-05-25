"""Tests for scan orchestration and events."""

from pathlib import Path

from app.core.events import (
    LibraryDetected,
    LibraryScanCompleted,
    LibraryScanStarted,
)
from app.services.scan_service import run_scan


def test_run_scan_emits_events(tmp_path: Path) -> None:
    """run_scan emits started, detected (if any), and completed events."""
    (tmp_path / "PIONEER" / "rekordbox").mkdir(parents=True)
    (tmp_path / "PIONEER" / "rekordbox" / "master.db").write_bytes(b"")

    captured: list = []

    def capture(event) -> None:
        captured.append(type(event).__name__)

    result = run_scan(mount=str(tmp_path), emit=capture)

    assert "LibraryScanStarted" in captured
    assert "LibraryScanCompleted" in captured
    assert len(result.mounts) == 1
    assert result.mounts[0].path == tmp_path.resolve()
    assert len(result.libraries) >= 1
    assert result.libraries[0].library_type.value == "rekordbox"


def test_run_scan_json_serializable(tmp_path: Path) -> None:
    """ScanResult.to_dict is JSON-friendly."""
    result = run_scan(mount=str(tmp_path))
    data = result.to_dict()
    assert "mounts" in data
    assert "libraries" in data
    assert data["event_count"] >= 2  # started + completed; detections optional


def test_event_dataclasses_to_dict() -> None:
    """Event types serialize via to_dict."""
    started = LibraryScanStarted(mounts=("/mnt/usb",))
    assert started.to_dict()["mounts"] == ("/mnt/usb",)

    detected = LibraryDetected(
        path="/mnt/usb/lib",
        library_type="rekordbox",
        confidence=0.9,
        mount_path="/mnt/usb",
        indicators=("master.db",),
    )
    assert detected.to_dict()["confidence"] == 0.9

    completed = LibraryScanCompleted(mount_count=1, library_count=0)
    assert completed.to_dict()["library_count"] == 0
