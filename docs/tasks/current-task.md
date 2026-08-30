# Current Task

**Status:** `completed`
**Task ID:** `TASK-309`
**Last updated:** 2026-08-30

## Objective

Select-all is `^a`, quit shows `^q`, hide the playlist scrollbar, and
match the track table to the native TUI colours.

## Files touched

- `app/tui/screens/library.py`
- `app/tui/app.py`
- `tests/test_tui_library.py`
- `docs/planning/interactive-tui.md`
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
- pytest 355 passed / 4 skipped
