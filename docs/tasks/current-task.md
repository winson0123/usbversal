# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-211` |
| Objective | Two more user-reported issues on the same Library screen: the count/state columns still looked jagged despite TASK-210's fixed-width padding, and a request for an "All" option |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/services/sync_service.py` — `_rollup_state` renamed to
  `combine_sync_states` and made public (was already exactly the logic the
  new "All playlists" node's aggregate state needs; exporting it avoided
  writing the same three-way rule a second time in the TUI)
- `app/tui/screens/library.py` — the real fix and the real feature:
  - `_prefix_width(depth, is_folder)`: computes exactly how many cells
    Tree's own guide lines and expand icon consume before a label at a given
    depth, derived by reading `Tree.render_line()`'s actual output at
    several depths (`▼ `, `├── `, `│   └── `, etc.) rather than guessing —
    `depth * tree.guide_depth + (icon_width if is_folder else 0)`. Padding
    now accounts for this instead of assuming every row starts at the same
    offset, which naive fixed-width padding (TASK-210) did not.
  - Checkbox glyphs changed from unicode (✓/·/~) to plain ASCII (x/-/~):
    ambiguous-width unicode characters render as 1 or 2 terminal cells
    depending on font, which was throwing off exactly the rows that used
    them -- a second, independent source of the same jaggedness complaint.
  - Padding now measures cell width via `rich.cells.cell_len` instead of
    `len()`, so a playlist name with wide characters won't reintroduce the
    same class of bug.
  - "All playlists" is now a real, collapsible `Tree` folder node
    (`tree.root.add(..., expand=True)`) containing every top-level
    playlist/folder as children, not a sibling leaf next to them --
    collapsing it hides the whole library, and toggling it selects
    everything, both using the exact same mechanics every other folder
    already has.
  - New binding: `e` expands/collapses the highlighted folder.
    Tree's own default for this was space, which TASK-207 already
    repurposed for selection, so expand/collapse needed a home of its own.
- `tests/test_tui_library.py` — `_playlist_nodes()` helper (real playlists
  now sit one level under the "All playlists" node, not as `tree.root`'s
  direct children); existing tests updated for the new nesting and cursor
  position; four new tests: "All playlists" contains and aggregates every
  top-level node, it collapses on `e`, `e` on a leaf is a no-op, and the
  count column lands on the identical character offset across folder /
  nested-leaf / top-level-leaf rows (the direct regression test for the
  reported jaggedness)
- `docs/tasks/backlog.md`, `docs/state/*.json`

### Design decisions

- **Derived the padding formula empirically, not from documentation.**
  Textual's guide-rendering internals aren't part of its public API surface
  in a way that's simple to introspect directly; rendering known tree
  shapes and reading `Tree.render_line()`'s actual character output at each
  depth (0/1/2, folder/leaf) gave an exact, verifiable formula rather than
  an assumption that happened to look right in one test case.
- **"All playlists" restructured as the true container, not left as a
  summary row.** The user asked for it to be collapsible "as well" --
  meaning like other folders -- which only makes sense if it structurally
  *is* one. A sibling leaf with the same label text couldn't collapse
  anything, since it had no children of its own to hide.
- **`combine_sync_states` exported rather than reimplemented.** The "All"
  node's aggregate state needs exactly the rollup rule folders already use;
  giving the private function a public name and one doc update was cheaper
  and safer than a second, easy-to-drift copy of a three-way state rule in
  the TUI layer.
- **ASCII checkboxes, not merely `cell_len`-aware unicode ones.** Padding
  math trusts `cell_len`'s Unicode East Asian Width heuristic, but that
  heuristic doesn't universally match what every real terminal/font
  actually renders for *ambiguous-width* glyphs specifically (checkmarks,
  middle dots) -- switching to unambiguous ASCII sidesteps the whole
  category rather than trusting a heuristic that was already once wrong
  about how wide these exact glyphs render.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 248 passed, 4 skipped (no stick mounted in this environment, no `dist/usbversal` built) |
| `.venv/bin/python -m app.cli --help` | unchanged |
| Manual `Tree.render_line()` inspection | Built a 4-row synthetic tree (top-level folder, nested leaf, a deliberately long nested leaf, top-level leaf) and confirmed the count column starts at the identical character column on all but the over-length row, which shifts right rather than truncating or misaligning silently |
| Real hardware | **Not yet re-confirmed by the user.** Everything here was verified in this environment only, via direct `Tree.render_line()` inspection and `Pilot`-driven tests against synthetic fixtures. |

## Next

Ask the user to re-run against `/mnt/usb`: check that the count/state
columns line up visually now, that "All playlists" shows at the top and can
be collapsed with `e`, and that toggling it with space selects every
playlist in the library.
