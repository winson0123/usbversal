# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-30

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-322` |
| Objective | Fix over-truncated titles and scan bar on crate switch |
| Completed | 2026-08-30 |

### Scope

- Title column width uses the Tracks pane when the table is hidden.
- A cancelled preview does not hide the scan bar for the next crate.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 379 passed, 4 skipped |

## Next

Ask the user. Re-sync after Serato has created `location.sqlite` to
flip the library-list blues. Live Serato on this stick uses
`analysis_flags = 24` for loaded tracks, not 31.
