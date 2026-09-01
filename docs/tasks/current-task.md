# Current task

**Status:** `complete`
**Task ID:** `TASK-331`
**Last updated:** 2026-09-01

## Objective

Show the Serato crate layout in the README as a tree, and drop the slash-in-playlist-name note.

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
