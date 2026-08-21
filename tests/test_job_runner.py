"""Tests for the async job runner."""

import asyncio

import pytest

from app.core.event_bus import EventBus
from app.jobs.exceptions import JobCancelledError, JobNotFoundError, UnknownJobTypeError
from app.jobs.models import JobContext, JobRecord, JobState
from app.jobs.registry import JobRegistry
from app.jobs.runner import JobRunner


async def _echo(ctx: JobContext) -> str:
    """Emit one progress event and return a value."""
    ctx.check_cancelled()
    ctx.progress("working", current=1, total=1)
    return ctx.parameters.get("value", "done")


@pytest.mark.asyncio
async def test_job_completes_and_emits_lifecycle_events() -> None:
    """A handler runs to completion and publishes start/progress/complete."""
    events: list[str] = []
    bus = EventBus()
    bus.subscribe(lambda event: events.append(event.type))
    runner = JobRunner({"echo": _echo}, bus=bus)

    job_id = await runner.start("echo", {"value": "ok"})
    record = await runner.wait(job_id)

    assert record.state == JobState.COMPLETED
    assert record.result == "ok"
    assert events == ["job.started", "job.progress", "job.completed"]


@pytest.mark.asyncio
async def test_unknown_job_type_raises() -> None:
    """Starting an unregistered job type fails fast."""
    runner = JobRunner({})
    with pytest.raises(UnknownJobTypeError):
        await runner.start("missing")


@pytest.mark.asyncio
async def test_wait_unknown_job_raises() -> None:
    """Waiting on an unknown job id raises."""
    runner = JobRunner({})
    with pytest.raises(JobNotFoundError):
        await runner.wait("nope")


@pytest.mark.asyncio
async def test_cancel_marks_job_cancelled() -> None:
    """A cooperative handler observes the cancel flag and stops."""

    async def slow(ctx: JobContext) -> None:
        for _ in range(100):
            ctx.check_cancelled()
            await asyncio.sleep(0.01)

    runner = JobRunner({"slow": slow})
    job_id = await runner.start("slow")
    await asyncio.sleep(0.02)
    runner.cancel(job_id)
    record = await runner.wait(job_id)

    assert record.state == JobState.CANCELLED
    assert record.cancel_requested is True


@pytest.mark.asyncio
async def test_failed_job_stores_error() -> None:
    """A raising handler leaves the job failed with its message."""

    async def failing(ctx: JobContext) -> None:
        raise RuntimeError("boom")

    events: list[str] = []
    bus = EventBus()
    bus.subscribe(lambda event: events.append(event.type))
    runner = JobRunner({"bad": failing}, bus=bus)

    record = await runner.wait(await runner.start("bad"))

    assert record.state == JobState.FAILED
    assert record.error == "boom"
    assert "job.failed" in events


@pytest.mark.asyncio
async def test_cancel_before_run_short_circuits() -> None:
    """A handler raising JobCancelledError lands in the cancelled state."""

    async def cancels(ctx: JobContext) -> None:
        raise JobCancelledError(ctx.job_id)

    runner = JobRunner({"c": cancels})
    record = await runner.wait(await runner.start("c"))
    assert record.state == JobState.CANCELLED


def test_registry_lists_records_in_insertion_order() -> None:
    """The registry preserves insertion order."""
    registry = JobRegistry()
    for job_id in ("a", "b"):
        registry.add(
            JobRecord(job_id=job_id, job_type="echo", state=JobState.PENDING, parameters={})
        )
    assert [r.job_id for r in registry.list_all()] == ["a", "b"]
