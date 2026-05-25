"""CLI tests for rollback command."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.cli.main import main
from app.storage.rollback import RollbackResult


def test_rollback_json_output() -> None:
    """rollback --json prints valid JSON."""
    result = RollbackResult(
        backup_id="20260101T120000Z",
        backup_dir=Path("/mnt/usb/backups/20260101T120000Z"),
        restored_paths=("PIONEER/rekordbox/exportLibrary.db",),
        pre_rollback_backup_dir=None,
    )
    with patch("app.cli.main.rollback_mount_libraries", return_value=result):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            code = main(
                [
                    "rollback",
                    "--mount",
                    "/mnt/usb",
                    "--backup-id",
                    "20260101T120000Z",
                    "--json",
                ],
            )
    assert code == 0
    data = json.loads(stdout.getvalue())
    assert data["backup_id"] == "20260101T120000Z"
    assert data["restored_count"] == 1
