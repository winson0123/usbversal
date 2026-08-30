# Current Task

**Status:** `completed`
**Task ID:** `TASK-310`
**Last updated:** 2026-08-30

## Objective

Give the playlist tree the row above the legend, and keep parent
guide lines visible on the cursor row.

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
- pytest 356 passed / 4 skipped
