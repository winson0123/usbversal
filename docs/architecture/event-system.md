# Event System

**Status:** design placeholder — not implemented.

## Purpose

Decouple operation progress from CLI rendering and enable future GUI subscribers without changing job or adapter internals.

## Event Shape (Planned)

```python
# Illustrative — not implemented
@dataclass(frozen=True)
class Event:
    type: str           # e.g. "job.progress"
    job_id: str | None
    payload: dict[str, Any]
    timestamp: datetime
```

## Event Categories

| Category | Examples | Consumers |
|----------|----------|-----------|
| `job.*` | started, progress, completed, failed, cancelled | CLI, logs |
| `scan.*` | library_found, mount_scanned | CLI |
| `adapter.*` | unknown_field, schema_version | logs, docs |
| `storage.*` | backup_created, rollback_done | CLI, audit |
| `warning.*` | db_locked, process_running | CLI stderr |

## Delivery Model

- Synchronous dispatch to subscribers in-process (initially).
- Subscribers must not raise; failures logged and ignored.
- No guaranteed ordering across job types unless documented per job.

## Forbidden

- Subscribers mutating adapter or database state
- Blocking I/O in subscriber callbacks

## Related

- [async-model.md](async-model.md)
- [../jobs/progress-reporting.md](../jobs/progress-reporting.md)
