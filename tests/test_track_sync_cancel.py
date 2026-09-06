"""Tests for cooperative cancel during ANLZ cache warm."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.cancellation import (
    OperationCancelled,
    clear_quit_request,
    request_quit,
)
from app.services.track_sync import warm_analysis_ported_cache


@pytest.fixture(autouse=True)
def _reset_quit_flag() -> None:
    """
    Keep the process-wide quit flag clear around each test.

    Yields:
        None.
    """
    clear_quit_request()
    yield
    clear_quit_request()


def test_warm_analysis_raises_when_quit_already_requested(tmp_path: Path) -> None:
    """A warm that starts after quit must not open any files."""
    request_quit()
    with patch("app.services.track_sync._analysis_is_ported") as probe:
        with pytest.raises(OperationCancelled):
            warm_analysis_ported_cache(
                tmp_path,
                [("/Contents/a.mp3", None)],
                {},
            )
    probe.assert_not_called()


def test_warm_analysis_stops_mid_pool_without_waiting_for_every_track(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Quit during a parallel warm must return soon, not after all tracks.

    Workers block until quit; the warm loop must notice the flag on its
    poll interval and raise instead of draining the whole queue.
    """
    monkeypatch.setenv("USBVERSAL_SYNC_WORKERS", "4")
    started = threading.Event()
    release = threading.Event()
    calls = 0
    lock = threading.Lock()

    def slow_probe(dat_path, audio_path):
        """Block like a slow ANLZ/tag read until the test releases."""
        nonlocal calls
        with lock:
            calls += 1
            if calls == 1:
                started.set()
        release.wait(timeout=5)
        return True

    tracks = [(f"/Contents/t{i}.mp3", None) for i in range(20)]
    cache: dict[str, bool] = {}

    def run_warm() -> None:
        """Run warm on a side thread so the test can request quit."""
        with pytest.raises(OperationCancelled):
            warm_analysis_ported_cache(tmp_path, tracks, cache)

    with patch("app.services.track_sync._analysis_is_ported", slow_probe):
        worker = threading.Thread(target=run_warm)
        worker.start()
        assert started.wait(timeout=2.0)
        request_quit()
        began = time.monotonic()
        # Unblock in-flight probes so shutdown(wait=False) orphans finish.
        release.set()
        worker.join(timeout=2.0)
        elapsed = time.monotonic() - began

    assert not worker.is_alive()
    assert elapsed < 1.0
    assert len(cache) < len(tracks)
