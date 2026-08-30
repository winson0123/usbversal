# Current Task

**Status:** `complete`
**Task ID:** `TASK-313`
**Last updated:** 2026-08-30

## Objective

Use Posting's amber in place of TUI green, and a brighter yellow on footer keys.

## Files touched

- `app/tui/palette.py`
- `app/tui/app.py`
- `app/tui/screens/library.py`
- `app/tui/screens/progress.py`
- `tests/test_tui_library.py`
- `tests/test_tui_progress.py`
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

- ruff: pass
- ruff format: pass
- pytest: 363 passed / 4 skipped
