"""CLI tests for migrate-playlist command."""

import json
from io import StringIO
from unittest.mock import patch

from app.cli.main import main
from app.services.migration_service import PlaylistMigrationPlan, PlaylistMigrationResult


def test_migrate_playlist_json_dry_run() -> None:
    """migrate-playlist --dry-run --json prints plan summary."""
    plan = PlaylistMigrationPlan(
        playlist_id=1,
        playlist_name="Pocket",
        crate_name="Pocket",
        serato_paths=("Contents/a.mp3",),
        skipped_paths=(),
        rekordbox_paths=("/Contents/a.mp3",),
    )
    result = PlaylistMigrationResult(plan=plan, backup=None, crate_path=None, dry_run=True)
    with patch("app.cli.main.migrate_playlist_to_crate", return_value=result):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            code = main(
                [
                    "migrate-playlist",
                    "--mount",
                    "/mnt/usb",
                    "--playlist-id",
                    "1",
                    "--dry-run",
                    "--json",
                ],
            )
    assert code == 0
    data = json.loads(stdout.getvalue())
    assert data["dry_run"] is True
    assert data["playlist_name"] == "Pocket"
    assert data["serato_track_count"] == 1
