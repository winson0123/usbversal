# Job Lifecycle

**Status:** design placeholder — not implemented.

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
- Optional `parent_job_id` for chained operations

## Persistence (Planned)

Job records stored under user config dir:

```text
~/.config/usbversal/jobs/<job_id>.json
```

Contains state, checkpoints, backup references, error messages.

## Related

- [resumability.md](resumability.md)
- [cancellation.md](cancellation.md)
- [progress-reporting.md](progress-reporting.md)
