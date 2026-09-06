# Current task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-09-06

## Recently completed

- TASK-337: Drop cosmetic TUI tests
- TASK-338: Disable Textual command palette / theme picker
- TASK-336: Quit promptly during ANLZ analysis (cooperative cancel)

## Verification (TASK-336)

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest tests/test_tui_app.py tests/test_track_sync_cancel.py tests/test_tui_home.py tests/test_sync_state.py -q
```

Pass: ruff clean; quit-during-analysis tests finish without multi-second waits.

README screenshot refresh left uncommitted until PNGs exist.

Next id is `TASK-339`.
