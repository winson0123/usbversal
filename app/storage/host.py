"""Host-side paths that are not on the USB mount."""

from __future__ import annotations

import os
import re
from pathlib import Path

DATA_ROOT_ENV = "USBVERSAL_DATA_ROOT"
_VOLUME_KEY = re.compile(r"[^A-Za-z0-9._-]+")


def host_volume_dir(mount: Path) -> Path:
    """
    Return the host directory for this volume's logs.

    Uses ``USBVERSAL_DATA_ROOT`` when set, otherwise the platform user-data
    directory. Never defaults to a folder on the USB.

    Args:
        mount: Mount root; its name namespaces logs from different sticks.

    Returns:
        Absolute host directory (created by the caller as needed).
    """
    override = os.environ.get(DATA_ROOT_ENV)
    if override:
        base = Path(override)
    elif os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        base = base / "usbversal"
    else:
        base = Path.home() / ".local/share/usbversal"
    return (base / _volume_key(mount)).resolve()


def _volume_key(mount: Path) -> str:
    """
    Return a filesystem-safe directory name for a mount.

    Args:
        mount: Mount root.

    Returns:
        Label derived from the mount folder name.
    """
    name = mount.resolve().name.strip() or "usb"
    cleaned = _VOLUME_KEY.sub("_", name).strip("._")
    return cleaned or "usb"
