"""Opt-in smoke test for a PyInstaller release build."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "dist" / "usbversal"
SPEC = ROOT / "packaging" / "usbversal.spec"


@pytest.mark.skipif(
    os.environ.get("USBVERSAL_PACKAGING_BUILD") != "1",
    reason="Set USBVERSAL_PACKAGING_BUILD=1 to run a full PyInstaller build",
)
def test_pyinstaller_build() -> None:
    """Build usbversal with PyInstaller (slow; opt-in release check)."""
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)],
        cwd=ROOT,
        check=True,
        timeout=600,
    )
    assert BINARY.is_file()
    assert BINARY.stat().st_size > 0
