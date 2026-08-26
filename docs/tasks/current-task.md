# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-075` |
| Objective | Stop nested Rekordbox playlist folders colliding on the same Serato crate filename |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/adapters/serato/naming.py` — `crate_name_for()` now takes a required
  `by_id: dict[int, Playlist]` and walks `parent_id` up through it, joining
  each ancestor folder's sanitized name with the playlist's own using `%%`
  (Serato's documented, still-unverified convention). A dangling parent
  reference stops at the last resolvable ancestor instead of raising, and a
  cycle in `parent_id` (malformed data, never observed) terminates instead of
  looping forever.
- `app/services/sync_service.py` — the four call sites
  (`playlist_sync_states`, `find_crate_name_collisions`, and both branches of
  `sync_playlists`) now pass a `by_id` map built from the playlist list
  already in scope at each site; `find_crate_name_collisions`'s docstring
  updated to describe what it still catches now that cross-folder same-name
  collisions are gone (same-folder duplicates, and names that only collide
  after `sanitize_crate_name` strips characters)
- `tests/test_naming.py` (new) — seven direct tests: top-level maps to its
  own name, one level of nesting prefixes with the folder, deep nesting joins
  every ancestor in order, the actual bug this task fixes (two same-named
  playlists in different folders now get different crate names), each
  ancestor is sanitized independently, a dangling parent reference degrades
  gracefully, a parent cycle terminates
- `tests/test_sync_state.py` — three existing tests built crates keyed by the
  bare leaf name for playlists nested under a folder; updated to the `%%`-joined
  names the new `crate_name_for` actually produces
- `docs/schemas/serato-schema-notes.md`, `docs/tasks/backlog.md`,
  `docs/state/*.json`

### Design decisions

- **`by_id` is a required parameter, not optional-defaulting-to-flat.** An
  optional parameter defaulting to the old flattened behavior would have made
  "forgot to pass it" silently reintroduce the exact collision bug this task
  exists to fix. All four real call sites already had the full playlist list
  in scope, so requiring it added no real friction.
- **Cycle protection, even though never observed.** `build_playlist_tree`
  (TASK-201) already promotes a dangling-parent playlist to root rather than
  dropping it, on the same "never observed, but not assumed impossible"
  reasoning; `crate_name_for` extends the same caution to a `parent_id` cycle,
  which would otherwise hang the caller rather than just produce a wrong name.
- **Convention stays `[assumed]` in the docs, now with "implemented" added
  next to it.** No stick with a nested-folder playlist has been synced and
  checked in Serato — implementing the documented convention is not the same
  as confirming it, and the docs say so explicitly rather than letting
  "done" imply "verified."

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 226 passed, 4 skipped (no stick mounted, no `dist/usbversal` built; skips are 2 `/mnt/usb` integration tests, the opt-in full PyInstaller build, and the binary-help smoke test) |
| `.venv/bin/python -m app.cli --help` | unchanged |

## Next

`TASK-076` (bootstrap `_Serato_` on a rekordbox-only stick) — the last
pre-M11 item that doesn't need a real stick to implement and test against
synthetic fixtures. `TASK-090` (`export.pdb` DeviceSQL reader) remains
explicitly deferred in the backlog; both it and validating TASK-075's naming
convention need real hardware this session doesn't have.
