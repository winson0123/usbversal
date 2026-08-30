# Current Task

**Status:** `completed`
**Task ID:** `TASK-307`
**Last updated:** 2026-08-30

## Objective

Drop the All playlists parent so the tree is one level shallower, keep
select-all on a key, and put the selection count beside the mount path.

## Files touched

- `app/tui/screens/library.py`
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
- pytest 354 passed / 4 skipped
