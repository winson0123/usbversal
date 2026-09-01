# Current task

**Status:** `complete`
**Task ID:** `TASK-329`
**Last updated:** 2026-09-01

## Objective

Remove README claims that do not help an operator, starting with the unused network line.

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
