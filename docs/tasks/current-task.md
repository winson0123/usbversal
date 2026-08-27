# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-238` |
| Objective | Fold `sync_analysis.py` back into `sync_service.py` — restore the TASK-235 module shape |
| Completed | 2026-08-27 |

### Scope

- Merged analysis write / BPM correction back into `sync_service.py` (`_analysis_dat_path`, `_write_track_tags`, `_sync_analysis`, `correct_index_bpm`).
- Deleted `app/services/sync_analysis.py`.
- Kept `_COMMANDS` / `_emit_json` and the shared backup extra/unique helpers.
- File is 933 lines. Public signatures unchanged.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 284 passed, 4 skipped |

## Next

Ask the user.
