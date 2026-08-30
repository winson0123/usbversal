# Current Task

**Status:** `completed`
**Task ID:** `TASK-306`
**Last updated:** 2026-08-30

## Objective

Drop the legend rule one row and colour the legend words to match the dots.

## Files touched

- `app/tui/screens/library.py`
- `tests/test_tui_library.py`
- `docs/tasks/backlog.md`
- `docs/tasks/completed-tasks.md`
- `docs/HANDOFF.md`
- `docs/state/task-state.json`
- `docs/state/repository-state.json`

## Verification criteria

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

## Verification log

- ruff ✓
- ruff format ✓
- pytest 354 passed / 4 skipped
