"""Filesystem paths for persisted job metadata."""

import os
from pathlib import Path


def get_jobs_dir() -> Path:
    """
    Return the directory used for persisted job JSON records.

    Uses ``$XDG_CONFIG_HOME/usbversal/jobs`` when set, otherwise
    ``~/.config/usbversal/jobs``.

    Returns:
        Path to the jobs directory (created by callers when writing).
    """
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    return base / "usbversal" / "jobs"
