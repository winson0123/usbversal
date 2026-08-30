# Current Task

**Status:** `completed`
**Task ID:** `TASK-252`
**Last updated:** 2026-08-30

## Objective

Library two-pane: Playlists left with coloured `x/y` and no `-`, track
preview right (Title, Genre, Key, BPM). Settings and analysis-aware
yellow stay later.

## Files touched

- `app/tui/screens/library.py`
- `app/services/track_preview.py`
- `tests/test_tui_library.py`
- `tests/test_track_preview.py`
- `docs/tasks/backlog.md`
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
- pytest 351 passed / 4 skipped
