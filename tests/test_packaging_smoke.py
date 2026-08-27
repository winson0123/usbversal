"""Smoke tests for PyInstaller release binary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "dist" / "usbversal"
SPEC = ROOT / "packaging" / "usbversal.spec"


def test_packaging_spec_exists() -> None:
    """Release spec file is present for PyInstaller builds."""
    assert SPEC.is_file()


@pytest.mark.skipif(
    not BINARY.is_file(),
    reason="Run ./scripts/build-release.sh to build dist/usbversal",
)
def test_usbversal_binary_is_built() -> None:
    """
    Built executable exists and is non-empty.

    Requires a prior PyInstaller build at dist/usbversal. The binary
    launches the TUI; there is no --help command list to assert.
    """
    assert BINARY.is_file()
    assert BINARY.stat().st_size > 0


@pytest.mark.skipif(
    os.environ.get("USBVERSAL_PACKAGING_BUILD") != "1",
    reason="Set USBVERSAL_PACKAGING_BUILD=1 to run full PyInstaller build in CI",
)
def test_pyinstaller_build() -> None:
    """
    Build usbversal with PyInstaller (slow; opt-in).

    Intended for release validation, not default pytest runs.
    """
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)],
        cwd=ROOT,
        check=True,
        timeout=600,
    )
    assert BINARY.is_file()
    assert BINARY.stat().st_size > 0
