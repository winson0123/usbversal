# Current Task

**Status:** `completed`
**Task ID:** `TASK-311`
**Last updated:** 2026-08-30

## Objective

Light the parent path when the cursor is on a crate, and still light
every child guide when the cursor is on a folder.

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
- pytest 358 passed / 4 skipped
