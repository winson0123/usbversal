# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-28

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-247` |
| Objective | Host-side audio tag deltas instead of full songs on the USB |
| Completed | 2026-08-28 |

### Scope

- Default backup root is on the host (`~/.local/share/usbversal/backups/<volume>/`), not `backups/` on the stick.
- Audio files are stored as a `UVSD1` tag-region delta. Databases and crates stay full copies.
- `USBVERSAL_BACKUP_ROOT` overrides the host path.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 283 passed, 4 skipped |

## Next

`correct_index_bpm` live write (if approved), variable-tempo deck check, then Library two-pane redesign.
