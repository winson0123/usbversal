# Job Lifecycle

**Status:** partially implemented (TASK-040, TASK-041)

## States

| State | Description |
|-------|-------------|
| `pending` | Created, not yet scheduled |
| `running` | asyncio task active |
| `completed` | Finished successfully |
| `failed` | Terminal error |
| `cancelled` | User or system cancelled |

## Transitions

```text
pending ──start──► running ──success──► completed
                    │
                    ├──error──► failed
                    │
                    └──cancel──► cancelled
```

## Creation

Jobs are created by CLI or API with:

- `job_type` (e.g. `scan`, `apply`, `backup`)
- `parameters` (mount path, plan path, etc.)
- Optional `parent_job_id` for chained operations (planned)

### Implemented handlers

| `job_type` | Handler | Notes |
|------------|---------|-------|
| `scan` | `app/jobs/scan_job.py` | Runs `run_scan` in `asyncio.to_thread`; emits `JobProgress` and library scan events |

The `scan` CLI command uses `JobRunner.start("scan", …)` via `run_scan_job_sync()`.

## Persistence

Job records stored beside the running executable or application tree:

```text
<runtime_base>/jobs/<job_id>.json
```

For PyInstaller builds, ``runtime_base`` is the directory containing the binary.
For ``python -m app.cli``, it is the repository root (parent of ``app/``).
Override with ``USBVERSAL_JOBS_DIR`` when needed.

Contains state, checkpoints, cancel flags, backup references, and error messages. Stale `running` jobs are recovered as `failed` on load.

## Related

- [resumability.md](resumability.md)
- [cancellation.md](cancellation.md)
- [progress-reporting.md](progress-reporting.md)
