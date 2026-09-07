# Current task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-09-07

## Recently completed

- TASK-339: Library click selects (not sync); track preview cache + prefetch

## Verification (TASK-339)

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest tests/test_tui_library.py tests/test_track_preview.py -q
```

Pass: 19 tests green; click toggles selection; enter syncs; revisit uses cache.

Next id is `TASK-340`.
