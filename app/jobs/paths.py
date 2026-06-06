"""Filesystem paths for persisted job metadata."""

import os
import sys
from pathlib import Path


def _is_python_interpreter(path: Path) -> bool:
    """
    Return True when path points to a Python interpreter executable.

    Args:
        path: Candidate executable path from ``sys.argv[0]``.

    Returns:
        True for names like ``python`` or ``python3.13``.
    """
    name = path.name
    return name == "python" or name.startswith("python") or name.startswith("pypy")


def get_runtime_base_dir() -> Path:
    """
    Return the directory anchoring runtime files (jobs, etc.).

    Resolution order:
    - PyInstaller binary: directory containing ``sys.executable``
    - Console script or ``.py`` entry: directory containing that file
    - Virtualenv console script: repository/package root (not ``.venv/bin``)
    - ``python -m app.cli``: repository/package root (parent of ``app/``)

    Returns:
        Base directory for colocated runtime data.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    if sys.argv:
        entry = Path(sys.argv[0]).resolve()
        if entry.is_file() and not _is_python_interpreter(entry):
            base = entry.parent
            if base.name == "bin" and (base.parent / "pyvenv.cfg").is_file():
                return Path(__file__).resolve().parents[2]
            return base

    return Path(__file__).resolve().parents[2]


def get_jobs_dir() -> Path:
    """
    Return the directory used for persisted job JSON records.

    Jobs are stored beside the running executable or application tree at
    ``<runtime_base>/jobs/``. Override with ``USBversal_JOBS_DIR`` for tests.

    Returns:
        Path to the jobs directory (created by callers when writing).
    """
    override = os.environ.get("USBversal_JOBS_DIR")
    if override:
        return Path(override)
    return get_runtime_base_dir() / "jobs"
