# Job Resumability

**Status:** design placeholder — not implemented.

## Goal

Allow long-running jobs (large library scan, bulk apply) to resume after CLI exit or crash without duplicating backups or corrupting databases.

## Checkpoint Model (Planned)

| Field | Purpose |
|-------|---------|
| `step_index` | Last successfully completed step |
| `step_name` | Human-readable step id |
| `backup_ids` | Backups already created for this job |
| `partial_results` | Paths/libraries already processed |

## Resume Rules

- Resume only from `failed` or interrupted `running` (converted to `failed` on startup).
- Re-run idempotent steps (discovery) safely.
- Skip backup creation if `backup_ids` already contains required paths.
- Never resume into a write step without verifying backup still exists on disk.

## CLI

```bash
usbversal jobs resume <job-id>
```

## Related

- [job-lifecycle.md](job-lifecycle.md)
- [../storage/backup-strategy.md](../storage/backup-strategy.md)
