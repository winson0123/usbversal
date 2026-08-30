# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-30

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-319` |
| Objective | Show Checking analysis on the Home detecting screen |
| Completed | 2026-08-30 |

### Scope

- Home detecting and opening captions include a second line:
  Checking analysis.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 376 passed, 4 skipped |

## Next

Ask the user. Re-sync after Serato has created `location.sqlite` to
flip the library-list blues. Live Serato on this stick uses
`analysis_flags = 24` for loaded tracks, not 31.
