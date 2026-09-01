# Current task

**Status:** `complete`
**Task ID:** `TASK-332`
**Last updated:** 2026-09-01

## Objective

Add from-source development steps to the README so running the Python checkout is documented, not only the release binary.

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
