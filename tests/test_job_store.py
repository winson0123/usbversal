"""Tests for persisted job metadata."""

import json
from pathlib import Path

import pytest

from app.jobs.exceptions import JobNotFoundError, JobNotResumableError
from app.jobs.models import JobCheckpoint, JobRecord, JobState
from app.jobs.serialization import record_from_dict, record_summary, record_to_dict
from app.jobs.store import JobStore


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """JobStore persists and reloads a job record."""
    store = JobStore(tmp_path)
    record = JobRecord(
        job_id="abc123",
        job_type="scan",
        state=JobState.RUNNING,
        parameters={"mount": "/mnt/usb"},
        checkpoint=JobCheckpoint(step_index=1, step_name="scan_complete"),
    )
    store.save(record)

    loaded = store.load("abc123")
    assert loaded.job_id == "abc123"
    assert loaded.state == JobState.RUNNING
    assert loaded.parameters["mount"] == "/mnt/usb"
    assert loaded.checkpoint.step_name == "scan_complete"


def test_request_cancel_pending_job(tmp_path: Path) -> None:
    """Cancelling a pending job marks it cancelled immediately."""
    store = JobStore(tmp_path)
    record = JobRecord(
        job_id="pending1",
        job_type="scan",
        state=JobState.PENDING,
        parameters={},
    )
    store.save(record)

    updated = store.request_cancel("pending1")
    assert updated.state == JobState.CANCELLED
    assert updated.cancel_requested is True


def test_request_cancel_running_sets_flag(tmp_path: Path) -> None:
    """Cancelling a running job sets cancel_requested without forcing state."""
    store = JobStore(tmp_path)
    record = JobRecord(
        job_id="run1",
        job_type="scan",
        state=JobState.RUNNING,
        parameters={},
    )
    store.save(record)

    updated = store.request_cancel("run1")
    assert updated.state == JobState.RUNNING
    assert updated.cancel_requested is True
    assert store.is_cancel_requested("run1") is True


def test_recover_interrupted_running_jobs(tmp_path: Path) -> None:
    """Stale running jobs are marked failed on recovery."""
    store = JobStore(tmp_path)
    record = JobRecord(
        job_id="stale1",
        job_type="scan",
        state=JobState.RUNNING,
        parameters={},
    )
    store.save(record)

    recovered = store.recover_interrupted()
    assert len(recovered) == 1
    assert recovered[0].state == JobState.FAILED
    assert "Interrupted" in (recovered[0].error or "")


def test_prepare_resume_resets_failed_job(tmp_path: Path) -> None:
    """Failed jobs can be reset to pending for resume."""
    store = JobStore(tmp_path)
    record = JobRecord(
        job_id="fail1",
        job_type="scan",
        state=JobState.FAILED,
        parameters={"mount": "/tmp"},
        error="boom",
    )
    store.save(record)

    prepared = store.prepare_resume("fail1")
    assert prepared.state == JobState.PENDING
    assert prepared.error is None
    assert prepared.cancel_requested is False


def test_prepare_resume_rejects_completed(tmp_path: Path) -> None:
    """Completed jobs cannot be resumed."""
    store = JobStore(tmp_path)
    record = JobRecord(
        job_id="done1",
        job_type="scan",
        state=JobState.COMPLETED,
        parameters={},
    )
    store.save(record)

    with pytest.raises(JobNotResumableError):
        store.prepare_resume("done1")


def test_load_missing_job_raises(tmp_path: Path) -> None:
    """Loading an unknown job id raises JobNotFoundError."""
    store = JobStore(tmp_path)
    with pytest.raises(JobNotFoundError):
        store.load("missing")


def test_record_json_format(tmp_path: Path) -> None:
    """Persisted JSON contains checkpoint and cancel metadata."""
    store = JobStore(tmp_path)
    record = JobRecord(
        job_id="json1",
        job_type="scan",
        state=JobState.COMPLETED,
        parameters={"mount": "/mnt/usb"},
        checkpoint=JobCheckpoint(step_index=1, step_name="scan_complete"),
    )
    store.save(record)

    data = json.loads((tmp_path / "json1.json").read_text(encoding="utf-8"))
    assert data["checkpoint"]["step_name"] == "scan_complete"
    assert record_summary(record_from_dict(data))["job_id"] == "json1"


def test_record_to_dict_serializes_scan_result(tmp_path: Path) -> None:
    """ScanResult values are converted to dicts for persistence."""
    from app.core.domain import MountPoint
    from app.services.scan_service import ScanResult

    record = JobRecord(
        job_id="r1",
        job_type="scan",
        state=JobState.COMPLETED,
        parameters={},
        result=ScanResult(
            mounts=(MountPoint(path=tmp_path, source="user_specified"),),
            libraries=(),
            events=(),
        ),
    )
    data = record_to_dict(record)
    assert data["result"]["mounts"][0]["path"] == str(tmp_path.resolve())
