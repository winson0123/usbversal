# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-207` |
| Objective | Screen 3 of the target flow: the playlist folder tree with a red/yellow/green state per node, and multi-select toggling |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/library.py` (new) — `LibraryScreen`: builds a
  `textual.widgets.Tree` from `sync_service.playlist_tree_sync_states()`,
  space toggles selection (a folder toggles every descendant playlist),
  enter reports the selection via `Tree.NodeSelected`
- `app/tui/screens/home.py` — `_open()` now pushes `LibraryScreen(library)`
  once a valid mount opens, completing the screen 2 → 3 handoff that was
  left as a terminal "Ready: ..." message in TASK-206
- `app/tui/app.py` — docstring updated to reflect Library existing
- `tests/test_tui_library.py` (new) — five tests via `Pilot`: every playlist
  appears labelled with its state, space selects a leaf, space again
  deselects, space on a folder selects every descendant, enter reports the
  selection without syncing
- `tests/test_tui_home.py` — the two tests that exercise a successful open
  now patch `LibraryScreen` with a trivial dummy screen (Library's own
  behaviour has its own test file) and assert on the handoff instead of on
  text that no longer applies once the screen changes
- `docs/planning/interactive-tui.md`, `docs/tasks/backlog.md`,
  `docs/state/*.json`

### Design decisions

- **Space beats Tree's own space binding via `priority=True`, not by editing
  Tree's `BINDINGS`.** First attempt subclassed `Tree` and filtered "space"
  out of the subclass's own `BINDINGS` list — this silently didn't work,
  because Textual's runtime binding resolution walks the whole MRO and
  merges `BINDINGS` from every base class, so the filtered-out entry came
  back from `Tree` itself. `Binding(..., priority=True)` on the *Screen* is
  the mechanism Textual actually provides for a container to override a
  focused child's own key handling, and it needed no `Tree` subclass at all.
- **Every folder starts expanded, and the cursor starts on the first node.**
  With space redirected to selection, there is no key left for expand/collapse
  in this screen, so nothing should default to collapsed. Discovered a second
  real bug the same way: `Tree.cursor_node` is `None` until something moves
  the cursor, so `action_toggle_selection`'s first real keypress was silently
  a no-op until `on_mount` explicitly sets `tree.cursor_line = 0`. Both bugs
  were caught by the same failing `Pilot` tests that exist to catch them, not
  discovered later by hand.
- **Labels use ✓/·/~ prefixes, not `[x]`/`[ ]`.** Tried the obvious bracket
  checkbox first; Rich markup parses `[x]` as an (unrecognised, silently
  dropped) style tag, since it's inside a label string. `[ ]` (a literal
  space) happens to survive because it isn't a valid tag name, which would
  have made the bug invisible until someone chose "selected" over
  "unselected" as their empty state and it silently vanished. Symbols with no
  bracket characters sidestep the whole class of problem.
- **Confirming a selection reports it rather than syncing.** `LibraryScreen`
  has no path to `sync_playlists()` yet -- that requires `JobRunner` wiring
  and a Progress screen, TASK-208's scope. Saying so in the status line
  ("not wired yet, TASK-208") is honest about what enter currently does
  rather than a screen that looks finished but silently does nothing.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 209 passed, 4 skipped (no stick mounted, no `dist/usbversal` built; skips are 2 `/mnt/usb` integration tests, the opt-in full PyInstaller build, and the binary-help smoke test) |
| `.venv/bin/python -m app.cli --help` | unchanged |

## Next

`TASK-208` (TUI Progress + Done screens) — the last M11 backlog item. Runs
`sync_playlists` as a job through `JobRunner`, renders progress with
`textual.widgets.ProgressBar` and `jobs.progress_rate.ProgressRateTracker`,
then a completion summary. This is also where `sync_playlists` first becomes
reachable from the TUI at all.
