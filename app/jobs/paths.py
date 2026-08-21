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
    return path.name.startswith(("python", "pypy"))


def _package_root() -> Path:
    """Return the directory containing the ``app`` package."""
    return Path(__file__).resolve().parents[2]


def get_runtime_base_dir() -> Path:
    """
    Return the directory anchoring runtime files (jobs, etc.).

    Resolution order:
    - PyInstaller binary: directory containing ``sys.executable``
    - Entry point inside the ``app`` package (``python -m app.cli``):
      package root, **not** the package subdirectory holding ``__main__.py``
    - Virtualenv console script: package root, not ``.venv/bin``
    - Any other console script or ``.py`` entry: directory containing it
    - No usable ``sys.argv``: package root

    Returns:
        Base directory for colocated runtime data.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    root = _package_root()
    if sys.argv:
        entry = Path(sys.argv[0]).resolve()
        if entry.is_file() and not _is_python_interpreter(entry):
            base = entry.parent
            # ``python -m app.cli`` puts __main__.py's directory in argv[0],
            # which would scatter job records inside the source tree.
            if base.is_relative_to(root / "app"):
                return root
            if base.name == "bin" and (base.parent / "pyvenv.cfg").is_file():
                return root
            return base

    return root


def get_jobs_dir() -> Path:
    """
    Return the directory used for persisted job JSON records.

    Jobs are stored beside the running executable or application tree at
    ``<runtime_base>/jobs/``. Override with ``USBVERSAL_JOBS_DIR`` for tests.

    Returns:
        Path to the jobs directory (created by callers when writing).
    """
    override = os.environ.get("USBVERSAL_JOBS_DIR")
    if override:
        return Path(override)
    return get_runtime_base_dir() / "jobs"
