"""Async scan job handler."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.jobs.models import JobContext
from app.services.scan_service import ScanResult, run_scan

JobHandler = Callable[[JobContext], Awaitable[Any]]


async def run_scan_job(ctx: JobContext) -> ScanResult:
    """
    Run a library scan in a worker thread with cooperative cancel checks.

    Args:
        ctx: Job context with mount parameter and event emitters.

    Returns:
        ScanResult from the underlying scan orchestration.

    Raises:
        JobCancelledError: When cancellation is requested before or after scan.
    """
    ctx.check_cancelled()
    mount = ctx.parameters.get("mount")

    ctx.progress("Scan starting", current=0, total=1)

    result = await asyncio.to_thread(run_scan, mount=mount, emit=ctx.emit)

    ctx.check_cancelled()
    ctx.progress("Scan complete", current=1, total=1)
    ctx.update_checkpoint(
        step_index=1,
        step_name="scan_complete",
        partial_results={
            "mount_count": len(result.mounts),
            "library_count": len(result.libraries),
        },
    )
    return result
