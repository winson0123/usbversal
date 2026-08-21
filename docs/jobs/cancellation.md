# Job Cancellation

**Status:** implemented (TASK-042)

## Cooperative Cancellation

Jobs poll `ctx.check_cancelled()` between steps. No forced thread kill.

## Cancel Points

| Safe to cancel | Unsafe (must finish step) |
|----------------|---------------------------|
| Between mount scans | Mid SQLite transaction |
| Between playlist reads | During backup copy |
| Before apply write | During file replace |

## Behavior on Cancel

1. Set `cancel_requested` on the persisted job record
2. Running jobs observe the flag via `JobRunner._is_cancelled`
3. Emit `JobCancelled` event and set state to `cancelled`
4. Pending jobs are cancelled immediately when `jobs cancel` is invoked

## CLI

```bash
usbversal jobs cancel <job-id>
```

## Related

- [job-lifecycle.md](job-lifecycle.md)
- [../storage/rollback-flow.md](../storage/rollback-flow.md)
