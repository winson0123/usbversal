"""Tests for jobs CLI commands."""

import json
import re
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.cli.main import main
from app.jobs.models import JobRecord, JobState
from app.jobs.store import JobStore


def test_jobs_list_empty(tmp_path: Path, monkeypatch) -> None:
    """jobs list reports no jobs when directory is empty."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with patch("sys.stdout", new_callable=StringIO) as stdout:
        code = main(["jobs", "list"])
    assert code == 0
    assert "No persisted jobs" in stdout.getvalue()


def test_jobs_list_json(tmp_path: Path, monkeypatch) -> None:
    """jobs list --json prints persisted job summaries."""
    store = JobStore(tmp_path / "usbversal" / "jobs")
    store.save(
        JobRecord(
            job_id="job123",
            job_type="scan",
            state=JobState.COMPLETED,
            parameters={"mount": "/mnt/usb"},
        )
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    with patch("sys.stdout", new_callable=StringIO) as stdout:
        code = main(["jobs", "list", "--json"])
    assert code == 0
    data = json.loads(stdout.getvalue())
    assert len(data) == 1
    assert data[0]["job_id"] == "job123"


def test_jobs_cancel(tmp_path: Path, monkeypatch) -> None:
    """jobs cancel requests cancellation for a persisted job."""
    store = JobStore(tmp_path / "usbversal" / "jobs")
    store.save(
        JobRecord(
            job_id="cancelme",
            job_type="scan",
            state=JobState.PENDING,
            parameters={},
        )
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    with patch("sys.stdout", new_callable=StringIO) as stdout:
        code = main(["jobs", "cancel", "cancelme"])
    assert code == 0
    assert "cancelme" in stdout.getvalue()
    assert store.load("cancelme").state == JobState.CANCELLED


def test_jobs_resume_scan(tmp_path: Path, monkeypatch) -> None:
    """jobs resume re-runs a failed scan job idempotently."""
    (tmp_path / "mount" / "PIONEER" / "rekordbox").mkdir(parents=True)
    (tmp_path / "mount" / "PIONEER" / "rekordbox" / "master.db").write_bytes(b"")

    jobs_dir = tmp_path / "cfg" / "usbversal" / "jobs"
    store = JobStore(jobs_dir)
    store.save(
        JobRecord(
            job_id="resume1",
            job_type="scan",
            state=JobState.FAILED,
            parameters={"mount": str(tmp_path / "mount")},
            error="Interrupted",
        )
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))

    with patch("sys.stdout", new_callable=StringIO) as stdout:
        code = main(["jobs", "resume", "resume1", "--json"])
    assert code == 0
    output = stdout.getvalue()
    match = re.search(r'\{\n  "job_id"', output)
    assert match is not None
    data = json.loads(output[match.start() :])
    assert data["state"] == "completed"
    assert store.load("resume1").checkpoint.step_name == "scan_complete"
