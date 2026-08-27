# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-244` |
| Objective | Drop TASK-090; take `/mnt/usb` out of operator docs |
| Completed | 2026-08-27 |

### Scope

- `TASK-090` removed from `pending_tasks`; marked dropped in the backlog.
- Operator docs teach auto-detect (`/media/$USER`, `/Volumes`, drive letters).
  `USBVERSAL_MOUNT` stays as a one-line WSL escape hatch.
- `USBVERSAL_TEST_MOUNT` has no hardcoded default.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 276 passed, 4 skipped |

## Next

Library two-pane redesign (see [docs/HANDOFF.md](../HANDOFF.md)).
