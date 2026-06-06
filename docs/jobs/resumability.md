# Job Resumability

**Status:** partially implemented (TASK-042)

## Goal

Allow long-running jobs (large library scan, bulk apply) to resume after CLI exit or crash without duplicating backups or corrupting databases.

## Checkpoint Model

| Field | Purpose |
|-------|---------|
| `step_index` | Last successfully completed step |
| `step_name` | Human-readable step id |
| `backup_ids` | Backups already created for this job |
| `partial_results` | Paths/libraries already processed |

Stored on each `JobRecord` and persisted under `~/.config/usbversal/jobs/<job_id>.json`.

## Resume Rules

- Resume only from `failed` or `cancelled` (see `JobStore.prepare_resume`).
- Stale `running` jobs are marked `failed` with an interrupted message on startup.
- Scan jobs re-run discovery idempotently (read-only); checkpoint records mount/library counts.

## CLI

```bash
usbversal jobs list
usbversal jobs resume <job-id>
```

## Related

- [job-lifecycle.md](job-lifecycle.md)
- [../storage/backup-strategy.md](../storage/backup-strategy.md)
