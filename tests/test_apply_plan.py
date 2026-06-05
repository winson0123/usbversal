"""Tests for apply plan loading."""

import json
from pathlib import Path

import pytest

from app.core.apply_plan import ApplyPlanError, load_apply_plan


def test_load_apply_plan_migrate_playlist(tmp_path: Path) -> None:
    """load_apply_plan parses migrate_playlist operations."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": 1,
                "operations": [
                    {"op": "migrate_playlist", "playlist_id": 1, "overwrite": True},
                ],
            },
        ),
        encoding="utf-8",
    )
    plan = load_apply_plan(plan_path)
    assert plan.version == 1
    assert len(plan.operations) == 1
    op = plan.operations[0]
    assert op.playlist_id == 1
    assert op.playlist_name is None
    assert op.overwrite is True


def test_load_apply_plan_requires_playlist_selector(tmp_path: Path) -> None:
    """migrate_playlist must specify playlist_id or playlist_name."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({"version": 1, "operations": [{"op": "migrate_playlist"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ApplyPlanError, match="playlist_id or playlist_name"):
        load_apply_plan(plan_path)


def test_load_apply_plan_rejects_unknown_op(tmp_path: Path) -> None:
    """Unknown operation types are rejected."""
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": 1,
                "operations": [{"op": "analyze_all"}],
            },
        ),
        encoding="utf-8",
    )
    with pytest.raises(ApplyPlanError, match="unknown op"):
        load_apply_plan(plan_path)
