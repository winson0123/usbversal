# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-231` |
| Objective | Library labels as `Text`; `leaf_ids` computed on `PlaylistTreeSyncState` |
| Completed | 2026-08-27 |

### Scope

- `app/services/sync_service.py`: `PlaylistTreeSyncState.leaf_ids` rolled up while building the tree.
- `app/tui/screens/library.py`: `_leaf_ids` removed; `_label` uses `rich.text.Text` so a `[` in a playlist name cannot break markup.

TUI restructure TASK-226–231 is done. Next pending product work is still the Library two-pane redesign in `docs/HANDOFF.md`.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 277 passed, 4 skipped |

## Next

Ask the user. The large pending Library screen redesign is still not started — see `docs/HANDOFF.md`.
