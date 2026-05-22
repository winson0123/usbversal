# Job Cancellation

**Status:** design placeholder — not implemented.

## Cooperative Cancellation

Jobs poll `ctx.is_cancelled()` between steps. No forced thread kill.

## Cancel Points

| Safe to cancel | Unsafe (must finish step) |
|----------------|---------------------------|
| Between mount scans | Mid SQLite transaction |
| Between playlist reads | During backup copy |
| Before apply write | During file replace |

## Behavior on Cancel

1. Set job state to `cancelled`
2. Emit `job.cancelled` event
3. If write started: attempt rollback if backup exists
4. Persist final state to job record

## CLI

```bash
usbversal jobs cancel <job-id>
```

## Related

- [job-lifecycle.md](job-lifecycle.md)
- [../storage/rollback-flow.md](../storage/rollback-flow.md)
