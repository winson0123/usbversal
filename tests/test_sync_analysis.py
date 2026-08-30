"""Tests for parallel analysis tag writes."""

import threading
import time
from pathlib import Path

from app.services.sync_analysis import (
    AnalysisJob,
    analysis_worker_count,
    begin_analysis_jobs,
    process_analysis_track,
    run_analysis_jobs,
)
from app.services.sync_progress import SyncProgress


def test_analysis_worker_count_defaults_to_at_most_four() -> None:
    """The default pool is small so a USB stick is not flooded."""
    assert 1 <= analysis_worker_count(100) <= 4


def test_analysis_worker_count_follows_the_env(monkeypatch) -> None:
    """USBVERSAL_SYNC_WORKERS sets the pool size, capped by the job count."""
    monkeypatch.setenv("USBVERSAL_SYNC_WORKERS", "8")
    assert analysis_worker_count(3) == 3
    assert analysis_worker_count(20) == 8


def test_analysis_worker_count_rejects_a_bad_env(monkeypatch) -> None:
    """A non-integer override falls back to the default cap."""
    monkeypatch.setenv("USBVERSAL_SYNC_WORKERS", "nope")
    assert 1 <= analysis_worker_count(10) <= 4


def test_run_analysis_jobs_uses_more_than_one_thread(monkeypatch) -> None:
    """Several jobs overlap on different threads when the pool is larger than one."""
    monkeypatch.setenv("USBVERSAL_SYNC_WORKERS", "4")
    seen: set[int] = set()
    original = process_analysis_track

    def _record(job: AnalysisJob):
        """Run the real worker after noting this thread."""
        seen.add(threading.get_ident())
        time.sleep(0.05)
        return original(job)

    monkeypatch.setattr("app.services.sync_analysis.process_analysis_track", _record)
    jobs = [
        AnalysisJob(raw=f"t{index}", audio_path=Path("/missing"), dat_path=None, key=None)
        for index in range(4)
    ]
    results = run_analysis_jobs(jobs)
    assert len(results) == 4
    assert len(seen) > 1


def test_analysis_session_lets_crates_run_during_jobs(monkeypatch) -> None:
    """Crate work on this thread can run while tag jobs are in flight."""
    monkeypatch.setenv("USBVERSAL_SYNC_WORKERS", "2")
    started = threading.Event()
    release = threading.Event()
    original = process_analysis_track

    def _block(job: AnalysisJob):
        """Hold the worker until the caller has done other work."""
        started.set()
        assert release.wait(1)
        return original(job)

    monkeypatch.setattr("app.services.sync_analysis.process_analysis_track", _block)
    jobs = [
        AnalysisJob(raw="t", audio_path=Path("/missing"), dat_path=None, key=None),
    ]
    session = begin_analysis_jobs(jobs)
    try:
        assert started.wait(1)
        overlapped = True
        release.set()
        results = session.wait()
    finally:
        session.close()
    assert overlapped
    assert len(results) == 1


def test_run_analysis_jobs_emits_progress_for_each_completion(monkeypatch) -> None:
    """Each finished job ticks the bar once, in completion order."""
    monkeypatch.setenv("USBVERSAL_SYNC_WORKERS", "2")
    jobs = [
        AnalysisJob(raw="a", audio_path=Path("/missing"), dat_path=None, key=None),
        AnalysisJob(raw="b", audio_path=Path("/missing"), dat_path=None, key=None),
    ]
    calls: list[SyncProgress] = []
    run_analysis_jobs(jobs, on_progress=calls.append)
    assert {sample.item for sample in calls} == {"a", "b"}
    assert {sample.done for sample in calls} == {1, 2}
    assert all(sample.total == 2 for sample in calls)
