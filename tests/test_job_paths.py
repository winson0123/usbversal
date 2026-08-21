"""Tests for runtime job directory resolution."""

import sys
from pathlib import Path

import pytest

from app.jobs.paths import get_jobs_dir, get_runtime_base_dir


def test_get_jobs_dir_honors_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """USBVERSAL_JOBS_DIR overrides the default jobs location."""
    monkeypatch.setenv("USBVERSAL_JOBS_DIR", str(tmp_path / "custom"))
    assert get_jobs_dir() == tmp_path / "custom"


def test_get_jobs_dir_default_is_beside_runtime_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default jobs directory is a jobs/ folder under the runtime base."""
    monkeypatch.delenv("USBVERSAL_JOBS_DIR", raising=False)
    base = get_runtime_base_dir()
    assert get_jobs_dir() == base / "jobs"


def test_runtime_base_dir_is_repo_root_under_pytest() -> None:
    """Under pytest, runtime base resolves to the repository root."""
    base = get_runtime_base_dir()
    assert (base / "app" / "jobs" / "paths.py").is_file()


def test_module_entry_uses_package_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    ``python -m app.cli`` anchors runtime data at the package root.

    sys.argv[0] is __main__.py's path in that mode, so taking its parent would
    scatter job records inside the source tree at app/cli/jobs/ -- which
    .gitignore's root-anchored /jobs/ rule does not cover.
    """
    root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("USBVERSAL_JOBS_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "argv", [str(root / "app" / "cli" / "__main__.py")])

    assert get_runtime_base_dir() == root
    assert get_jobs_dir() == root / "jobs"


def test_external_script_uses_its_own_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A console script outside the package anchors beside itself."""
    script = tmp_path / "usbversal"
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    monkeypatch.delenv("USBVERSAL_JOBS_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "argv", [str(script)])

    assert get_runtime_base_dir() == tmp_path
