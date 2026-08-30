# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-30

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-316` |
| Objective | When `location.sqlite` exists, mark synced tracks analyzed |
| Completed | 2026-08-30 |

### Scope

- `app/adapters/serato/library_db.py`: set `analysis_flags` to 31.
- `app/services/sync_analysis.py`: still send an index row when tags already match.
- Tests for the flag and a no-op when already 31.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 372 passed, 4 skipped |

## Next

Ask the user. Re-sync after Serato has created `location.sqlite` to
flip the library-list blues.
