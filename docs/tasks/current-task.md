# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-239` |
| Objective | Commit the leftover test trim; restore tests that still earn their keep |
| Completed | 2026-08-27 |

### Scope

- Merged overlapping Home searching tests into one; dropped the Enter-retry mock covered by the visible-resume test.
- Folded playlist count assertions into the existing tree-state test.
- Restored unique coverage: mid-timeout spin, stop-polling-once-open, Home bootstrap, `e` on a leaf, custom `USBVERSAL_MOUNT` name.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 281 passed, 4 skipped |

## Next

Ask the user.
