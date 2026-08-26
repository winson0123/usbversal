# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-26

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-201` |
| Objective | Real playlist/folder nesting plus a per-folder aggregate sync state, the last piece `docs/planning/interactive-tui.md` names as a hard blocker for the TUI's library screen |
| Completed | 2026-08-26 |

### Scope

Files touched:

- `app/core/playlist_tree.py` (new) — `PlaylistNode` and `build_playlist_tree()`,
  nesting Rekordbox's flat `parent_id`-linked list into a real tree
- `app/services/sync_service.py` — `PlaylistTreeSyncState`, `_rollup_state()`,
  `playlist_tree_sync_states()`: walks the tree, giving each leaf its own
  state from `playlist_sync_states()` and each folder a state rolled up from
  its children
- `tests/test_playlist_tree.py` (new) — tree construction: flat lists, nested
  folders, arbitrary depth, sibling order, a dangling parent reference
  promoted to root rather than dropped, empty input
- `tests/test_sync_state.py` — four new tests for the rollup: all-synced
  folder is green, mixed children is yellow, an empty folder is red (not
  vacuously green), and the rollup composes through two nested folder levels
- `docs/planning/interactive-tui.md` — corrected the stale 110–115 task IDs
  and marked items 1, 2, 3, and 6 of the TUI gap list done

### Design decisions

- **Tree building lives in `core`, not `services`.** It only operates on the
  `Playlist` domain type and needs no adapter or mount access, so it belongs
  where `domain.py` already lives rather than in `sync_service.py` — matches
  the layer rule `core: []` (core depends on nothing outside itself).
- **The rollup composes rather than re-walking descendants.** A folder's
  state is computed from its *direct* children's states, and for a nested
  folder that child state is already itself a rollup — so the same
  all-synced/all-unsynced/else-partial rule at every level produces the
  correct answer for arbitrarily deep nesting without a separate "flatten and
  check every leaf" pass.
- **An empty folder is red, not green.** `all(...)` on an empty list is
  vacuously `True` in Python, which would have made an empty folder (or one
  holding only other empty folders) register as fully synced. `_rollup_state`
  special-cases no children as `NOT_SYNCED` explicitly, and it has a test.
- **A dangling `parent_id` promotes to root instead of vanishing.** Never
  observed on the real stick, but silently dropping a playlist because its
  declared parent went missing would be worse than surfacing it at the top
  level.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 183 passed, 3 skipped (no stick mounted; skips are the two `/mnt/usb` integration tests and the PyInstaller build) |
| `.venv/bin/python -m app.cli --help` | all commands listed (unchanged) |

## Next

`TASK-203` (removable-media polling) — the next M11 groundwork item.
`TASK-206` (TUI framework ADR + shell) is a framework choice among
`textual`/`prompt_toolkit`/`rich`/`curses` and is flagged as a decision point
rather than something to pick unilaterally.
