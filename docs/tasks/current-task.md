# Current task

**Status:** `complete`
**Task ID:** `TASK-328`
**Last updated:** 2026-09-01

## Objective

Rewrite README.md as a short operator guide: what usbversal is, how to run a sync, and a plain overview of how Rekordbox data reaches Serato.

## Files touched

- `README.md`
- `docs/state/task-state.json`
- `docs/state/repository-state.json`
- `docs/tasks/current-task.md`
- `docs/tasks/backlog.md`

## Verification

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

- ruff check: pass
- ruff format: pass
- pytest: 332 passed, 3 skipped
