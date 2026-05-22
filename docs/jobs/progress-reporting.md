# Progress Reporting

**Status:** design placeholder — not implemented.

## Mechanisms

| Channel | Use case |
|---------|----------|
| Event bus | Structured `job.progress` events |
| CLI stderr | Human progress bar / spinner |
| `--json` stdout | NDJSON progress lines for scripting |

## Progress Payload (Planned)

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

Emit at most one progress event per 100ms unless `--verbose` requests every step.

## Related

- [../architecture/event-system.md](../architecture/event-system.md)
- [../architecture/cli-flow.md](../architecture/cli-flow.md)
