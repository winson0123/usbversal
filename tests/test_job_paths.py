"""Tests for runtime job directory resolution."""

from pathlib import Path

from app.jobs.paths import get_jobs_dir, get_runtime_base_dir


def test_get_jobs_dir_honors_override(tmp_path: Path, monkeypatch) -> None:
    """USBversal_JOBS_DIR overrides the default jobs location."""
    monkeypatch.setenv("USBversal_JOBS_DIR", str(tmp_path / "custom"))
    assert get_jobs_dir() == tmp_path / "custom"


def test_get_jobs_dir_default_is_beside_runtime_base(monkeypatch) -> None:
    """Default jobs directory is a jobs/ folder under the runtime base."""
    monkeypatch.delenv("USBversal_JOBS_DIR", raising=False)
    base = get_runtime_base_dir()
    assert get_jobs_dir() == base / "jobs"


def test_runtime_base_dir_is_repo_root_under_pytest() -> None:
    """Under pytest, runtime base resolves to the repository root."""
    base = get_runtime_base_dir()
    assert (base / "app" / "jobs" / "paths.py").is_file()
