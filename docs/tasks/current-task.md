# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-30

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-318` |
| Objective | Checking analysis stays on Home with a moving scan bar |
| Completed | 2026-08-30 |

### Scope

- Home phase `CHECKING` after `prepare_library`.
- `playlist_tree_sync_states` runs on Home; Library is pushed with those states.
- Scan bar stays mounted and keeps ticking until the handoff.

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
