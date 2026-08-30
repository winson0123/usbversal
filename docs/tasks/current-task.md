# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-30

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-321` |
| Objective | Show the Home scan bar in the Library Tracks pane while loading |
| Completed | 2026-08-30 |

### Scope

- `ScanBar` widget shared by Home and Library.
- Tracks pane shows the bar until preview rows are ready.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 377 passed, 4 skipped |

## Next

Ask the user. Re-sync after Serato has created `location.sqlite` to
flip the library-list blues. Live Serato on this stick uses
`analysis_flags = 24` for loaded tracks, not 31.
