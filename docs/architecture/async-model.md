# Async Model

**Status:** partially implemented (TASK-040, TASK-041)

## Rationale

USB scans and database reads can take seconds to minutes. Blocking the CLI thread is unacceptable for interactive use and future GUI integration.

## Design

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `JobRunner` | Owns asyncio task lifecycle | Implemented (`app/jobs/runner.py`) |
| `JobRegistry` | Maps `job_id` → state, result, error | In-memory only |
| Job handlers | Async coroutines with `JobContext` | `scan` registered |
| `EventBus` | Publishes progress from worker coroutines | Skeleton (`app/core/event_bus.py`) |

## Job States

```text
pending → running → completed
                 ↘ failed
                 ↘ cancelled
```

## Concurrency Rules

- One job runner process per CLI invocation (initially).
- Adapter I/O uses `asyncio.to_thread` for blocking SQLite/file reads (scan job).
- No shared mutable adapter state across concurrent jobs (single-task policy at repo level).

## CLI Integration

`usbversal scan` delegates to `JobRunner` via `run_scan_job_sync()` in `app/jobs/scan_cli.py`.

## Resumability

Checkpoint metadata stored with job record (see `docs/jobs/resumability.md`) — not yet implemented (TASK-042).

## Related

- [../jobs/job-lifecycle.md](../jobs/job-lifecycle.md)
- [../decisions/0002-use-asyncio.md](../decisions/0002-use-asyncio.md)
