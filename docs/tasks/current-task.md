# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-210` |
| Objective | Two real-hardware findings from the same run: a synced playlist stayed "not synced" until the app restarted, and the user wanted `x/x` counts visible, not just the state word |
| Completed | 2026-08-27 |

### Scope

The user's report, after TASK-209's crash fix held on real hardware and a
sync actually completed: the "toilet" playlist still showed "not synced" on
the Library screen — only a full app restart picked up the change. Separately,
mid-fix, they asked for the sync/not-synced/partial indicator justified
properly, with `x/x` counts visible, not just the word.

Files touched:

- `app/services/sync_service.py` — `PlaylistTreeSyncState` gained `synced`
  and `total` fields: a leaf's own `in_crate`/`total` from
  `playlist_sync_states`, a folder's the sum across its children (composing
  through nesting depth the same way `state`'s rollup already did).
  `playlist_tree_sync_states()`'s `leaf_states` map now keeps the whole
  `PlaylistSyncState`, not just `.state`, so the counts are available to read.
- `app/tui/screens/library.py` — `on_mount` replaced by `on_screen_resume`,
  which (re)builds the entire tree from `playlist_tree_sync_states` every
  time this screen becomes the active one, not just the first time. Verified
  empirically that Textual fires `on_screen_resume` on a screen's first
  activation too (not just later resumes), so there's no separate "first
  load" path needed. `_label()` now renders `name / count / state` as
  fixed-width columns (`Tree` has no column model, so this is the closest a
  label string gets without giving up the folder hierarchy that's the whole
  point of this screen).
- `tests/test_sync_state.py` — two new tests: a leaf carries its own
  synced/total, a folder's are the sum of its children's
- `tests/test_tui_library.py` — `_write_crate()` helper extracted from
  `_stick()`'s inline crate-writing so a test can write a crate mid-run; one
  new test for the count columns; one new test that is the actual regression
  test for the reported bug — write a crate file after the screen has
  already loaded, simulate the Progress→Done→Library round trip (push a
  screen, pop it), and assert the tree now shows the update
- `docs/tasks/backlog.md`, `docs/state/*.json`

### Design decisions

- **`on_screen_resume` replaces `on_mount` entirely, not alongside it.**
  Confirmed with a standalone repro before touching real code: Textual fires
  `on_screen_resume` on a screen's very first activation, not only when
  something pushed above it is later popped. Keeping tree-building in both
  `on_mount` and `on_screen_resume` would have fetched sync state twice on
  every fresh load for no reason.
- **Counts flow through `PlaylistTreeSyncState`, not computed in the TUI.**
  The service layer already owns the state-rollup math (`_rollup_state`);
  putting the count-rollup right next to it keeps one place responsible for
  "what does this node's sync coverage actually mean," rather than the
  screen re-deriving totals from a tree it doesn't otherwise reason about.
- **Fixed-width label columns, not a `DataTable`.** A real table would align
  perfectly regardless of name length, but `DataTable` has no built-in tree
  nesting — the folder hierarchy is this screen's whole reason for existing.
  Padding the label string to fixed widths gets consistent-enough alignment
  without trading that away; a name long enough to overflow its column
  degrades to a shifted (but complete, not truncated) row rather than losing
  information.
- **Selection is cleared on every refresh**, including the redundant
  first-activation fire. A selection surviving a refresh triggered by an
  actual sync having just run doesn't make sense — those playlists were just
  acted on.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 243 passed, 4 skipped (no stick mounted in this environment, no `dist/usbversal` built) |
| `.venv/bin/python -m app.cli --help` | unchanged |
| Real hardware | **Not yet re-confirmed by the user.** TASK-209's crash fix is confirmed working (their sync completed); this task's two fixes (refresh-on-resume, count columns) were made in response to what they saw on that same run but haven't been re-run since. |

## Next

Ask the user to re-run against `/mnt/usb`: sync a playlist, confirm the
Library screen shows it as synced (with correct counts) immediately on
return, without restarting the app.
