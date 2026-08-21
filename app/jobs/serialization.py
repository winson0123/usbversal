"""Serialize and deserialize job records for JSON persistence."""

from dataclasses import asdict
from typing import Any

from app.jobs.models import JobCheckpoint, JobRecord, JobState


def record_to_dict(record: JobRecord) -> dict[str, Any]:
    """
    Convert a JobRecord to a JSON-serializable dictionary.

    Args:
        record: In-memory job record.

    Returns:
        Plain dict suitable for ``json.dump``.
    """
    result = record.result
    if hasattr(result, "to_dict"):
        result = result.to_dict()

    return {
        "job_id": record.job_id,
        "job_type": record.job_type,
        "state": record.state.value,
        "parameters": record.parameters,
        "result": result,
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "cancel_requested": record.cancel_requested,
        "checkpoint": asdict(record.checkpoint),
    }


def record_from_dict(data: dict[str, Any]) -> JobRecord:
    """
    Reconstruct a JobRecord from persisted JSON data.

    Args:
        data: Dictionary loaded from a job JSON file.

    Returns:
        JobRecord instance.
    """
    checkpoint_data = data.get("checkpoint") or {}
    checkpoint = JobCheckpoint(
        step_index=int(checkpoint_data.get("step_index", 0)),
        step_name=str(checkpoint_data.get("step_name", "")),
        partial_results=dict(checkpoint_data.get("partial_results") or {}),
    )
    return JobRecord(
        job_id=str(data["job_id"]),
        job_type=str(data["job_type"]),
        state=JobState(str(data["state"])),
        parameters=dict(data.get("parameters") or {}),
        result=data.get("result"),
        error=data.get("error"),
        created_at=str(data.get("created_at", "")),
        updated_at=str(data.get("updated_at", "")),
        cancel_requested=bool(data.get("cancel_requested", False)),
        checkpoint=checkpoint,
    )


def record_summary(record: JobRecord) -> dict[str, Any]:
    """
    Build a concise summary dict for CLI and list output.

    Args:
        record: Job record to summarize.

    Returns:
        Dict with id, type, state, timestamps, and checkpoint step.
    """
    return {
        "job_id": record.job_id,
        "job_type": record.job_type,
        "state": record.state.value,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "cancel_requested": record.cancel_requested,
        "checkpoint": {
            "step_index": record.checkpoint.step_index,
            "step_name": record.checkpoint.step_name,
        },
        "error": record.error,
    }
