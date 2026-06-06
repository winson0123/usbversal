# Event System

**Status:** partially implemented (TASK-022)

## Purpose

Decouple operation progress from CLI rendering and enable future GUI subscribers without changing job or adapter internals.

## Event Shape

```python
@dataclass(frozen=True)
class Event:
    type: str           # e.g. "job.progress"
    job_id: str | None
    payload: dict[str, Any]
    timestamp: str      # ISO-8601 UTC
```

Implemented in `app/core/event_envelope.py`. Dataclass events from `app/core/events.py` are wrapped via `wrap_event()` before delivery.

## Event Categories

| Category | Examples | Consumers |
|----------|----------|-----------|
| `job.*` | started, progress, completed, failed, cancelled | CLI, logs |
| `scan.*` | started, library_found, completed | CLI |
| `adapter.*` | unknown_field, schema_version | logs, docs (planned) |
| `storage.*` | backup_created, rollback_done | CLI, audit (planned) |
| `warning.*` | db_locked, process_running | CLI stderr (planned) |

## Delivery Model

- `EventBus` (`app/core/event_bus.py`) dispatches synchronously to subscribers in-process.
- `JobRunner` publishes job and forwarded scan events through an optional bus.
- Subscribers must not raise; failures logged and ignored.
- No guaranteed ordering across job types unless documented per job.

## CLI Integration

`usbversal scan` attaches `CliProgressRenderer` to stderr when not using `--json` (see `app/cli/progress.py`).

## Forbidden

- Subscribers mutating adapter or database state
- Blocking I/O in subscriber callbacks

## Related

- [async-model.md](async-model.md)
- [../jobs/progress-reporting.md](../jobs/progress-reporting.md)
