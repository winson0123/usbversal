# Async Model

**Status:** design placeholder — not implemented.

## Rationale

USB scans and database reads can take seconds to minutes. Blocking the CLI thread is unacceptable for interactive use and future GUI integration.

## Design

| Component | Responsibility |
|-----------|----------------|
| `JobRunner` | Owns asyncio task lifecycle |
| `JobRegistry` | Maps `job_id` → state, checkpoint, cancel token |
| `Job` protocol | `run(ctx) -> None` with cooperative cancel checks |
| Event bus | Publishes progress from worker coroutines |

## Job States

```text
pending → running → completed
                 ↘ failed
                 ↘ cancelled
```

## Concurrency Rules

- One job runner process per CLI invocation (initially).
- Adapter I/O uses `asyncio.to_thread` for blocking SQLite/file reads.
- No shared mutable adapter state across concurrent jobs (single-task policy at repo level).

## Resumability

Checkpoint metadata stored with job record (see `docs/jobs/resumability.md`):

- Last completed step index
- Paths and backup IDs already created

## Related

- [../jobs/job-lifecycle.md](../jobs/job-lifecycle.md)
- [../decisions/0002-use-asyncio.md](../decisions/0002-use-asyncio.md)
