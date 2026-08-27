# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-235` |
| Objective | Split the remaining CC 11+ functions: `write_geob`, `build_track_record`, `_find_playlist` |
| Completed | 2026-08-27 |

### Scope

- `app/adapters/serato/tags.py`: `write_geob` is now copy / append / pad / splice.
- `app/services/track_records.py`: optional fields and size/date fields named separately.
- `app/services/migration_service.py`: `_find_playlist` dispatches to by-id and by-name.

Public signatures unchanged. No function in `app/` is left at CC 11+.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 284 passed, 4 skipped |

## Next

Ask the user. The Library two-pane redesign is still not started — see `docs/HANDOFF.md`.
