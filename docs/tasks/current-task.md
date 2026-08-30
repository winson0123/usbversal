# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-30

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-315` |
| Objective | Report a missing audio file as an analysis error instead of skipping it silently |
| Completed | 2026-08-30 |

### Scope

- `app/services/sync_analysis.py`: missing audio + ANLZ is `"audio file is missing"`.
- `tests/test_sync_analysis.py`: error vs quiet no-ANLZ.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 371 passed, 4 skipped |

## Next

Ask the user. Settings extra columns stay unscoped.
