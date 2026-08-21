"""Execute apply plans (batch operations on a mount)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from app.adapters.serato.writer import CrateExistsError
from app.core.apply_plan import ApplyPlan, ApplyPlanError, MigratePlaylistOperation, load_apply_plan
from app.services.migration_service import (
    MigrationError,
    PlaylistMigrationResult,
    migrate_playlist_to_crate,
)
from app.storage.mounts import resolve_mount_path

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ApplyOperationResult:
    """
    Outcome of one plan operation.

    Attributes:
        index: Zero-based position in the plan.
        op: Operation type string (e.g. migrate_playlist).
        result: Operation-specific payload (migration dict when successful).
        error: Error message when the operation failed.
    """

    index: int
    op: str
    result: dict[str, Any] | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize this operation outcome for JSON CLI output.

        Returns:
            Dict with op, index, and either result or error.
        """
        payload: dict[str, Any] = {"index": self.index, "op": self.op}
        if self.error is not None:
            payload["error"] = self.error
        else:
            payload["result"] = self.result
        return payload


@dataclass(frozen=True)
class ApplyResult:
    """
    Outcome of executing an apply plan.

    Attributes:
        plan_path: Source plan file path.
        mount: Resolved mount root used for execution.
        dry_run: True when no writes were performed.
        operations: Per-operation results in plan order.
    """

    plan_path: Path
    mount: Path
    dry_run: bool
    operations: tuple[ApplyOperationResult, ...]

    @property
    def success_count(self) -> int:
        """Return the number of operations that completed without error."""
        return sum(1 for op in self.operations if op.error is None)

    @property
    def failed_count(self) -> int:
        """Return the number of operations that failed."""
        return sum(1 for op in self.operations if op.error is not None)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the full apply result for JSON CLI output.

        Returns:
            Dict with summary counts and per-operation outcomes.
        """
        return {
            "dry_run": self.dry_run,
            "plan_path": str(self.plan_path),
            "mount": str(self.mount),
            "operation_count": len(self.operations),
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "operations": [op.to_dict() for op in self.operations],
        }


def _resolve_mount(cli_mount: str | Path, plan: ApplyPlan) -> Path:
    """
    Resolve mount path and validate against an optional plan mount field.

    Args:
        cli_mount: Mount from --mount CLI flag.
        plan: Loaded apply plan.

    Returns:
        Resolved absolute mount path.

    Raises:
        ApplyPlanError: Plan mount disagrees with CLI mount.
    """
    mount_path = resolve_mount_path(cli_mount)
    if plan.mount is not None:
        plan_mount = Path(plan.mount).resolve()
        if plan_mount != mount_path:
            msg = f"Plan mount {plan.mount!r} does not match --mount {cli_mount!r}"
            raise ApplyPlanError(msg)
    return mount_path


def _run_migrate_playlist(
    mount: Path,
    operation: MigratePlaylistOperation,
    *,
    dry_run: bool,
    backup_root: Path | None,
) -> PlaylistMigrationResult:
    """
    Execute one migrate_playlist operation.

    Args:
        mount: USB mount root.
        operation: Parsed migrate_playlist op.
        dry_run: Skip backup and writes when True.
        backup_root: Optional backups parent directory.

    Returns:
        PlaylistMigrationResult from the migration service.
    """
    return migrate_playlist_to_crate(
        mount,
        playlist_id=operation.playlist_id,
        playlist_name=operation.playlist_name,
        dry_run=dry_run,
        overwrite=operation.overwrite,
        backup_root=backup_root,
    )


def apply_plan_file(
    mount: str | Path,
    plan_path: str | Path,
    *,
    dry_run: bool = False,
    backup_root: str | Path | None = None,
    stop_on_error: bool = False,
) -> ApplyResult:
    """
    Load and execute an apply plan against a mount.

    Operations run sequentially in plan order. Each migrate_playlist op takes
    its own backup before writing (same as the migrate-playlist CLI).

    A failing operation is recorded on its ApplyOperationResult and the run
    continues, so the caller always learns which operations succeeded. Check
    ``failed_count`` to detect partial application.

    Args:
        mount: USB mount path (must match plan.mount when set).
        plan_path: JSON plan file path.
        dry_run: Validate and plan only; no backup or writes.
        backup_root: Optional backups parent directory.
        stop_on_error: Halt after the first failing operation instead of
            continuing. Earlier operations remain applied and reported.

    Returns:
        ApplyResult with per-operation outcomes.

    Raises:
        ApplyPlanError: Invalid plan file, mount mismatch, or unsupported op.
        OSError: Filesystem failures, including backup creation.
        BackupVerificationError: A backup could not be verified before a write.
    """
    plan = load_apply_plan(plan_path)
    mount_path = _resolve_mount(mount, plan)
    backup = Path(backup_root).resolve() if backup_root else None

    results: list[ApplyOperationResult] = []
    for index, operation in enumerate(plan.operations):
        if not isinstance(operation, MigratePlaylistOperation):
            msg = f"Unsupported operation type at index {index}"
            raise ApplyPlanError(msg)

        try:
            migration = _run_migrate_playlist(
                mount_path,
                operation,
                dry_run=dry_run,
                backup_root=backup,
            )
        except (MigrationError, CrateExistsError) as exc:
            logger.warning(
                "apply_operation_failed",
                index=index,
                op="migrate_playlist",
                error=str(exc),
            )
            results.append(
                ApplyOperationResult(
                    index=index,
                    op="migrate_playlist",
                    result=None,
                    error=str(exc),
                ),
            )
            if stop_on_error:
                break
            continue

        results.append(
            ApplyOperationResult(
                index=index,
                op="migrate_playlist",
                result=migration.to_dict(),
                error=None,
            ),
        )
        logger.info(
            "apply_operation_completed",
            index=index,
            op="migrate_playlist",
            playlist=migration.plan.playlist_name,
            dry_run=dry_run,
        )

    return ApplyResult(
        plan_path=Path(plan_path).resolve(),
        mount=mount_path,
        dry_run=dry_run,
        operations=tuple(results),
    )
