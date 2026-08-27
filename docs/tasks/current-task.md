# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-237` |
| Objective | Flatten the TASK-236 helper explosion: inline one-off extracts, keep only splits that still earn their name |
| Completed | 2026-08-27 |

### Scope

- Inlined one-off CC-split helpers back into their callers across CLI, TUI, adapters, storage, and services.
- Kept the splits that still do real work: `_COMMANDS` / `_emit_json`, `sync_analysis.py`, shared backup extra/unique helpers, and the TASK-234/235 named steps.
- Public signatures unchanged.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 284 passed, 4 skipped |

## Next

Ask the user.
