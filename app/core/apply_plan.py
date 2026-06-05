"""Apply-plan file schema and loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ApplyPlanError(ValueError):
    """Raised when a plan file is invalid or unsupported."""


@dataclass(frozen=True)
class MigratePlaylistOperation:
    """
    Copy one Rekordbox playlist to a Serato crate.

    Attributes:
        playlist_id: Rekordbox playlist id (optional if playlist_name set).
        playlist_name: Exact Rekordbox playlist name (optional if playlist_id set).
        overwrite: Replace an existing Subcrates/<name>.crate when True.
    """

    playlist_id: int | None
    playlist_name: str | None
    overwrite: bool


ApplyOperation = MigratePlaylistOperation


@dataclass(frozen=True)
class ApplyPlan:
    """
    Parsed apply plan ready for execution.

    Attributes:
        version: Plan schema version (currently 1).
        mount: Optional mount path from the file; validated against CLI --mount.
        operations: Ordered list of operations to run.
        source_path: Path the plan was loaded from.
    """

    version: int
    mount: str | None
    operations: tuple[ApplyOperation, ...]
    source_path: Path


def _parse_migrate_playlist(raw: dict[str, Any], index: int) -> MigratePlaylistOperation:
    """
    Parse one migrate_playlist operation from plan JSON.

    Args:
        raw: Operation object from the plan file.
        index: Zero-based operation index (for error messages).

    Returns:
        MigratePlaylistOperation instance.

    Raises:
        ApplyPlanError: Missing playlist selector or invalid fields.
    """
    playlist_id = raw.get("playlist_id")
    playlist_name = raw.get("playlist_name")
    if playlist_id is None and playlist_name is None:
        msg = f"operations[{index}]: migrate_playlist requires playlist_id or playlist_name"
        raise ApplyPlanError(msg)
    if playlist_id is not None and not isinstance(playlist_id, int):
        msg = f"operations[{index}]: playlist_id must be an integer"
        raise ApplyPlanError(msg)
    if playlist_name is not None and not isinstance(playlist_name, str):
        msg = f"operations[{index}]: playlist_name must be a string"
        raise ApplyPlanError(msg)
    overwrite = raw.get("overwrite", False)
    if not isinstance(overwrite, bool):
        msg = f"operations[{index}]: overwrite must be a boolean"
        raise ApplyPlanError(msg)
    return MigratePlaylistOperation(
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        overwrite=overwrite,
    )


def load_apply_plan(path: str | Path) -> ApplyPlan:
    """
    Load and validate an apply plan JSON file.

    Args:
        path: Path to a UTF-8 JSON plan file.

    Returns:
        Parsed ApplyPlan.

    Raises:
        ApplyPlanError: Invalid schema or unsupported version.
        OSError: File read failure.
        json.JSONDecodeError: Malformed JSON.
    """
    plan_path = Path(path).resolve()
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ApplyPlanError("Plan root must be a JSON object")

    version = data.get("version")
    if version != 1:
        raise ApplyPlanError(f"Unsupported plan version: {version!r} (expected 1)")

    mount = data.get("mount")
    if mount is not None and not isinstance(mount, str):
        raise ApplyPlanError("mount must be a string when present")

    raw_ops = data.get("operations")
    if not isinstance(raw_ops, list) or not raw_ops:
        raise ApplyPlanError("operations must be a non-empty array")

    operations: list[ApplyOperation] = []
    for index, raw in enumerate(raw_ops):
        if not isinstance(raw, dict):
            raise ApplyPlanError(f"operations[{index}] must be an object")
        op_type = raw.get("op")
        if op_type == "migrate_playlist":
            operations.append(_parse_migrate_playlist(raw, index))
        else:
            raise ApplyPlanError(f"operations[{index}]: unknown op {op_type!r}")

    return ApplyPlan(
        version=version,
        mount=mount,
        operations=tuple(operations),
        source_path=plan_path,
    )
