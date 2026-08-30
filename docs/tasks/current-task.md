# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-30

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-303` |
| Objective | Yellow when a track is in the crate but Rekordbox analysis is not on the file; `x/y` counts green only |
| Completed | 2026-08-30 |

### Scope

- `app/services/track_sync.py`: shared crate + analysis verdict.
- `app/core/domain.py`: `PlaylistSyncState.complete`.
- `app/services/sync_service.py`: tree `x/y` uses the green count.
- `app/services/track_preview.py`: preview row colours match.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 369 passed, 4 skipped |

## Next

Library two-pane queue is empty. Settings extra columns stay unscoped
(user deferred). Ask the user.
