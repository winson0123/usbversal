# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-236` |
| Objective | Bring every remaining `app/` function under CC 6 |
| Completed | 2026-08-27 |

### Scope

- Named steps extracted from every remaining CC 6–10 function in `app/`.
- Analysis write / index-BPM correction moved to `app/services/sync_analysis.py` so `sync_service.py` stays under 1000 lines (725).
- Public signatures unchanged (`correct_index_bpm` still imported from `sync_service`).

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 284 passed, 4 skipped |

## Next

Ask the user.
