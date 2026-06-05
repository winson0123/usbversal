"""Tests for apply service and CLI."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from app.cli.main import main
from app.core.apply_plan import ApplyPlanError
from app.services.apply_service import ApplyOperationResult, ApplyResult, apply_plan_file
from app.services.migration_service import PlaylistMigrationPlan, PlaylistMigrationResult


def test_apply_plan_file_dry_run(tmp_path: Path) -> None:
    """apply_plan_file runs migrate_playlist ops in dry-run mode."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": 1,
                "mount": str(tmp_path),
                "operations": [
                    {"op": "migrate_playlist", "playlist_name": "Pocket"},
                ],
            },
        ),
        encoding="utf-8",
    )
    migration = PlaylistMigrationResult(
        plan=PlaylistMigrationPlan(
            playlist_id=1,
            playlist_name="Pocket",
            crate_name="Pocket",
            serato_paths=("Contents/a.mp3",),
            skipped_paths=(),
            rekordbox_paths=("/Contents/a.mp3",),
        ),
        backup=None,
        crate_path=None,
        dry_run=True,
    )
    with patch(
        "app.services.apply_service.migrate_playlist_to_crate",
        return_value=migration,
    ) as migrate:
        result = apply_plan_file(tmp_path, plan_path, dry_run=True)

    migrate.assert_called_once()
    assert result.dry_run is True
    assert result.success_count == 1
    assert result.operations[0].result is not None
    assert result.operations[0].result["playlist_name"] == "Pocket"


def test_apply_plan_mount_mismatch(tmp_path: Path) -> None:
    """apply_plan_file rejects mount mismatch between plan and CLI."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": 1,
                "mount": "/other/usb",
                "operations": [
                    {"op": "migrate_playlist", "playlist_id": 1},
                ],
            },
        ),
        encoding="utf-8",
    )
    with pytest.raises(ApplyPlanError, match="does not match"):
        apply_plan_file(tmp_path, plan_path, dry_run=True)


def test_apply_cli_json_dry_run(tmp_path: Path) -> None:
    """apply --dry-run --json prints structured results."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": 1,
                "operations": [{"op": "migrate_playlist", "playlist_id": 1}],
            },
        ),
        encoding="utf-8",
    )
    apply_result = ApplyResult(
        plan_path=plan_path,
        mount=tmp_path,
        dry_run=True,
        operations=(
            ApplyOperationResult(
                index=0,
                op="migrate_playlist",
                result={"playlist_name": "Pocket", "serato_track_count": 1},
                error=None,
            ),
        ),
    )
    with patch("app.cli.main.apply_plan_file", return_value=apply_result):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            code = main(
                [
                    "apply",
                    "--mount",
                    str(tmp_path),
                    "--plan",
                    str(plan_path),
                    "--dry-run",
                    "--json",
                ],
            )
    assert code == 0
    data = json.loads(stdout.getvalue())
    assert data["dry_run"] is True
    assert data["success_count"] == 1
