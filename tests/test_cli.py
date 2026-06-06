"""Tests for CLI entrypoint."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.cli.main import main
from app.core.domain import LibraryLocation, LibraryType, MountPoint
from app.services.scan_service import ScanResult


def test_scan_command_json_output() -> None:
    """scan --json prints valid JSON."""
    with patch("app.cli.main.run_scan_job_sync") as mock_scan:
        mock_scan.return_value = ScanResult(
            mounts=(MountPoint(path=Path("/mnt/usb"), source="user_specified"),),
            libraries=(
                LibraryLocation(
                    path=Path("/mnt/usb/PIONEER/rekordbox"),
                    library_type=LibraryType.REKORDBOX,
                    confidence=0.95,
                    mount_path=Path("/mnt/usb"),
                    indicators=("PIONEER/rekordbox directory",),
                ),
            ),
            events=(),
        )
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            code = main(["scan", "--mount", "/mnt/usb", "--json"])
        assert code == 0
        data = json.loads(stdout.getvalue())
        assert len(data["libraries"]) == 1
        assert data["libraries"][0]["type"] == "rekordbox"
