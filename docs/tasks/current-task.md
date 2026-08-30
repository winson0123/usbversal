# Current Task

**Status:** `completed`
**Task ID:** `TASK-305`
**Last updated:** 2026-08-30

## Objective

Stop clipping playlist tree names to a 16-cell column so nested folders
stay readable.

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
- pytest 353 passed / 4 skipped
