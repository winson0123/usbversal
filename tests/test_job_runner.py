"""Tests for JobRunner, registry, and scan job."""

from pathlib import Path

import pytest

from app.jobs.exceptions import JobNotFoundError, UnknownJobTypeError
from app.jobs.models import JobContext, JobRecord, JobState
from app.jobs.registry import JobRegistry
from app.jobs.runner import JobRunner


@pytest.mark.asyncio
async def test_scan_job_completes(tmp_path: Path) -> None:
    """JobRunner runs scan job and stores ScanResult."""
    (tmp_path / "PIONEER" / "rekordbox").mkdir(parents=True)
    (tmp_path / "PIONEER" / "rekordbox" / "master.db").write_bytes(b"")

    events: list[str] = []
    runner = JobRunner(emit=lambda event: events.append(type(event).__name__))

    job_id = await runner.start("scan", {"mount": str(tmp_path)})
    record = await runner.wait(job_id)

    assert record.state == JobState.COMPLETED
    assert record.result is not None
    assert len(record.result.libraries) >= 1
    assert "JobStarted" in events
    assert "JobProgress" in events
    assert "JobCompleted" in events


@pytest.mark.asyncio
async def test_scan_job_emits_library_events(tmp_path: Path) -> None:
    """Scan job forwards library scan events through the job emitter."""
    (tmp_path / "PIONEER" / "rekordbox").mkdir(parents=True)
    (tmp_path / "PIONEER" / "rekordbox" / "master.db").write_bytes(b"")

    captured: list[str] = []

    def capture(event) -> None:
        captured.append(type(event).__name__)

    runner = JobRunner(emit=capture)
    job_id = await runner.start("scan", {"mount": str(tmp_path)})
    await runner.wait(job_id)

    assert "JobStarted" in captured
    assert "LibraryScanStarted" in captured
    assert "LibraryScanCompleted" in captured


@pytest.mark.asyncio
async def test_unknown_job_type_raises() -> None:
    """Starting an unregistered job type raises UnknownJobTypeError."""
    runner = JobRunner()
    with pytest.raises(UnknownJobTypeError):
        await runner.start("missing")


@pytest.mark.asyncio
async def test_wait_unknown_job_raises() -> None:
    """Waiting on an unknown job id raises JobNotFoundError."""
    runner = JobRunner()
    with pytest.raises(JobNotFoundError):
        await runner.wait("does-not-exist")


@pytest.mark.asyncio
async def test_cancelled_job_marks_cancelled(tmp_path: Path) -> None:
    """Cooperative cancel marks the job as cancelled."""
    (tmp_path / "PIONEER" / "rekordbox").mkdir(parents=True)
    (tmp_path / "PIONEER" / "rekordbox" / "master.db").write_bytes(b"")

    started = False

    async def slow_scan(ctx: JobContext) -> None:
        nonlocal started
        started = True
        ctx.check_cancelled()

    runner = JobRunner(handlers={"scan": slow_scan})
    job_id = await runner.start("scan", {"mount": str(tmp_path)})
    runner.cancel(job_id)
    record = await runner.wait(job_id)

    assert started
    assert record.state == JobState.CANCELLED


@pytest.mark.asyncio
async def test_failed_job_stores_error() -> None:
    """Handler exceptions mark the job failed with an error message."""

    async def failing(_ctx: JobContext) -> None:
        raise ValueError("boom")

    runner = JobRunner(handlers={"scan": failing})
    job_id = await runner.start("scan", {})
    record = await runner.wait(job_id)

    assert record.state == JobState.FAILED
    assert record.error == "boom"


def test_registry_list_jobs() -> None:
    """Registry returns all records in insertion order."""
    registry = JobRegistry()
    registry.add(JobRecord("a", "scan", JobState.PENDING, {}))
    registry.add(JobRecord("b", "scan", JobState.PENDING, {}))
    assert [r.job_id for r in registry.list_all()] == ["a", "b"]


def test_run_scan_job_sync(tmp_path: Path, monkeypatch) -> None:
    """Synchronous CLI helper returns ScanResult."""
    from app.jobs.paths import get_jobs_dir
    from app.jobs.scan_cli import run_scan_job_sync
    from app.jobs.store import JobStore

    monkeypatch.setenv("USBVERSAL_JOBS_DIR", str(tmp_path / "jobs"))
    jobs_dir = get_jobs_dir()
    store = JobStore(jobs_dir)

    (tmp_path / "PIONEER" / "rekordbox").mkdir(parents=True)
    (tmp_path / "PIONEER" / "rekordbox" / "master.db").write_bytes(b"")

    result = run_scan_job_sync(mount=str(tmp_path), store=store)
    assert len(result.mounts) == 1
    assert len(list(jobs_dir.glob("*.json"))) == 1
