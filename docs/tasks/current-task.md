# Current Task

**Status:** `completed`
**Task ID:** `TASK-304`
**Last updated:** 2026-08-30

## Objective

Narrow the Playlists pane, use rounded borders, separate the traffic-light
legend with a line, and keep the track table from scrolling sideways.

## Files touched

- `app/tui/screens/library.py`
- `tests/test_tui_library.py`
- `docs/tasks/backlog.md`
- `docs/HANDOFF.md`
- `docs/state/task-state.json`
- `docs/tasks/completed-tasks.md`

## Verification criteria

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

## Verification log

- ruff ✓
- ruff format ✓
- pytest 352 passed / 4 skipped
