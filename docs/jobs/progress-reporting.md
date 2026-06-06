# Progress Reporting

**Status:** partially implemented (TASK-022)

## Mechanisms

| Channel | Use case | Status |
|---------|----------|--------|
| Event bus | Structured `job.progress` events | Implemented |
| CLI stderr | Human progress lines | `scan` command |
| `--json` stdout | NDJSON progress lines for scripting | Planned |

## Progress Payload

```json
{
  "type": "job.progress",
  "job_id": "abc-123",
  "payload": {
    "current": 42,
    "total": 100,
    "message": "Scanning playlists"
  }
}
```

## Granularity

- **Scan jobs:** per mount, per library, per playlist batch
- **Apply jobs:** per plan step
- **Backup jobs:** per file copied with byte progress optional

## Throttling

CLI progress renders at most one line per 100ms unless `--verbose` is set on `scan`.

## Related

- [../architecture/event-system.md](../architecture/event-system.md)
- [../architecture/cli-flow.md](../architecture/cli-flow.md)
