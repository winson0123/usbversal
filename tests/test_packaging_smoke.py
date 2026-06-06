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
def test_usbversal_binary_help() -> None:
    """
    Built executable responds to --help.

    Requires a prior PyInstaller build at dist/usbversal.
    """
    result = subprocess.run(
        [str(BINARY), "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "migrate-playlist" in result.stdout
    assert "apply" in result.stdout


@pytest.mark.skipif(
    os.environ.get("USBversal_PACKAGING_BUILD") != "1",
    reason="Set USBversal_PACKAGING_BUILD=1 to run full PyInstaller build in CI",
)
def test_pyinstaller_build_and_help() -> None:
    """
    Build usbversal with PyInstaller and verify --help (slow; opt-in).

    Intended for release validation, not default pytest runs.
    """
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)],
        cwd=ROOT,
        check=True,
        timeout=600,
    )
    assert BINARY.is_file()
    result = subprocess.run(
        [str(BINARY), "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
